import json
import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from httpx_validator import validate_coupon
from json_writer import (
    load_coupons_json,
    load_research_codes,
    merge_results,
    update_research_status,
    write_coupons_json,
)
from src.config import load_config
from src.results import CouponResult, ResultsWriter

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
CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.json")


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


@app.post("/run")
async def run_validation():
    if state["running"]:
        raise HTTPException(status_code=409, detail="Validation already running")

    state["running"] = True
    start_time = datetime.now(timezone.utc)
    try:
        config = load_config(CONFIG_PATH)
        all_regions = list(config["regions"].keys())

        # Merge config coupons with pending research codes
        research_path = os.path.join(DATA_DIR, "research.json")
        research_codes = load_research_codes(research_path)
        config_codes = set(c["code"] for c in config["coupons"])
        all_coupons = list(config["coupons"]) + [
            rc for rc in research_codes if rc["code"] not in config_codes
        ]
        logger.info(
            "Loaded %d config coupons + %d pending research codes",
            len(config["coupons"]),
            len(all_coupons) - len(config["coupons"]),
        )

        # Expand coupon+region combinations
        combinations = []
        for coupon in all_coupons:
            regions = all_regions if "*" in coupon["regions"] else coupon["regions"]
            for region_key in regions:
                if region_key in config["regions"]:
                    combinations.append((coupon, region_key))

        logger.info("Testing %d coupon+region combinations via HTTP", len(combinations))

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        csv_path = f"results/{timestamp}.csv"
        results_writer = ResultsWriter(csv_path, "screenshots")
        all_results = []

        for coupon, region_key in combinations:
            region_config = config["regions"][region_key]
            result = await validate_coupon(
                coupon_code=coupon["code"],
                region_key=region_key,
                proxy_url=region_config["proxy"],
                iherb_url=region_config["iherb_url"],
                locale_path=region_config.get("locale_path", ""),
            )
            results_writer.write_result(result)
            all_results.append({
                "coupon_code": result.coupon_code,
                "region": result.region,
                "valid": result.valid,
                "discount_amount": result.discount_amount,
                "discount_type": result.discount_type,
                "error_message": result.error_message,
            })

        results_writer.close()

        # Merge into coupons.json
        coupons_path = os.path.join(DATA_DIR, "coupons.json")
        existing = load_coupons_json(coupons_path)
        merged = merge_results(existing, all_results)
        write_coupons_json(merged, coupons_path)

        # Update research.json validation statuses
        update_research_status(research_path, all_results)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        summary = {
            "codes_validated": len(all_results),
            "valid": sum(1 for r in all_results if r["valid"] == "true"),
            "invalid": sum(1 for r in all_results if r["valid"] == "false"),
            "errors": sum(1 for r in all_results if r["valid"] == "error"),
            "csv_file": csv_path,
        }

        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_error"] = None
        state["healthy"] = True
        state["last_result"] = summary

        logger.info(
            "Done! %d valid, %d invalid, %d errors. CSV: %s",
            summary["valid"], summary["invalid"], summary["errors"], csv_path,
        )

        return {
            "status": "success",
            "duration_seconds": round(duration, 1),
            "summary": summary,
        }

    except Exception as e:
        state["last_error"] = str(e)
        state["healthy"] = False
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        logger.exception("Validation run failed")
        return {
            "status": "failure",
            "error": str(e),
        }
    finally:
        state["running"] = False
