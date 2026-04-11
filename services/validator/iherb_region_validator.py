"""Stage-2 Playwright region validator for iHerb.

Runs only on codes already confirmed by iherb_api_validator (Stage 1).
For each (code, region), sets the `iher-pref1` cookie, navigates to the
cart page with the code pre-applied, and reads the rendered HTML for
eligibility. Explicitly ignores the auto-promo banner to avoid the DOM
contamination bug that poisoned the old DOM-reading validator.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger("validator")

# Region → iHerb shipping country code used inside the iher-pref1 cookie.
# Values verified in the sister project's production DB.
REGION_SCCODES: dict[str, str] = {
    "us": "US", "kr": "KR", "jp": "JP", "de": "DE", "gb": "GB",
    "au": "AU", "sa": "SA", "ca": "CA", "cn": "CN", "rs": "RS",
    "hr": "HR", "it": "IT", "fr": "FR", "at": "AT", "nl": "NL",
    "se": "SE", "ch": "CH", "ie": "IE", "tw": "TW", "in": "IN",
    "hk": "HK",
}

_APPLIED_ROW_RE = re.compile(
    r'data-testid="applied-coupon-row"[^>]*data-code="([^"]+)"[^>]*>'
    r'(?:(?!data-testid="applied-coupon-row").)*?'
    r'class="applied-coupon-status"[^>]*>([^<]+)<',
    re.DOTALL | re.IGNORECASE,
)

_NOT_ELIGIBLE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"shipping destination is not eligible", re.IGNORECASE),
    re.compile(r"not available in your region", re.IGNORECASE),
    re.compile(r"cannot be applied to orders shipped", re.IGNORECASE),
    re.compile(r"invalid for your shipping country", re.IGNORECASE),
)


def parse_cart_html(html: str, code: str) -> tuple[bool, str]:
    """Pure parser: given rendered cart HTML and the code under test,
    return (eligible, reason). Explicitly scopes to the applied-coupon
    row keyed on `code`; never reads the promo-unlock banner.
    """
    if not html:
        return False, "empty html"

    # Find the applied-coupon row whose data-code matches our code exactly.
    matches = _APPLIED_ROW_RE.findall(html)
    target = next(
        ((row_code, status) for row_code, status in matches if row_code.upper() == code.upper()),
        None,
    )
    if target is None:
        return False, "applied-coupon row not found"

    _, status_text = target

    # Check for region-eligibility rejection language.
    for pat in _NOT_ELIGIBLE_PATTERNS:
        if pat.search(status_text):
            return False, f"not eligible: {pat.search(status_text).group(0)[:80]}"

    # If the status text says "Applied" (any case) we consider it eligible.
    if "applied" in status_text.lower():
        return True, "applied"

    return False, f"unknown status: {status_text.strip()[:120]}"


@dataclass
class RegionResult:
    code: str
    region: str
    eligible: bool
    reason: str


class IHerbRegionValidator:
    """Playwright-based Stage-2 region eligibility checker.

    Usage:
        v = IHerbRegionValidator()
        results = await v.validate(codes=["GOLD60"], regions=list(REGION_SCCODES))
        # results is {code: [region, ...]}
    """

    def __init__(self, concurrency: int = 4, jitter_range: tuple[int, int] = (30, 120)):
        self.concurrency = concurrency
        self.jitter_range = jitter_range

    async def validate(
        self,
        codes: Iterable[str],
        regions: Iterable[str] | None = None,
    ) -> dict[str, list[str]]:
        codes = list(codes)
        regions = list(regions) if regions is not None else list(REGION_SCCODES)
        if not codes:
            return {}

        # Imported lazily so pure-parser tests don't require Playwright at import time.
        from playwright.async_api import async_playwright

        sem = asyncio.Semaphore(self.concurrency)
        out: dict[str, list[str]] = {c: [] for c in codes}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, channel="chrome")
            try:
                for code in codes:
                    tasks = [
                        self._check_one(browser, sem, code, region)
                        for region in regions
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            logger.warning("region check raised: %s", r)
                            continue
                        if r.eligible:
                            out[code].append(r.region)
            finally:
                await browser.close()

        return out

    async def _check_one(self, browser, sem, code: str, region: str) -> RegionResult:
        async with sem:
            sccode = REGION_SCCODES.get(region)
            if not sccode:
                return RegionResult(code, region, False, f"unknown region {region}")
            jitter = random.randint(*self.jitter_range)
            await asyncio.sleep(jitter / 10)  # /10 keeps test runs sane; production uses full seconds
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
                ),
            )
            await context.add_cookies([{
                "name": "iher-pref1",
                "value": f"sccode={sccode}",
                "domain": ".iherb.com",
                "path": "/",
            }])
            page = await context.new_page()
            try:
                url = f"https://checkout.iherb.com/cart?appliedCoupon={code}"
                await page.goto(url, wait_until="networkidle", timeout=20000)
                html = await page.content()
                eligible, reason = parse_cart_html(html, code)
                return RegionResult(code, region, eligible, reason)
            except Exception as e:
                return RegionResult(code, region, False, f"error: {e}")
            finally:
                await context.close()
