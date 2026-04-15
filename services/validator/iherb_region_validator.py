"""Stage-2 Playwright region validator for iHerb.

Two-stage validation flow:
  Stage 1 (iherb_api_validator): HTTP-based, ~3s/code, filters to codes iHerb
    recognizes. Region-blind — always returns the same result regardless of
    shipping country.
  Stage 2 (this module): Playwright-based, ~2min/code/region. For each
    (code, region) pair, sets the iher-pref1 cookie with full URL-encoded
    format, loads the cart page, clicks "Add to Cart" on recommended items
    to build cart value, applies the coupon via the #coupon-input form, and
    classifies the rendered HTML for eligibility.

Why Playwright is needed: iHerb's apply-coupon JSON API is region-blind —
it returns the same recognition response regardless of the cart's bound
country. The eligibility signal is produced by iHerb's React app on the
cart page after applying, and only lives in the rendered HTML. No JSON
endpoint surfaces it.

The parser (parse_cart_html / _classify_html) is importable and callable
without Playwright — it's a pure function over HTML strings. This lets
unit tests run without a browser.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger("validator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Region → iHerb shipping country code used inside the iher-pref1 cookie.
# Values verified in the sister project's production DB.
REGION_SCCODES: dict[str, str] = {
    "us": "US", "kr": "KR", "jp": "JP", "de": "DE", "gb": "GB",
    "au": "AU", "sa": "SA", "ca": "CA", "cn": "CN", "rs": "RS",
    "hr": "HR", "it": "IT", "fr": "FR", "at": "AT", "nl": "NL",
    "se": "SE", "ch": "CH", "ie": "IE", "tw": "TW", "in": "IN",
    "hk": "HK", "es": "ES", "pl": "PL",
}

# Region → preferred proxy URL override. Empty by default — all regions use
# IHERB_PROXY_URL (proxy-local). Gluetun VPN proxies were tested (9001-9010
# exposed on docker gateway 172.19.0.1) but the country-mismatch between
# VPN exit IP and iher-pref1 cookie breaks iHerb's "Recommended for you"
# seeding: items become non-addable when the IP country doesn't match the
# cookie country. Keeping the hook in place for future use if we get
# exact-country VPNs (e.g. a real DE config instead of AT).
REGION_PROXY_MAP: dict[str, str] = {}

CART_URL = "https://checkout.iherb.com/cart"

# Anti-bot constants (inlined from sister project's browser.py)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--ignore-certificate-errors",
]

ANTI_WEBDRIVER_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
"""

# Coupon apply UI selectors (iHerb cart page, 2026 layout)
COUPON_INPUT = "#coupon-input"
COUPON_APPLY_BUTTON = "#coupon-apply"

# Add-to-cart from the empty-cart "Recommended for you" section
ADD_TO_CART_BUTTON = 'button:has-text("Add to Cart"):visible'
ADD_TO_CART_CLICKS = 6

# Timing
APPLY_SETTLE_MS = 6000
NAV_TIMEOUT_MS = 30000

# ---------------------------------------------------------------------------
# HTML classification regexes
# ---------------------------------------------------------------------------

# iHerb's React cart uses data-qa-element attributes to mark UI states.
APPLIED_QA = re.compile(
    r'data-qa-element="(?:applied-count-text|applied-promo)"', re.IGNORECASE,
)

REJECTED_QA = re.compile(
    r'data-qa-element="warning-msg-promo[^"]*"[\s\S]{0,300}?not\s+applied',
    re.IGNORECASE,
)

INELIGIBLE_REGION_QA = re.compile(
    r'data-qa-element="warning-msg-promo[^"]*"[\s\S]{0,300}?not\s+eligible',
    re.IGNORECASE,
)

NOT_ELIGIBLE_TEXT_PATTERNS = (
    re.compile(r"shipping destination is not eligible", re.IGNORECASE),
    re.compile(r"please\s+enter\s+a\s+valid\s+(?:promo|coupon|rewards)", re.IGNORECASE),
)

_SCRIPT_TAG = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r"<[^>]+>")

