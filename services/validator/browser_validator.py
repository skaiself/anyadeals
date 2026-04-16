"""Two-stage iHerb validator orchestrator.

Stage 1: iherb_api_validator.IHerbAPIValidator (HTTP, ~3s/code)
Stage 2: iherb_region_validator.IHerbRegionValidator (Playwright, only survivors)

Failsafes (in order):
  1. Proxy health check  — GET iherb.com/robots.txt through IHERB_PROXY_URL before
                           Stage 2. If it fails, Stage 2 is skipped entirely.
  2. Canary check        — validate GOLD60 (known-always-valid) as the first Stage 2
                           test. If GOLD60 fails, the Playwright stack or iHerb cart
                           is broken; Stage 2 results are discarded.
  3. Stage 1 CascadingFailure — if iHerb's API returns transient errors for 10+
                           codes, Stage 1 aborts and returns [] (no changes).

With these in place the 3-consecutive-failures threshold is not needed: a single
Stage 2 failure is trustworthy once the canary and proxy checks pass.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import httpx

from iherb_api_validator import (
    IHerbAPIValidator,
    CascadingFailure,
    ProxyQuotaExhausted,
)
from iherb_region_validator import IHerbRegionValidator, REGION_SCCODES

logger = logging.getLogger("validator")

ALL_REGIONS: list[str] = list(REGION_SCCODES)

_PROXY_HEALTH_URL = "https://www.iherb.com/robots.txt"
_PROXY_HEALTH_TIMEOUT = 15  # seconds

# Canary: a code that should always be valid in the US.
# If it fails Stage 2, something is broken with the validator, not the codes.
_CANARY_CODE = "GOLD60"
_CANARY_REGION = "us"


async def check_proxy_health() -> bool:
    """Return True if the Stage 2 proxy can reach iHerb.

    If no proxy is configured, returns True (direct connection assumed OK).
    """
    proxy_url = os.environ.get("IHERB_PROXY_URL", "")
    if not proxy_url:
        return True
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=_PROXY_HEALTH_TIMEOUT,
            follow_redirects=True,
        ) as client:
            resp = await client.get(_PROXY_HEALTH_URL)
            ok = resp.status_code < 500
            if not ok:
                logger.warning("Proxy health check: HTTP %s", resp.status_code)
            return ok
    except Exception as exc:
        logger.warning("Proxy health check failed: %s", exc)
        return False


async def check_stage2_canary(region_validator: IHerbRegionValidator) -> bool:
    """Return True if GOLD60 applies successfully in US.

    A canary failure means Stage 2's Playwright stack or iHerb's cart is
    broken — not that the codes under test have expired.
    """
    results = await region_validator.validate_detailed([_CANARY_CODE], [_CANARY_REGION])
    region_results = results.get(_CANARY_CODE, [])
    eligible = any(r.eligible for r in region_results)
    if not eligible:
        logger.error(
            "Canary %s failed in %s — Stage 2 results unreliable, skipping.",
            _CANARY_CODE, _CANARY_REGION,
        )
    return eligible


def _stage1_failures_only(codes: list[str], stage1: list[dict]) -> list[dict]:
    """Build output containing only Stage 1 rejections.

    Stage 1 survivors are omitted so merge_browser_results leaves them
    untouched (fail_count not incremented).
    """
    by_code = {r["code"]: r for r in stage1}
    output: list[dict] = []
    for code in codes:
        s1 = by_code.get(code, {"valid": True})
        if not s1["valid"]:
            output.append({
                "code": code,
                "stage1_invalid": True,
                "results": {"us": {"valid": False, "message": s1.get("message", "")}},
            })
    return output


async def validate_codes(
    codes: Iterable[str],
    brand_notes_map: dict[str, str] | None = None,
    regions: Iterable[str] | None = None,
) -> list[dict]:
    """Run the two-stage validator over `codes`.

    Returns a list of dicts shaped like the old browser_validator output::

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

    # ── Stage 1: fast HTTP API check ────────────────────────────────────────
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

    # ── Stage 2 pre-flight: proxy + canary ──────────────────────────────────
    if not await check_proxy_health():
        logger.error(
            "Stage 2 skipped — proxy health check failed. "
            "fail_counts unchanged for Stage 1 survivors."
        )
        return _stage1_failures_only(codes, stage1)

    region_validator = IHerbRegionValidator()

    # Skip canary check if GOLD60 is already in the batch being tested
    # (it'll be validated naturally; no need to run it twice).
    if _CANARY_CODE not in survivors:
        if not await check_stage2_canary(region_validator):
            logger.error(
                "Stage 2 skipped — canary check failed. "
                "fail_counts unchanged for Stage 1 survivors."
            )
            return _stage1_failures_only(codes, stage1)

    # ── Stage 2: Playwright region checker ──────────────────────────────────
    stage2 = await region_validator.validate_detailed(survivors, regions)
    logger.info(
        "Stage 2 complete: %s",
        {c: sum(1 for r in res if r.eligible) for c, res in stage2.items()},
    )

    # Build output: merge Stage 1 discount fallback with Stage 2 per-region data.
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

        stage2_discount = next(
            (r.discount for r in region_results if r.eligible and r.discount),
            None,
        )
        discount = stage2_discount or stage1_discount

        if not eligible_regions:
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
