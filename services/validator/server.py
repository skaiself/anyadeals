import asyncio
import json
import logging
import os
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
from browser_validator import validate_codes, ALL_REGIONS

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


@app.post("/scrape-gutschein")
async def scrape_gutschein():
    """Run Playwright-based German Gutschein site scraper.

    Returns JSON array of {code, source, raw_description, raw_context}.
    """
    logger.info("Running Gutschein scraper")
    proc = await asyncio.create_subprocess_exec(
        "python", "gutschein_scraper.py", "--headless",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    stderr_text = stderr.decode("utf-8", errors="replace")
    for line in stderr_text.strip().splitlines()[-30:]:
        logger.info("[gutschein] %s", line.strip())

    if proc.returncode != 0:
        logger.error("Gutschein scraper failed (exit %d)", proc.returncode)
        return {"status": "error", "codes": []}

    try:
        codes = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError:
        logger.error("Gutschein scraper returned invalid JSON")
        codes = []

    logger.info("Gutschein scraper found %d codes", len(codes))
    return {"status": "ok", "codes": codes}


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

        # Build brand notes map for codes with "brand only" in notes
        brand_notes = {}
        for c in existing:
            notes = c.get("notes") or ""
            if "brand only" in notes.lower():
                brand_notes[c["code"]] = notes

        logger.info(
            "Two-stage validation: %d pending + %d active = %d unique codes, regions=%s, brand_codes=%d",
            len(pending_codes), len(active_codes), len(all_codes), requested_regions, len(brand_notes),
        )

        full_results = await validate_codes(all_codes, brand_notes, requested_regions)

        # Count stage-1 survivors for the summary payload.
        us_valid_codes = [
            item["code"]
            for item in full_results
            if any(r.get("valid") for r in item.get("results", {}).values())
        ]

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


@app.post("/rescue")
async def rescue_invalid():
    """One-shot backfill: re-validate every row currently marked `invalid`.

    See services/validator/rescue_backfill.py for the script entry point.
    """
    import rescue_backfill
    summary = await rescue_backfill.run()
    return {"status": "ok", "summary": summary}
