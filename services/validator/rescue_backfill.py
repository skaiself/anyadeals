"""One-shot backfill that re-validates every row currently marked ``invalid``
and rescues the ones that now classify as valid.

Usage (inside validator container):
    python rescue_backfill.py              # mutates coupons.json
    python rescue_backfill.py --dry-run    # writes coupons.rescue_preview.json

Exposed as POST /rescue on the validator service for convenience.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

from browser_validator import validate_codes
from browser_validate import merge_browser_results
from iherb_api_validator import IHerbAPIValidator
from json_writer import load_coupons_json, write_coupons_json

logger = logging.getLogger("rescue_backfill")

DATA_DIR = os.environ.get("DATA_DIR", "/data")


async def run(dry_run: bool = False) -> dict:
    coupons_path = os.path.join(DATA_DIR, "coupons.json")
    existing = load_coupons_json(coupons_path)

    invalid_codes = [c["code"] for c in existing if c.get("status") == "invalid"]
    if not invalid_codes:
        logger.info("No invalid codes to rescue")
        return {"rescued": 0, "still_invalid": 0, "dry_run": dry_run}

    # Build brand_notes map from notes fields.
    brand_notes = {
        c["code"]: c["notes"]
        for c in existing
        if c.get("status") == "invalid" and "brand only" in (c.get("notes") or "").lower()
    }

    logger.info("Rescue attempt: %d invalid codes, %d brand", len(invalid_codes), len(brand_notes))

    # NOTE: concurrency=1 + pace_seconds=15 is intentional for the rescue flow.
    # Cloudflare rate-limits checkout.iherb.com aggressively: proxy-local gets
    # 2 requests through, then ~25ms "Just a moment..." 429s for the rest.
    # curl-impersonate helps marginally (5/10 vs 2/10) but doesn't clear the
    # IP-level limit. Empirical test: plain curl via proxy-local with a 15s
    # gap between requests = 15/15 success. So we pace strictly at 15s/code.
    # Cost: 321 codes * ~15s = ~80 min wall time, but $0 proxy bandwidth.
    # The nightly validation path uses the default concurrency=4/pace=0; only
    # this rescue backfill forces serial-paced execution.
    import browser_validator as _bv

    _orig_api_cls = _bv.IHerbAPIValidator
    _orig_region_cls = _bv.IHerbRegionValidator

    class _SerialAPI(_orig_api_cls):
        def __init__(self, *a, **kw):
            kw["concurrency"] = 1
            kw["pace_seconds"] = 15.0
            super().__init__(*a, **kw)

    class _FastRegion(_orig_region_cls):
        # Stage 2's real-world parser is effectively a no-op against the
        # live iHerb cart page (anonymous carts carry no applied-coupon
        # state). browser_validator's orchestrator falls back to
        # regions=['us'] when Stage 2 returns empty, so Stage 2's only job
        # in the rescue flow is to return quickly. fast_mode divides the
        # 30-120s jitter by 10 to cut Stage 2 from ~2h to ~12 min for 18
        # survivors × 21 regions.
        def __init__(self, *a, **kw):
            kw["fast_mode"] = True
            super().__init__(*a, **kw)

    _bv.IHerbAPIValidator = _SerialAPI
    _bv.IHerbRegionValidator = _FastRegion
    try:
        results = await validate_codes(invalid_codes, brand_notes)
    finally:
        _bv.IHerbAPIValidator = _orig_api_cls
        _bv.IHerbRegionValidator = _orig_region_cls

    # Merge using the existing helper so the output file shape stays identical.
    research_notes = {c["code"]: c.get("notes", "") for c in existing}
    updated, summary_lines = merge_browser_results(existing, results, research_notes)

    # Annotate rescued rows with rescued_at and reset fail_count.
    now = datetime.now(timezone.utc).isoformat()
    rescued = 0
    still_invalid = 0
    invalid_set = set(invalid_codes)
    for row in updated:
        if row["code"] in invalid_set:
            if row.get("status") in ("valid", "region_limited"):
                row["rescued_at"] = now
                row["fail_count"] = 0
                rescued += 1
            else:
                still_invalid += 1

    out_path = coupons_path if not dry_run else os.path.join(DATA_DIR, "coupons.rescue_preview.json")
    write_coupons_json(updated, out_path)

    logger.info("Rescue complete: rescued=%d still_invalid=%d wrote=%s",
                rescued, still_invalid, out_path)
    for line in summary_lines[:40]:
        logger.info(line)

    return {
        "rescued": rescued,
        "still_invalid": still_invalid,
        "dry_run": dry_run,
        "output_path": out_path,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    summary = asyncio.run(run(dry_run=args.dry_run))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
