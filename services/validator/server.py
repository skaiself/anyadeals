import asyncio
import csv
import glob
import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from json_writer import load_coupons_json, merge_results, write_coupons_json

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
        from main import run
        await run(CONFIG_PATH, headed=False)

        result_files = sorted(glob.glob("results/*.csv"))
        summary = {"codes_validated": 0}

        if result_files:
            latest_csv = result_files[-1]
            results = []
            with open(latest_csv) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    results.append(row)

            coupons_path = os.path.join(DATA_DIR, "coupons.json")
            existing = load_coupons_json(coupons_path)
            merged = merge_results(existing, results)
            write_coupons_json(merged, coupons_path)

            summary = {
                "codes_validated": len(results),
                "csv_file": latest_csv,
            }

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_error"] = None
        state["healthy"] = True
        state["last_result"] = summary

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
