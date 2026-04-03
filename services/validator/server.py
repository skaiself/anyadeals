import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from json_writer import (
    load_coupons_json,
    load_research_codes,
    update_research_status,
    write_coupons_json,
)
from browser_validate import load_browser_results, merge_browser_results

logger = logging.getLogger("validator")
logging.basicConfig(level=logging.INFO)

state = {
    "healthy": True,
    "last_run": None,
    "last_error": None,
    "running": False,
    "last_result": None,
}

DATA_DIR = os.environ.get("DATA_DIR", "/data")

# All regions for full validation (after US filter pass)
ALL_REGIONS = ["us", "kr", "jp", "de", "gb", "au", "sa", "ca", "cn", "rs", "hr",
               "it", "fr", "at", "nl", "se", "ch", "ie", "tw", "in", "hk"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Validator service starting")
    yield
    logger.info("Validator service shutting down")


app = FastAPI(title="Validator Service", lifespan=lifespan)


@app.get("/status")
def get_status():
    return {
        "healthy": state["healthy"],
        "last_run": state["last_run"],
        "last_error": state["last_error"],
        "running": state["running"],
    }


async def _run_browser_validator(codes: list[str], regions: list[str]) -> list[dict]:
    """Run browser_validator.py and return parsed JSON results."""
    if not codes:
        return []

    results_path = f"/tmp/browser_results_{os.getpid()}.json"

    proc = await asyncio.create_subprocess_exec(
        "python", "browser_validator.py",
        "--codes", *codes,
        "--regions", *regions,
        "--headless",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    stderr_text = stderr.decode("utf-8", errors="replace")

    # Always log browser validator stderr (contains per-code results)
    for line in stderr_text.strip().splitlines()[-50:]:
        logger.info("[browser] %s", line.strip())

    if proc.returncode != 0:
        logger.error("Browser validator failed (exit %d)", proc.returncode)
        raise RuntimeError(f"Browser validator exited with code {proc.returncode}")

    # Parse JSON from stdout
    try:
        return json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError:
        logger.error("Failed to parse browser validator output: %s", stdout.decode()[:500])
        raise RuntimeError("Browser validator returned invalid JSON")


@app.post("/run")
async def run_validation(regions: str = ""):
    """Browser-only validation pipeline.

    Query params:
        regions: comma-separated region codes to test (e.g. "us,de,gb").
                 If empty, tests US first then all remaining regions.

    1. Load pending research codes + existing valid/region_limited codes
    2. Test all codes in US only (quick filter — ~45s each)
    3. Codes that pass US → test in specified (or all) remaining regions
    4. Update coupons.json with full regional results
    """
    if state["running"]:
        raise HTTPException(status_code=409, detail="Validation already running")

    state["running"] = True
    start_time = datetime.now(timezone.utc)
    try:
        # Parse requested regions
        if regions:
            requested_regions = [r.strip().lower() for r in regions.split(",") if r.strip()]
        else:
            requested_regions = list(ALL_REGIONS)

        # Always include US for the initial filter
        if "us" not in requested_regions:
            requested_regions.insert(0, "us")

        coupons_path = os.path.join(DATA_DIR, "coupons.json")
        research_path = os.path.join(DATA_DIR, "research.json")
        existing = load_coupons_json(coupons_path)

        # Gather all codes to test
        # 1. Pending research codes (not yet validated)
        research_codes = load_research_codes(research_path)
        pending_codes = [rc["code"] for rc in research_codes]

        # 2. Existing valid/region_limited codes (re-validation)
        active_codes = [c["code"] for c in existing
                        if c.get("status") in ("valid", "region_limited")]

        all_codes = list(dict.fromkeys(pending_codes + active_codes))  # deduplicate, preserve order

        if not all_codes:
            state["last_run"] = datetime.now(timezone.utc).isoformat()
            state["healthy"] = True
            return {"status": "success", "summary": "No codes to validate"}

        logger.info(
            "Browser validation: %d pending + %d active = %d unique codes, regions=%s",
            len(pending_codes), len(active_codes), len(all_codes), requested_regions,
        )

        # Phase 1: Test all codes in US only (quick filter)
        logger.info("Phase 1: Testing %d codes in US", len(all_codes))
        us_results = await _run_browser_validator(all_codes, ["us"])

        # Identify codes that passed US validation
        us_valid_codes = []
        for item in us_results:
            us_result = item.get("results", {}).get("us", {})
            if us_result.get("valid"):
                us_valid_codes.append(item["code"])

        logger.info("Phase 1 complete: %d/%d passed US filter", len(us_valid_codes), len(all_codes))

        # Phase 2: Test US-valid codes in remaining requested regions
        remaining_regions = [r for r in requested_regions if r != "us"]
        full_results = us_results  # Start with US results

        if us_valid_codes and remaining_regions:
            logger.info("Phase 2: Testing %d codes across %d regions",
                        len(us_valid_codes), len(remaining_regions))
            regional_results = await _run_browser_validator(us_valid_codes, remaining_regions)

            # Merge regional results into full_results
            us_map = {item["code"]: item for item in full_results}
            for item in regional_results:
                if item["code"] in us_map:
                    us_map[item["code"]]["results"].update(item.get("results", {}))
                else:
                    full_results.append(item)

        # Load AI-generated notes from research.json
        research_notes = {}
        if os.path.exists(research_path):
            with open(research_path) as f:
                for entry in json.load(f):
                    if entry.get("notes"):
                        research_notes[entry["code"]] = entry["notes"]

        # Process results into coupons.json
        updated, summary = merge_browser_results(existing, full_results, research_notes)
        write_coupons_json(updated, coupons_path)

        # Update research.json statuses
        research_api_results = []
        for item in full_results:
            for region, info in item.get("results", {}).items():
                research_api_results.append({
                    "coupon_code": item["code"],
                    "region": region,
                    "valid": "true" if info.get("valid") else "false",
                    "discount_amount": "",
                    "discount_type": "",
                    "error_message": info.get("message", ""),
                })
        update_research_status(research_path, research_api_results)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        result_summary = {
            "total_codes": len(all_codes),
            "us_valid": len(us_valid_codes),
            "us_invalid": len(all_codes) - len(us_valid_codes),
            "regions_tested": len(ALL_REGIONS) if us_valid_codes else 1,
        }

        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_error"] = None
        state["healthy"] = True
        state["last_result"] = result_summary

        logger.info("Done! %s (%.1fs)", result_summary, duration)
        for line in summary:
            logger.info(line)

        return {
            "status": "success",
            "duration_seconds": round(duration, 1),
            "summary": result_summary,
        }

    except Exception as e:
        state["last_error"] = str(e)
        state["healthy"] = False
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        logger.exception("Validation run failed")
        return {"status": "failure", "error": str(e)}
    finally:
        state["running"] = False
