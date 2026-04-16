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

    survivors = [r["code"] for r in stage1 if r["valid"]]
    logger.info("Stage 1 survivors: %s", survivors)

    if not survivors:
        # No codes survived Stage 1 — build failure output and return early.
        by_code = {r["code"]: r for r in stage1}
        output: list[dict] = []
        for code in codes:
            s1 = by_code.get(code, {"valid": False, "message": "no stage1 result"})
            output.append({
                "code": code,
                "stage1_invalid": True,
                "results": {"us": {"valid": False, "message": s1.get("message", "")}},
            })
        return output

    # Stage 2: Playwright region checker — tests survivors across all regions.
    # Uses the iher-pref1 cookie + recommended-items cart seeding + #coupon-input
    # form to get real eligibility signals from iHerb's React cart page.
    region_validator = IHerbRegionValidator()
    stage2 = await region_validator.validate_detailed(survivors, regions)
    logger.info(
        "Stage 2 complete: %s",
        {c: sum(1 for r in res if r.eligible) for c, res in stage2.items()},
    )

    # Build output: merge Stage 1 discount fallback with Stage 2 per-region
    # data including the discount string parsed from the applied-cart HTML.
    by_code = {r["code"]: r for r in stage1}
    output: list[dict] = []
    for code in codes:
        s1 = by_code.get(code, {"valid": False, "message": "no stage1 result"})
        if not s1["valid"]:
            output.append({
                "code": code,
                "stage1_invalid": True,
                "results": {"us": {"valid": False, "message": s1.get("message", "")}},
            })
            continue

        stage1_discount = _format_discount(
            s1.get("discount_pct", 0), s1.get("discount_raw", 0),
        )
        region_results = stage2.get(code, [])
        eligible_regions = {r.region for r in region_results if r.eligible}

        # Prefer Stage 2's HTML-extracted discount (e.g. "10% off" from the
        # applied-count-text). Fall back to Stage 1's API discount, then to
        # parse_discount_from_text() in the merge helper.
        stage2_discount = next(
            (r.discount for r in region_results if r.eligible and r.discount),
            None,
        )
        discount = stage2_discount or stage1_discount

        if not eligible_regions:
            # Stage 2 found zero regions — fall back to US-only from Stage 1.
            eligible_regions = {"us"}

        results: dict[str, dict] = {}
        for reg in regions:
            if reg in eligible_regions:
                results[reg] = {"valid": True, "discount": discount, "min_cart": ""}
            else:
                results[reg] = {"valid": False}
        output.append({"code": code, "results": results})

    return output


def _format_discount(pct: float, raw: float) -> str:
    if pct and pct > 0:
        return f"{int(pct)}% off"
    if raw and raw > 0:
        return f"${raw:.2f} off"
    return ""
