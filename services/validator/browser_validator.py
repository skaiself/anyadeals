"""Two-stage iHerb validator orchestrator.

Stage 1: iherb_api_validator.IHerbAPIValidator (HTTP, ~3s/code)
Stage 2: iherb_region_validator.IHerbRegionValidator (Playwright, only survivors)

The DOM-reading validator that lived here previously was removed - see
docs/superpowers/specs/2026-04-11-iherb-validator-rescue-design.md for why
(auto-promo banner DOM contamination false-invalidated real codes).
"""

from __future__ import annotations

import logging
from typing import Iterable

from iherb_api_validator import (
    IHerbAPIValidator,
    CascadingFailure,
    ProxyQuotaExhausted,
)
from iherb_region_validator import IHerbRegionValidator, REGION_SCCODES

logger = logging.getLogger("validator")

ALL_REGIONS: list[str] = list(REGION_SCCODES)


async def validate_codes(
    codes: Iterable[str],
    brand_notes_map: dict[str, str] | None = None,
    regions: Iterable[str] | None = None,
) -> list[dict]:
    """Run the two-stage validator over `codes`.

    Returns a list of dicts shaped like the old browser_validator output,
    so browser_validate.merge_browser_results consumes it unchanged::

        [
          {"code": "GOLD60",
           "results": {"us": {"valid": True, "discount": "10% off", "min_cart": "$60"},
                       "de": {"valid": False}}},
          ...
        ]
    """
    codes = list(codes)
    brand_notes_map = brand_notes_map or {}
    regions = list(regions) if regions is not None else ALL_REGIONS
    if not codes:
        return []

    api = IHerbAPIValidator()
    try:
        stage1 = await api.validate_many(codes, brand_notes_map)
    except (CascadingFailure, ProxyQuotaExhausted) as e:
        logger.error("Stage 1 aborted: %s", e)
        return []

    logger.info(
        "Stage 1 complete: %d/%d recognised",
        sum(1 for r in stage1 if r["valid"]),
        len(stage1),
    )

    # Stage 2 (Playwright region checker) is currently non-functional against
    # real iHerb HTML — the cart page carries no applied-coupon state for
    # anonymous sessions, so the parser always returns empty. Skipping it
    # avoids wasting ~2h of Playwright loads and prevents the fallback from
    # overwriting existing good region data with a degraded ['us'] default.
    #
    # When Stage 2 is fixed (e.g. by parsing DS_AutoApplyCartPromo from the
    # cart HTML, or by seeding cart items before loading), re-enable it here.
    survivors = [r["code"] for r in stage1 if r["valid"]]
    logger.info("Stage 1 survivors: %s", survivors)

    # Build output: Stage-1-valid codes get regions=['us'] (the only region
    # Stage 1 implicitly tests via its US-warehoused cart product). The merge
    # helper in browser_validate.py will NOT downgrade existing region data
    # that's richer than this — it only writes regions when the new set is
    # non-empty, so codes that already have multi-region data keep it.
    by_code = {r["code"]: r for r in stage1}
    output: list[dict] = []
    for code in codes:
        s1 = by_code.get(code, {"valid": False, "message": "no stage1 result"})
        if not s1["valid"]:
            output.append({
                "code": code,
                "results": {"us": {"valid": False, "message": s1.get("message", "")}},
            })
            continue
        discount = _format_discount(s1.get("discount_pct", 0), s1.get("discount_raw", 0))
        # Only claim US-valid — the one region Stage 1 actually proves.
        results: dict[str, dict] = {
            "us": {"valid": True, "discount": discount, "min_cart": ""},
        }
        output.append({"code": code, "results": results})

    return output


def _format_discount(pct: float, raw: float) -> str:
    if pct and pct > 0:
        return f"{int(pct)}% off"
    if raw and raw > 0:
        return f"${raw:.2f} off"
    return ""
