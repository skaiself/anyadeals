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
           "results": {"us": {"valid": True, "discount": "10% off", "min_cart_value": "$60"},
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

    survivors = [r["code"] for r in stage1 if r["valid"]]
    stage2: dict[str, list[str]] = {}
    if survivors:
        logger.info(
            "Stage 2: checking %d survivors x %d regions",
            len(survivors),
            len(regions),
        )
        stage2 = await IHerbRegionValidator().validate(survivors, regions)

    # Build the output in the shape that browser_validate.merge_browser_results expects.
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
        eligible_regions = stage2.get(code, [])
        # If stage 2 wasn't run (empty regions list) assume all regions OK.
        active_regions = eligible_regions or list(regions)
        results: dict[str, dict] = {
            r: {"valid": True, "discount": discount, "min_cart_value": ""}
            for r in active_regions
        }
        for r in regions:
            results.setdefault(r, {"valid": False, "message": "region not eligible"})
        output.append({"code": code, "results": results})

    return output


def _format_discount(pct: float, raw: float) -> str:
    if pct and pct > 0:
        return f"{int(pct)}% off"
    if raw and raw > 0:
        return f"${raw:.2f} off"
    return ""