# Discount extraction
_PERCENT_AFTER_CODE_WINDOW = 500
_PERCENT_DISCOUNT = re.compile(r"(\d{1,2})\s*%", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Pure functions (no Playwright dependency)
# ---------------------------------------------------------------------------

def _strip_scripts(html: str) -> str:
    return _SCRIPT_TAG.sub("", html)


def _extract_discount(html: str, code: str) -> str | None:
    """Extract a discount percentage from a successfully-applied cart HTML.

    Only call this when the classifier has already confirmed the apply was
    accepted. Returns a string like "15% off" or None.

    Strips <script> blocks and HTML tags first so the regex matches against
    visible text only.
    """
    clean = _strip_scripts(html)
    text = _HTML_TAG.sub(" ", clean)

    code_match = re.search(re.escape(code), text, re.IGNORECASE)
    if not code_match:
        return None

    window = text[code_match.end():code_match.end() + _PERCENT_AFTER_CODE_WINDOW]
    pct_match = _PERCENT_DISCOUNT.search(window)
    if not pct_match:
        return None

    pct = int(pct_match.group(1))
    if pct < 5 or pct > 60:
        return None
    return f"{pct}% off"


def _build_iher_pref(sccode: str) -> str:
    """Build the iher-pref1 cookie value for a given shipping country.

    iHerb stores it URL-encoded on the wire (%26 for &, %3D for =). The
    format matches what the Ship-to modal's Save button writes client-side.
    """
    pairs = [
        ("bi", "1"),
        ("ifv", "1"),
        ("lan", "en-US"),
        ("lchg", "1"),
        ("sccode", sccode.upper()),
        ("scurcode", "USD"),
        ("storeid", "0"),
        ("wp", "1"),
    ]
    raw = "&".join(f"{k}={v}" for k, v in pairs)
    return raw.replace("=", "%3D").replace("&", "%26")


def parse_cart_html(html: str, code: str) -> tuple[bool, str, str | None]:
    """Classify rendered cart HTML after applying a coupon.

    Returns (is_eligible, reason, discount_display).

    discount_display is only populated when the apply was accepted.
    None means "applied but no discount text found" OR "rejected".

    Strips <script> blocks first to ignore iHerb's i18n translation bundle
    (which contains rejection-sounding constants that would false-trip).

    Authoritative signals from iHerb's React cart, in priority order:
    1. data-qa-element="warning-msg-promo*" with 'not eligible' -> rejected (region)
    2. data-qa-element="warning-msg-promo*" with 'not applied' -> rejected (rule)
    3. visible 'Please enter a valid promo' text -> rejected (unrecognized)
    4. visible 'shipping destination is not eligible' -> rejected (region)
    5. data-qa-element="applied-count-text" / "applied-promo" -> accepted
    Anything else defaults to NOT eligible (conservative).
    """
    if not html:
        return False, "empty html", None

    clean = _strip_scripts(html)

    # 1+2: explicit rejection markers in cart UI
    if INELIGIBLE_REGION_QA.search(clean):
        return False, "warning-msg-promo: not eligible", None
    if REJECTED_QA.search(clean):
        return False, "warning-msg-promo: not applied", None

    # 3+4: visible-text rejection fallbacks
    for pat in NOT_ELIGIBLE_TEXT_PATTERNS:
        m = pat.search(clean)
        if m:
            return False, f"text: {m.group(0)[:80]}", None

    # 5: positive applied signal — extract discount from the same HTML
    if APPLIED_QA.search(clean):
        discount = _extract_discount(html, code)
        return True, "applied-count-text present", discount

    # Conservative default: no explicit confirmation = not eligible.
    return False, "no apply confirmation", None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RegionResult:
    code: str
    region: str
    eligible: bool
    reason: str
    discount: str | None = None


# ---------------------------------------------------------------------------
# Validator class (lazy Playwright import)
# ---------------------------------------------------------------------------

class IHerbRegionValidator:
    """Playwright-based Stage-2 region eligibility checker.

    Usage:
        v = IHerbRegionValidator()
        results = await v.validate(codes=["GOLD60"], regions=list(REGION_SCCODES))
        # results is {code: [region, ...]}
    """

    def __init__(
        self,
        concurrency: int = 4,
        jitter_range: tuple[int, int] = (30, 120),
        fast_mode: bool = False,
        proxy_url: str | None = None,
    ):
        self.concurrency = concurrency
        self.jitter_range = jitter_range
        self.fast_mode = fast_mode
        if proxy_url is None:
            proxy_url = os.environ.get("IHERB_PROXY_URL", "")
        self.proxy_url = proxy_url

    async def validate(
        self,
        codes: Iterable[str],
        regions: Iterable[str] | None = None,
    ) -> dict[str, list[str]]:
        """Validate codes across regions. Returns {code: [eligible_region, ...]}.

        Thin wrapper around ``validate_detailed`` that keeps the legacy
        shape (just region codes) for backwards compatibility.
        """
        detailed = await self.validate_detailed(codes, regions)
        return {code: [r.region for r in results if r.eligible]
                for code, results in detailed.items()}

    async def validate_detailed(
        self,
        codes: Iterable[str],
        regions: Iterable[str] | None = None,
    ) -> dict[str, list[RegionResult]]:
        """Validate codes across regions, returning full per-region results.

        Unlike ``validate``, the returned list includes both eligible and
        ineligible regions plus the discount string extracted from the
        rendered HTML of successful applies.
        """
        codes = list(codes)
        regions = list(regions) if regions is not None else list(REGION_SCCODES)
        if not codes:
            return {}

        # Lazy import so pure-parser tests don't require Playwright at import time.
        from playwright.async_api import async_playwright

        sem = asyncio.Semaphore(self.concurrency)
        out: dict[str, list[RegionResult]] = {c: [] for c in codes}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True, channel="chrome", args=LAUNCH_ARGS,
            )
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
                        out[code].append(r)
            finally:
                await browser.close()

        return out

    async def _check_one(self, browser, sem, code: str, region: str) -> RegionResult:
        """Test one code in one region. Fresh browser context per call."""
        async with sem:
            sccode = REGION_SCCODES.get(region)
            if not sccode:
                return RegionResult(code, region, False, f"unknown region {region}")

            jitter = random.randint(*self.jitter_range)
            sleep_seconds = jitter / 10 if self.fast_mode else jitter
            await asyncio.sleep(sleep_seconds)

            # Lazy import for timeout exception
            from playwright.async_api import TimeoutError as PlaywrightTimeout

            context_kwargs: dict = {
                "user_agent": USER_AGENT,
                "viewport": {"width": 1280, "height": 900},
                "locale": "en-US",
                "ignore_https_errors": True,
            }
            # Prefer a country-matching VPN exit when available; Cloudflare
            # won't rate-limit these the way it does the host datacenter IP.
            region_proxy = REGION_PROXY_MAP.get(region, self.proxy_url)
            if region_proxy:
                context_kwargs["proxy"] = {"server": region_proxy}

            context = await browser.new_context(**context_kwargs)
            await context.add_init_script(ANTI_WEBDRIVER_SCRIPT)

            # Set the full iher-pref1 cookie (URL-encoded format, not just sccode=XX)
            await context.add_cookies([{
                "name": "iher-pref1",
                "value": _build_iher_pref(sccode),
                "domain": ".iherb.com",
                "path": "/",
                "secure": True,
                "sameSite": "Lax",
                "httpOnly": False,
            }])

            page = await context.new_page()
            page.set_default_timeout(NAV_TIMEOUT_MS)

            try:
                # Load cart — use 'commit' not 'networkidle' (iHerb never reaches networkidle)
                await page.goto(CART_URL, wait_until="commit", timeout=NAV_TIMEOUT_MS)
                await page.wait_for_timeout(6000)

                # Populate the cart via the empty-cart Recommended section.
                # Click multiple recommended items so the cart clears the
                # typical $60+ minimum thresholds.
                added = 0
                for _ in range(ADD_TO_CART_CLICKS):
                    try:
                        add_btn = page.locator(ADD_TO_CART_BUTTON).first
                        await add_btn.click(force=True, timeout=8000)
                        added += 1
                        await page.wait_for_timeout(1200)
                    except Exception:
                        break
                if added == 0:
                    return RegionResult(code, region, False, "add-to-cart failed (zero items)")

                # Reload so the cart page renders items
                try:
                    await page.reload(wait_until="commit", timeout=NAV_TIMEOUT_MS)
                    await page.wait_for_timeout(4000)
                except Exception:
                    pass

                # Confirm cart is non-empty
                empty_count = await page.locator('text="Your shopping cart is empty"').count()
                if empty_count > 0:
                    return RegionResult(code, region, False, "cart empty after add")

                # Apply the coupon
                try:
                    await page.wait_for_selector(COUPON_INPUT, state="visible", timeout=10000)
                    await page.locator(COUPON_INPUT).fill(code)
                    await page.locator(COUPON_APPLY_BUTTON).click()
                except PlaywrightTimeout:
                    return RegionResult(code, region, False, "coupon input not found")

                # Wait for apply to settle
                await page.wait_for_timeout(APPLY_SETTLE_MS)

                # Read the full cart HTML and classify
                try:
                    html = await page.content()
                except Exception as e:
                    return RegionResult(code, region, False, f"content read failed: {str(e)[:60]}")

                eligible, reason, discount = parse_cart_html(html, code)
                return RegionResult(code, region, eligible, reason, discount)

            except Exception as e:
                return RegionResult(code, region, False, f"error: {e}")
            finally:
                try:
                    await context.close()
                except Exception:
                    pass
