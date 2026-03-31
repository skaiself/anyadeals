"""Researcher service — discovers iHerb promo codes from web sources."""

import json
import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

logger = logging.getLogger("researcher")
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
    logger.info("Researcher service starting")
    yield
    logger.info("Researcher service shutting down")


app = FastAPI(title="Researcher Service", lifespan=lifespan)


@app.get("/status")
def get_status():
    return {
        "healthy": state["healthy"],
        "last_run": state["last_run"],
        "last_error": state["last_error"],
        "running": state["running"],
    }


@app.post("/run")
async def run_research():
    if state["running"]:
        raise HTTPException(status_code=409, detail="Research already running")

    state["running"] = True
    start_time = datetime.now(timezone.utc)
    try:
        from scraper import run_all_scrapers
        from claude_parser import parse_and_deduplicate
        from json_writer import load_research_json, merge_research, write_research_json

        # Step 1: Scrape all sources
        raw_codes = await run_all_scrapers()
        logger.info("Scraped %d raw code entries", len(raw_codes))

        # Save raw codes for external AI processing
        raw_path = os.path.join(DATA_DIR, "raw_codes.json")
        with open(raw_path, "w") as f:
            json.dump(raw_codes[:50], f, indent=2, default=str)

        # Step 2: Parse and deduplicate with Claude CLI
        parsed_codes = await parse_and_deduplicate(raw_codes)
        logger.info("Parsed %d unique codes", len(parsed_codes))

        # Step 3: Merge into research.json
        research_path = os.path.join(DATA_DIR, "research.json")
        existing = load_research_json(research_path)
        merged = merge_research(existing, parsed_codes)
        write_research_json(merged, research_path)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        summary = {
            "sources_scraped": len(raw_codes),
            "codes_found": len(parsed_codes),
            "total_in_research": len(merged),
        }

        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_error"] = None
        state["healthy"] = True
        state["last_result"] = summary

        logger.info("Research complete: %s", summary)
        return {"status": "success", "duration_seconds": round(duration, 1), "summary": summary}

    except Exception as e:
        state["last_error"] = str(e)
        state["healthy"] = False
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        logger.exception("Research run failed")
        return {"status": "failure", "error": str(e)}
    finally:
        state["running"] = False


@app.get("/raw-codes")
def get_raw_codes():
    """Return latest raw scraped entries for external AI parsing."""
    data_dir = os.environ.get("DATA_DIR", "/data")
    raw_path = os.path.join(data_dir, "raw_codes.json")
    if not os.path.exists(raw_path):
        return []
    with open(raw_path) as f:
        raw = json.load(f)
    return raw[:50]
