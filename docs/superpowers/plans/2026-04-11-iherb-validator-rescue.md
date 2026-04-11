# iHerb Validator Rescue — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the DOM-reading Playwright validator with a two-stage HTTP-API-first validator, centralise scraper false-positive filtering, and rescue the false-invalidated codes currently sitting in `coupons.json`.

**Architecture:** Stage 1 is an HTTP-only validator (`iherb_api_validator.py`) that calls `checkout.iherb.com/api/Carts/v2/applyCoupon` via `curl`, classifies recognition in ~3s/code, and rejects anything with `appliedCouponCodeType=2` (referral). Stage 2 is a Playwright-based region checker (`iherb_region_validator.py`) that runs only on Stage 1 survivors: it sets the `iher-pref1` cookie and reads the cart HTML (explicitly excluding the auto-promo banner) for eligibility per region. A one-shot `rescue_backfill.py` reprocesses all 320 existing `invalid` rows through Stage 1+2 once.

**Tech Stack:** Python 3.12, httpx, curl subprocess, Playwright (chromium, headless), pytest, FastAPI, existing Docker Compose validator container.

**Spec:** `docs/superpowers/specs/2026-04-11-iherb-validator-rescue-design.md`
**Sister reference:** `/home/skaiself/repo/anyadealsplus/playwright_worker/validators/iherb_api.py`, `/home/skaiself/repo/anyadealsplus/docs/iherb-validation.md`

**Working directory for services (inside docker):** `/app` for each service container. Validator container has `DATA_DIR=/data` mounted to host `site/data/`.

---

## File Structure

**New files:**
- `services/researcher/parsers/__init__.py` — package marker
- `services/researcher/parsers/code_filter.py` — centralised FALSE_POSITIVES + referral phrase filter
- `services/researcher/tests/test_code_filter.py`
- `services/validator/iherb_api_validator.py` — Stage 1, HTTP API, curl
- `services/validator/iherb_region_validator.py` — Stage 2, Playwright HTML scan
- `services/validator/rescue_backfill.py` — one-shot rescue CLI
- `services/validator/tests/test_iherb_api_validator.py`
- `services/validator/tests/test_iherb_region_validator.py`
- `services/validator/tests/test_rescue_backfill.py`
- `services/validator/tests/fixtures/cart_with_autopromo_banner.html` — regression fixture for the contamination bug
- `services/validator/tests/fixtures/cart_ineligible_region.html` — fixture for region eligibility scan

**Modified files:**
- `services/researcher/sources/reddit.py` — call `filter_results`, drop inlined FALSE_POSITIVES
- `services/researcher/sources/couponfollow.py` — call `filter_results`, drop inlined FALSE_POSITIVES
- `services/researcher/sources/generic.py` — call `filter_results`
- `services/validator/browser_validator.py` — gut DOM path, become thin orchestrator
- `services/validator/server.py` — swap `/run` wiring, add `/rescue` endpoint

**Unchanged (explicitly):**
- `services/validator/browser_validate.py` — reuse `merge_browser_results` as-is
- `services/validator/gutschein_scraper.py` — gutschein flow keeps Playwright
- `services/validator/json_writer.py`
- `services/researcher/claude_parser.py` — AI enrichment still runs on top

---

## Task 1: `code_filter.py` and tests

**Files:**
- Create: `services/researcher/parsers/__init__.py`
- Create: `services/researcher/parsers/code_filter.py`
- Create: `services/researcher/tests/test_code_filter.py`

- [ ] **Step 1: Create the parsers package marker**

Write `services/researcher/parsers/__init__.py`:

```python
```

(Empty file — just marks the package.)

- [ ] **Step 2: Write the failing test**

Write `services/researcher/tests/test_code_filter.py`:

```python
"""Tests for the centralised code_filter module."""
from parsers.code_filter import (
    FALSE_POSITIVES,
    REFERRAL_PHRASES,
    is_false_positive,
    looks_like_referral,
    filter_results,
)


def test_false_positive_set_contains_known_junk():
    for junk in ("HTTP", "HTML", "NONE", "IHERB", "VITAMIN", "PROMO", "COUPON", "NBSP"):
        assert junk in FALSE_POSITIVES


def test_is_false_positive_case_insensitive():
    assert is_false_positive("http") is True
    assert is_false_positive("HTTP") is True
    assert is_false_positive("GOLD60") is False


def test_is_false_positive_rejects_short_codes():
    assert is_false_positive("AB") is True  # too short
    assert is_false_positive("ABC") is True  # still too short
    assert is_false_positive("ABCD") is False  # 4 is the minimum


def test_looks_like_referral_catches_my_code_phrase():
    assert looks_like_referral("Use my code ARWAOM for 5% off your first order") is True
    assert looks_like_referral("my referral link gives you a bonus") is True


def test_looks_like_referral_does_not_fire_on_plain_promos():
    assert looks_like_referral("Save 15% off your order with code GOLD60") is False
    assert looks_like_referral("Today's iHerb promo: 10% off sitewide") is False


def test_filter_results_drops_false_positive_codes():
    results = [
        {"code": "GOLD60", "raw_context": "Save 10% off"},
        {"code": "HTTP", "raw_context": "Save 10% off"},
        {"code": "ARWAOM", "raw_context": "use my code ARWAOM"},
        {"code": "CHI22", "raw_context": "iHerb promo codes April 2026"},
    ]
    kept = filter_results(results)
    kept_codes = {r["code"] for r in kept}
    assert kept_codes == {"GOLD60", "CHI22"}


def test_filter_results_tolerates_missing_raw_context():
    results = [{"code": "GOLD60"}]
    kept = filter_results(results)
    assert len(kept) == 1


def test_filter_results_preserves_original_fields():
    results = [{"code": "GOLD60", "source": "reddit", "raw_description": "10% off"}]
    kept = filter_results(results)
    assert kept[0] == results[0]
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd /home/skaiself/repo/anyadeals/services/researcher && python -m pytest tests/test_code_filter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'parsers.code_filter'`.

- [ ] **Step 4: Implement `code_filter.py`**

Write `services/researcher/parsers/code_filter.py`:

```python
"""Centralised false-positive and referral-phrase filter for scraped codes.

All scrapers in services/researcher/sources/ should call filter_results()
before returning, so junk tokens and personal referral codes never enter
the pipeline.
"""

FALSE_POSITIVES: frozenset[str] = frozenset({
    "HTTP", "HTML", "HEAD", "BODY", "META", "LINK", "NONE",
    "TRUE", "FALSE", "NULL", "JSON", "SELF", "POST", "NSFW",
    "REDDIT", "SUBREDDIT", "COMMENT", "HTTPS", "HREF", "TITLE",
    "IHERB", "HERB", "VITAMIN", "PROMO", "CODE", "COUPON",
    "EDIT", "UPDATE", "DELETED", "REMOVED", "TLDR", "NBSP",
    "IMGUR", "JPEG", "WEBP", "IFRAME", "CDATA",
})

REFERRAL_PHRASES: tuple[str, ...] = (
    "my code",
    "use my",
    "my referral",
    "my link",
    "my iherb",
    "new customer discount with",
    "first order with code",
    "first purchase with code",
)

MIN_CODE_LENGTH = 4


def is_false_positive(code: str) -> bool:
    """Return True if `code` is too short or belongs to the junk set."""
    if not code or len(code) < MIN_CODE_LENGTH:
        return True
    return code.upper() in FALSE_POSITIVES


def looks_like_referral(context: str) -> bool:
    """Return True if context text suggests a personal referral / affiliate code."""
    if not context:
        return False
    lowered = context.lower()
    return any(phrase in lowered for phrase in REFERRAL_PHRASES)


def filter_results(results: list[dict]) -> list[dict]:
    """Drop entries whose code is a false positive or whose raw_context
    triggers a referral phrase. Preserves all other fields and ordering.
    """
    kept: list[dict] = []
    for r in results:
        code = r.get("code", "")
        if is_false_positive(code):
            continue
        context = r.get("raw_context", "") or r.get("raw_description", "")
        if looks_like_referral(context):
            continue
        kept.append(r)
    return kept
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd /home/skaiself/repo/anyadeals/services/researcher && python -m pytest tests/test_code_filter.py -v
```

Expected: `7 passed`.

- [ ] **Step 6: Commit**

```bash
cd /home/skaiself/repo/anyadeals && \
git add services/researcher/parsers/__init__.py \
        services/researcher/parsers/code_filter.py \
        services/researcher/tests/test_code_filter.py && \
git commit -m "feat(researcher): add centralised code_filter for false positives and referrals"
```

---

## Task 2: Wire `code_filter` into scrapers

**Files:**
- Modify: `services/researcher/sources/reddit.py`
- Modify: `services/researcher/sources/couponfollow.py`
- Modify: `services/researcher/sources/generic.py`

- [ ] **Step 1: Inspect current reddit scraper**

```bash
sed -n '1,40p' /home/skaiself/repo/anyadeals/services/researcher/sources/reddit.py
```

Confirm there is an inline `FALSE_POSITIVES = frozenset({...})` near the top and an `_extract_codes` method that references it.

- [ ] **Step 2: Update reddit.py**

In `services/researcher/sources/reddit.py`:

- **Add import** near the other `from sources.*` imports:

```python
from parsers.code_filter import filter_results, is_false_positive
```

- **Delete** the module-level `FALSE_POSITIVES = frozenset({...})` block.

- **Replace** the guard inside `_extract_codes` that reads `if code in seen or code in FALSE_POSITIVES:` with:

```python
                if code in seen or is_false_positive(code):
                    continue
```

- **At the end of `scrape()`**, right before `logger.info("[%s] Found %d potential codes", self.name, len(results))`, add:

```python
        results = filter_results(results)
```

- [ ] **Step 3: Update couponfollow.py**

In `services/researcher/sources/couponfollow.py`:

- Add `from parsers.code_filter import filter_results, is_false_positive` next to the other imports.
- Delete the module-level `FALSE_POSITIVES = frozenset({...})` block.
- Replace `if code in seen or code in FALSE_POSITIVES:` with `if code in seen or is_false_positive(code):` (there are two occurrences — one in the href loop, one in the fallback regex loop).
- Replace `if code in seen or len(code) < 4 or code in FALSE_POSITIVES:` with `if code in seen or is_false_positive(code):`.
- Before `return results`, add:

```python
        results = filter_results(results)
```

- [ ] **Step 4: Update generic.py**

In `services/researcher/sources/generic.py`:

- Add `from parsers.code_filter import filter_results, is_false_positive` next to the other imports.
- Delete the inline tuple guard `if code in ("HTTP", "HTML", ...)`.
- Replace `if code in seen or len(code) < 4:` with `if code in seen or is_false_positive(code):`.
- Before the final `logger.info(...)` / `return results`, add:

```python
        results = filter_results(results)
```

- [ ] **Step 5: Run the existing researcher test suite**

```bash
docker exec anyadeals-researcher python -m pytest tests/ -v
```

Expected: all previously-passing tests still pass. If `tests/test_reddit.py` asserts on `FALSE_POSITIVES` symbol directly, update the import to `from parsers.code_filter import FALSE_POSITIVES`.

- [ ] **Step 6: Smoke-test the reddit scraper end-to-end**

```bash
docker exec anyadeals-researcher python -c "
import asyncio
from sources.reddit import RedditScraper
codes = asyncio.run(RedditScraper().scrape())
junk = [c for c in codes if c['code'] in {'HTTP','IHERB','PROMO','VITAMIN','NBSP'}]
ref = [c for c in codes if 'my code' in (c.get('raw_context','') or '').lower()]
print(f'total={len(codes)} junk={len(junk)} referral_leak={len(ref)}')
assert junk == [], f'junk leaked: {junk[:3]}'
assert ref == [], f'referral leaked: {ref[:3]}'
print('OK')
"
```

Expected: `junk=0 referral_leak=0 OK`.

- [ ] **Step 7: Commit**

```bash
cd /home/skaiself/repo/anyadeals && \
git add services/researcher/sources/reddit.py \
        services/researcher/sources/couponfollow.py \
        services/researcher/sources/generic.py && \
git commit -m "refactor(researcher): route scrapers through centralised code_filter"
```

---

## Task 3: Stage 1 — `iherb_api_validator.py`

**Files:**
- Create: `services/validator/iherb_api_validator.py`
- Create: `services/validator/tests/test_iherb_api_validator.py`

Read the sister reference first:

```bash
cat /home/skaiself/repo/anyadealsplus/playwright_worker/validators/iherb_api.py
```

You will port this file. The **adaptations** you must make:

1. **Drop the `BaseValidator` import.** Current project has no `playwright_worker.validators.base` module. Remove the `from playwright_worker.validators.base import BaseValidator` line and change `class IHerbAPIValidator(BaseValidator):` to `class IHerbAPIValidator:`.
2. **Keep the `_curl` helper and classification logic verbatim.** Including `_parse_success` with its `echoed_promo` confidence guard — that's how we dodge the `subscriptionDiscount` contamination.
3. **Output shape:** each `validate()` call returns a dict with keys `{code, valid, applied_type, discount_pct, discount_raw, message, http_code, confidence}`. This is the shape the orchestrator consumes.
4. **Concurrency default = 4**, chunk size = 25, retry_attempts = 3, cascading_failure_threshold = 10 — same as sister constants.
5. **Optional proxy URL** from env `IHERB_PROXY_URL`. Default: no proxy.

- [ ] **Step 1: Write the failing tests**

Write `services/validator/tests/test_iherb_api_validator.py`:

```python
"""Unit tests for IHerbAPIValidator — all _curl calls are mocked."""
from unittest.mock import AsyncMock, patch

import pytest

from iherb_api_validator import (
    IHerbAPIValidator,
    CascadingFailure,
    ProxyQuotaExhausted,
)


@pytest.mark.asyncio
async def test_valid_code_type1_with_promo_echo():
    """200 + type=1 + promoCode echoes our code → valid, high confidence."""
    responses = [
        (200, {}),  # add_to_cart ok
        (200, {"appliedCouponCodeType": 1, "promoCode": "GOLD60",
               "couponDiscountPercent": 10}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("GOLD60")
    assert result["valid"] is True
    assert result["applied_type"] == 1
    assert result["discount_pct"] == 10
    assert result["confidence"] == "high"


@pytest.mark.asyncio
async def test_valid_code_type1_without_promo_echo_is_low_confidence():
    """200 + type=1 + missing promoCode → valid but low confidence."""
    responses = [
        (200, {}),
        (200, {"appliedCouponCodeType": 1, "promoCode": None}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("MYSTERY")
    assert result["valid"] is True
    assert result["confidence"] == "low"


@pytest.mark.asyncio
async def test_promo_echo_mismatch_is_rejected():
    """If iHerb echoes a *different* code than we sent, reject."""
    responses = [
        (200, {}),
        (200, {"appliedCouponCodeType": 1, "promoCode": "SOMETHING_ELSE"}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("GOLD60")
    assert result["valid"] is False
    assert "mismatch" in result["message"].lower()


@pytest.mark.asyncio
async def test_referral_type2_is_rejected():
    """200 + type=2 → referral code, rejected per OFR0296 policy."""
    responses = [
        (200, {}),
        (200, {"appliedCouponCodeType": 2, "promoCode": "RANDOM"}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("RANDOM")
    assert result["valid"] is False
    assert result["applied_type"] == 2
    assert "referral" in result["message"].lower()


@pytest.mark.asyncio
async def test_invalid_400_response():
    responses = [
        (200, {}),
        (400, {"message": "Invalid coupon code"}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("FAKEINVALID999")
    assert result["valid"] is False
    assert result["http_code"] == 400


@pytest.mark.asyncio
async def test_transient_5xx_retries_then_succeeds():
    """First apply attempt 503, second attempt 200/valid."""
    call_count = {"n": 0}

    async def side_effect(*args, **kwargs):
        call_count["n"] += 1
        url = args[3] if len(args) >= 4 else kwargs.get("url", "")
        if "lineItems" in url:
            return (200, {})
        if call_count["n"] <= 2:  # first applyCoupon round
            return (503, {})
        return (200, {"appliedCouponCodeType": 1, "promoCode": "GOLD60"})

    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=side_effect)):
        result = await v.validate("GOLD60")
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_proxy_402_raises_quota_exhausted():
    responses = [(402, {})]
    v = IHerbAPIValidator(proxy_url="http://dummy")
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        with pytest.raises(ProxyQuotaExhausted):
            await v.validate("GOLD60")


@pytest.mark.asyncio
async def test_cascading_failure_after_ten_consecutive_transients():
    """10 consecutive transient failures in validate_many → CascadingFailure."""
    v = IHerbAPIValidator()

    async def always_transient(*a, **kw):
        return (503, {})

    with patch.object(v, "_curl", AsyncMock(side_effect=always_transient)):
        with pytest.raises(CascadingFailure):
            await v.validate_many([f"CODE{i}" for i in range(20)], {})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
docker exec anyadeals-validator python -m pytest tests/test_iherb_api_validator.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'iherb_api_validator'`.

- [ ] **Step 3: Port the sister file as the starting point**

```bash
cp /home/skaiself/repo/anyadealsplus/playwright_worker/validators/iherb_api.py \
   /home/skaiself/repo/anyadeals/services/validator/iherb_api_validator.py
```

- [ ] **Step 4: Apply the adaptation edits**

In `services/validator/iherb_api_validator.py`:

1. **Remove the BaseValidator import line:**

```python
from playwright_worker.validators.base import BaseValidator
```

2. **Change the class declaration** from `class IHerbAPIValidator(BaseValidator):` to:

```python
class IHerbAPIValidator:
```

3. **Replace any method that calls `super().__init__` inside `__init__`** — remove that line; there's no base class now.

4. **Normalise the return dict** at the bottom of `validate()` so every success/failure path returns the same keys. Add a private helper at the top of the class:

```python
    @staticmethod
    def _format_result(
        code: str,
        valid: bool,
        applied_type: int = 0,
        discount_pct: float = 0.0,
        discount_raw: float = 0.0,
        message: str = "",
        http_code: int = 0,
        confidence: str = "high",
    ) -> dict:
        return {
            "code": code,
            "valid": valid,
            "applied_type": applied_type,
            "discount_pct": discount_pct,
            "discount_raw": discount_raw,
            "message": message,
            "http_code": http_code,
            "confidence": confidence,
        }
```

Update every `return {"valid": ...}` inside `validate()` and `_parse_success()` to go through `self._format_result(code, ...)`. Keep the existing classification logic (type=1 / type=2 / echoed_promo check) exactly as sister wrote it.

5. **Confidence flag** in `_parse_success`:
   - `applied_type == 1` AND `echoed_promo == code.upper()` → `confidence="high"`, `valid=True`.
   - `applied_type == 1` AND `echoed_promo` empty → `confidence="low"`, `valid=True`.
   - `applied_type == 1` AND `echoed_promo != code.upper()` → `valid=False`, `message="echoed promo mismatch: {echoed_promo}"`.
   - `applied_type == 2` → `valid=False`, `message="referral code (type=2)"`.

6. **`validate_many(codes, brand_notes_map)`**: accept a dict of `{code: notes}` for brand codes. If a code has a brand-only note, resolve a matching productId via a helper that calls `www.iherb.com/search?kw=<brand>` (HTTP GET + regex for `"productId":(\d+)`) and use that in place of `CART_PRODUCT` for that single call. Cache the resolution per brand in `self._brand_cache: dict[str, dict]`. If resolution fails, fall back to the default `CART_PRODUCT`. Bound concurrency via `asyncio.Semaphore(self.concurrency)`.

7. **Cascading-failure counter:** in `validate_many`, maintain a running count of consecutive transient errors; reset to 0 on any non-transient outcome; raise `CascadingFailure` if the count reaches `CASCADING_FAILURE_THRESHOLD = 10`.

8. **Constants at top of file** (keep sister's values):

```python
CART_PRODUCT = {"productId": 61864, "quantity": 20}
CHECKOUT_BASE = "https://checkout.iherb.com"
ADD_ITEM_URL = f"{CHECKOUT_BASE}/api/Carts/v3/catalog/lineItems"
APPLY_COUPON_URL = f"{CHECKOUT_BASE}/api/Carts/v2/applyCoupon"
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 1.5
DEFAULT_CHUNK_SIZE = 25
CASCADING_FAILURE_THRESHOLD = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
docker exec anyadeals-validator python -m pytest tests/test_iherb_api_validator.py -v
```

Expected: `8 passed`. If any fail, the sister port needs adjustment — do NOT stub out the confidence guard; that's the bug fix.

- [ ] **Step 6: Live smoke test against real iHerb**

```bash
docker exec anyadeals-validator python -c "
import asyncio
from iherb_api_validator import IHerbAPIValidator
v = IHerbAPIValidator()
for code in ['GOLD60', 'FAKEINVALID999', 'THANKYOU15']:
    r = asyncio.run(v.validate(code))
    print(code, '->', r['valid'], r.get('message',''), 'conf=', r.get('confidence'))
"
```

Expected:
- `GOLD60 -> True` with confidence `high` (known valid)
- `FAKEINVALID999 -> False` with HTTP 400 message
- `THANKYOU15 -> True` with confidence `high`

If the smoke test fails with connection errors, verify `curl` is available inside the container: `docker exec anyadeals-validator which curl`.

- [ ] **Step 7: Commit**

```bash
cd /home/skaiself/repo/anyadeals && \
git add services/validator/iherb_api_validator.py \
        services/validator/tests/test_iherb_api_validator.py && \
git commit -m "feat(validator): add HTTP API Stage 1 validator for iHerb codes"
```

---

## Task 4: Stage 2 — `iherb_region_validator.py`

**Files:**
- Create: `services/validator/iherb_region_validator.py`
- Create: `services/validator/tests/test_iherb_region_validator.py`
- Create: `services/validator/tests/fixtures/cart_with_autopromo_banner.html`
- Create: `services/validator/tests/fixtures/cart_ineligible_region.html`

This task introduces the regression guard for the DOM contamination bug. **The fixture test is the most important thing in this plan** — it ensures we don't rebuild the old bug.

- [ ] **Step 1: Create the contamination-banner fixture**

Write `services/validator/tests/fixtures/cart_with_autopromo_banner.html` (a trimmed real-world snapshot — this is the banner that used to poison the old validator):

```html
<!doctype html>
<html>
<head><title>Cart</title></head>
<body>
  <div class="promo-unlock-banner" data-testid="promo-unlock">
    Add $12.34 to your order to unlock 10% off with GOLD60
  </div>

  <section data-testid="applied-coupons">
    <div data-testid="applied-coupon-row" data-code="TESTCODE123">
      <span class="applied-coupon-code">TESTCODE123</span>
      <span class="applied-coupon-status">Applied</span>
    </div>
  </section>

  <div data-testid="cart-summary">
    <span>Subtotal: $111.40</span>
    <span>Discount: -$11.14</span>
  </div>
</body>
</html>
```

- [ ] **Step 2: Create the ineligible-region fixture**

Write `services/validator/tests/fixtures/cart_ineligible_region.html`:

```html
<!doctype html>
<html>
<head><title>Cart</title></head>
<body>
  <div class="promo-unlock-banner" data-testid="promo-unlock">
    Add $12.34 to your order to unlock 10% off with GOLD60
  </div>

  <section data-testid="applied-coupons">
    <div data-testid="applied-coupon-row" data-code="EU15N">
      <span class="applied-coupon-code">EU15N</span>
      <span class="applied-coupon-status">Not applied: shipping destination is not eligible for this promotion</span>
    </div>
  </section>
</body>
</html>
```

- [ ] **Step 3: Write the failing tests**

Write `services/validator/tests/test_iherb_region_validator.py`:

```python
"""Unit tests for the Stage-2 Playwright region validator.

The parse_cart_html function is pure — it takes an HTML string and the code
under test, and returns (eligible: bool, reason: str). We test it against
fixtures, with no browser involved.
"""
from pathlib import Path

from iherb_region_validator import parse_cart_html, REGION_SCCODES

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_autopromo_banner_does_not_contaminate_eligibility():
    """REGRESSION: the auto-promo banner must NOT be read as the code's result."""
    html = _load("cart_with_autopromo_banner.html")
    # Code being tested is TESTCODE123, not GOLD60 (banner mentions GOLD60).
    eligible, reason = parse_cart_html(html, "TESTCODE123")
    assert eligible is True
    assert "GOLD60" not in reason


def test_ineligible_region_html_is_detected():
    html = _load("cart_ineligible_region.html")
    eligible, reason = parse_cart_html(html, "EU15N")
    assert eligible is False
    assert "not eligible" in reason.lower() or "ineligible" in reason.lower()


def test_parse_cart_html_returns_false_when_applied_row_missing():
    html = "<html><body><div>cart is empty</div></body></html>"
    eligible, reason = parse_cart_html(html, "GOLD60")
    assert eligible is False
    assert "no applied" in reason.lower() or "not found" in reason.lower()


def test_region_sccodes_covers_all_21_regions():
    expected = {"us", "kr", "jp", "de", "gb", "au", "sa", "ca", "cn", "rs", "hr",
                "it", "fr", "at", "nl", "se", "ch", "ie", "tw", "in", "hk"}
    assert expected.issubset(set(REGION_SCCODES.keys()))


def test_region_sccodes_values_are_uppercase_two_letter():
    for r, sc in REGION_SCCODES.items():
        assert len(sc) == 2 and sc.isupper(), f"{r} → {sc}"
```

- [ ] **Step 4: Run the test to verify it fails**

```bash
docker exec anyadeals-validator python -m pytest tests/test_iherb_region_validator.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'iherb_region_validator'`.

- [ ] **Step 5: Implement `iherb_region_validator.py`**

Write `services/validator/iherb_region_validator.py`:

```python
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
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
docker exec anyadeals-validator python -m pytest tests/test_iherb_region_validator.py -v
```

Expected: `5 passed`. The contamination-banner regression test is the load-bearing one. If it fails, DO NOT proceed — the parser is still contaminated.

- [ ] **Step 7: Commit**

```bash
cd /home/skaiself/repo/anyadeals && \
git add services/validator/iherb_region_validator.py \
        services/validator/tests/test_iherb_region_validator.py \
        services/validator/tests/fixtures/cart_with_autopromo_banner.html \
        services/validator/tests/fixtures/cart_ineligible_region.html && \
git commit -m "feat(validator): add Stage 2 Playwright region validator with contamination-regression fixture"
```

---

## Task 5: Gut `browser_validator.py`, wire orchestrator into `server.py`

**Files:**
- Modify: `services/validator/browser_validator.py`
- Modify: `services/validator/server.py`

The old `browser_validator.py` is the DOM-reading script invoked as a subprocess from `server.py`. We replace its core with the two-stage orchestrator and make `server.py` call the orchestrator directly (no subprocess).

- [ ] **Step 1: Shrink `browser_validator.py` to an orchestrator**

Replace `services/validator/browser_validator.py` with:

```python
"""Two-stage iHerb validator orchestrator.

Stage 1: iherb_api_validator.IHerbAPIValidator (HTTP, ~3s/code)
Stage 2: iherb_region_validator.IHerbRegionValidator (Playwright, only survivors)

The DOM-reading validator that lived here previously was removed — see
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
    so browser_validate.merge_browser_results consumes it unchanged:

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

    logger.info("Stage 1 complete: %d/%d recognised", sum(1 for r in stage1 if r["valid"]), len(stage1))

    survivors = [r["code"] for r in stage1 if r["valid"]]
    stage2: dict[str, list[str]] = {}
    if survivors:
        logger.info("Stage 2: checking %d survivors × %d regions", len(survivors), len(regions))
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
        results = {r: {"valid": True, "discount": discount, "min_cart_value": ""} for r in active_regions}
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
```

- [ ] **Step 2: Replace `server._run_browser_validator` with a direct call**

In `services/validator/server.py`:

1. **Delete** the `_run_browser_validator` function entirely (it spawned `browser_validator.py` as a subprocess).
2. **Add** at the top of the file, next to the existing imports:

```python
from browser_validator import validate_codes, ALL_REGIONS
```

(Remove the old `ALL_REGIONS = [...]` hardcoded list in server.py — use the import.)

3. **Update the `/run` handler** to call `validate_codes` directly. Replace the two-phase `_run_browser_validator` US-then-regions flow with a single call:

```python
        logger.info(
            "Two-stage validation: %d pending + %d active = %d unique codes, regions=%s, brand_codes=%d",
            len(pending_codes), len(active_codes), len(all_codes), requested_regions, len(brand_notes),
        )

        full_results = await validate_codes(all_codes, brand_notes, requested_regions)
```

(The downstream `merge_browser_results(existing, full_results, research_notes)` call stays identical.)

4. **Add a `/rescue` endpoint** below `/run`:

```python
@app.post("/rescue")
async def rescue_invalid():
    """One-shot backfill: re-validate every row currently marked `invalid`.

    See services/validator/rescue_backfill.py for the script entry point.
    """
    import rescue_backfill
    summary = await rescue_backfill.run()
    return {"status": "ok", "summary": summary}
```

- [ ] **Step 3: Run all existing validator tests**

```bash
docker exec anyadeals-validator python -m pytest tests/ -v
```

Expected: all previously-green tests still pass, plus the new Task 3 and Task 4 tests. If `tests/test_browser.py` asserts on the old DOM parser, delete those test cases (the parser they cover no longer exists) and commit that deletion in the same step.

- [ ] **Step 4: Live smoke test — one real code through the orchestrator**

```bash
docker exec anyadeals-validator python -c "
import asyncio
from browser_validator import validate_codes
print(asyncio.run(validate_codes(['GOLD60'], regions=['us'])))
"
```

Expected: a single dict where `results['us']['valid'] == True` and `discount` is populated.

- [ ] **Step 5: Rebuild the container and hit the HTTP endpoint**

```bash
cd /home/skaiself/repo/anyadeals && \
docker compose build validator && \
docker compose up -d validator && \
sleep 3 && \
curl -fsS -X POST 'http://localhost:8080/trigger/validate?regions=us' | head -40
```

Expected: HTTP 200, `status: success` or `no codes to validate`. Check logs:

```bash
docker logs anyadeals-validator --tail 30
```

Expected to see `Stage 1 complete:` log lines from the orchestrator, no `[browser]` subprocess lines.

- [ ] **Step 6: Commit**

```bash
cd /home/skaiself/repo/anyadeals && \
git add services/validator/browser_validator.py services/validator/server.py && \
git commit -m "refactor(validator): replace DOM path with two-stage HTTP+Playwright orchestrator"
```

---

## Task 6: `rescue_backfill.py` one-shot script

**Files:**
- Create: `services/validator/rescue_backfill.py`
- Create: `services/validator/tests/test_rescue_backfill.py`

- [ ] **Step 1: Write the failing test**

Write `services/validator/tests/test_rescue_backfill.py`:

```python
"""Tests for the rescue_backfill one-shot script."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import rescue_backfill


def _write_coupons(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "coupons.json"
    p.write_text(json.dumps(rows))
    return p


@pytest.mark.asyncio
async def test_rescue_rescues_newly_valid_codes(tmp_path, monkeypatch):
    coupons_path = _write_coupons(tmp_path, [
        {"code": "RESCUED1", "status": "invalid", "regions": [], "fail_count": 5,
         "notes": "", "source": "browser_validation", "discount": ""},
        {"code": "STILLBAD", "status": "invalid", "regions": [], "fail_count": 5,
         "notes": "", "source": "browser_validation", "discount": ""},
        {"code": "GOLD60", "status": "valid", "regions": ["us"], "fail_count": 0,
         "notes": "Min. order $60.", "source": "browser_validation", "discount": "10% off"},
    ])
    monkeypatch.setattr(rescue_backfill, "DATA_DIR", str(tmp_path))

    async def fake_validate_codes(codes, brand_notes_map=None, regions=None):
        assert set(codes) == {"RESCUED1", "STILLBAD"}
        return [
            {"code": "RESCUED1",
             "results": {"us": {"valid": True, "discount": "10% off", "min_cart_value": ""}}},
            {"code": "STILLBAD",
             "results": {"us": {"valid": False, "message": "Invalid code"}}},
        ]

    with patch.object(rescue_backfill, "validate_codes", side_effect=fake_validate_codes):
        summary = await rescue_backfill.run()

    rows = json.loads(coupons_path.read_text())
    by_code = {r["code"]: r for r in rows}

    assert by_code["RESCUED1"]["status"] in ("valid", "region_limited")
    assert by_code["RESCUED1"]["fail_count"] == 0
    assert by_code["RESCUED1"]["rescued_at"]
    assert by_code["STILLBAD"]["status"] == "invalid"
    assert by_code["GOLD60"]["status"] == "valid"  # untouched
    assert summary["rescued"] == 1
    assert summary["still_invalid"] == 1


@pytest.mark.asyncio
async def test_rescue_dry_run_does_not_mutate(tmp_path, monkeypatch):
    coupons_path = _write_coupons(tmp_path, [
        {"code": "RESCUED1", "status": "invalid", "regions": [], "fail_count": 5,
         "notes": "", "source": "browser_validation", "discount": ""},
    ])
    monkeypatch.setattr(rescue_backfill, "DATA_DIR", str(tmp_path))

    async def fake(*a, **kw):
        return [{"code": "RESCUED1",
                 "results": {"us": {"valid": True, "discount": "10% off", "min_cart_value": ""}}}]

    with patch.object(rescue_backfill, "validate_codes", side_effect=fake):
        summary = await rescue_backfill.run(dry_run=True)

    rows = json.loads(coupons_path.read_text())
    assert rows[0]["status"] == "invalid"  # unchanged
    preview = tmp_path / "coupons.rescue_preview.json"
    assert preview.exists()
    assert summary["dry_run"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
docker exec anyadeals-validator python -m pytest tests/test_rescue_backfill.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rescue_backfill'`.

- [ ] **Step 3: Implement `rescue_backfill.py`**

Write `services/validator/rescue_backfill.py`:

```python
"""One-shot backfill that re-validates every row currently marked `invalid`
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

    results = await validate_codes(invalid_codes, brand_notes)

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
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
docker exec anyadeals-validator python -m pytest tests/test_rescue_backfill.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Full validator test suite — green?**

```bash
docker exec anyadeals-validator python -m pytest tests/ -v
```

Expected: everything green. If anything is red, stop and investigate — do not move on.

- [ ] **Step 6: Commit**

```bash
cd /home/skaiself/repo/anyadeals && \
git add services/validator/rescue_backfill.py \
        services/validator/tests/test_rescue_backfill.py && \
git commit -m "feat(validator): add rescue_backfill one-shot for false-invalidated codes"
```

---

## Task 7: Run the rescue and verify outcome

**Files:**
- Mutates: `site/data/coupons.json`

This is the payoff task. No code changes — we run the backfill, inspect, and decide whether to commit the data change.

- [ ] **Step 1: Baseline snapshot**

```bash
python3 -c "
import json, collections
c = json.load(open('/home/skaiself/repo/anyadeals/site/data/coupons.json'))
rows = c if isinstance(c, list) else c.get('coupons', [])
print('before:', collections.Counter(r['status'] for r in rows))
print('active:', sum(1 for r in rows if r['status'] in ('valid','region_limited')))
"
```

Expected (matching today's state): `active: 5`.

- [ ] **Step 2: Dry-run the rescue**

```bash
docker exec anyadeals-validator python rescue_backfill.py --dry-run
```

Expected: JSON summary with `"rescued": N` where `N ≥ 10`.

- [ ] **Step 3: Inspect the dry-run preview**

```bash
python3 -c "
import json, collections
p = '/home/skaiself/repo/anyadeals/site/data/coupons.rescue_preview.json'
c = json.load(open(p))
rows = c if isinstance(c, list) else c.get('coupons', [])
print('after(preview):', collections.Counter(r['status'] for r in rows))
newly = [r for r in rows if r.get('rescued_at')]
print('newly rescued:', len(newly))
for r in newly[:20]: print(' -', r['code'], r['status'], r.get('regions', []))
"
```

Eyeball the rescued codes. If any look like junk (random 4-letter tokens with no context), stop and investigate `code_filter`. If they look like real codes (GOLD*, *15, *20, region-specific names), continue.

- [ ] **Step 4: Run for real**

```bash
docker exec anyadeals-validator python rescue_backfill.py
```

- [ ] **Step 5: Verify the new count meets the success criterion**

```bash
python3 -c "
import json
c = json.load(open('/home/skaiself/repo/anyadeals/site/data/coupons.json'))
rows = c if isinstance(c, list) else c.get('coupons', [])
active = [r for r in rows if r['status'] in ('valid','region_limited')]
print('active:', len(active))
for r in active: print(' -', r['code'], r['status'], r.get('regions', []))
assert len(active) >= 15, f'Target not met: {len(active)} < 15'
print('SUCCESS: target met')
"
```

Expected: ≥15 active codes. If the count is still low, diagnose before committing:

- Are rescued rows annotated with `rescued_at`? → rescue ran.
- Is stage 2 eliminating everything? → run `docker logs anyadeals-validator --tail 80` and check for "not eligible" storms.
- Is stage 1 rejecting with `echoed_promo mismatch`? → inspect 2–3 codes manually via the Step 6 smoke test from Task 3.

- [ ] **Step 6: Clean up the dry-run preview file**

```bash
rm /home/skaiself/repo/anyadeals/site/data/coupons.rescue_preview.json
```

- [ ] **Step 7: Commit the data change**

```bash
cd /home/skaiself/repo/anyadeals && \
git add site/data/coupons.json && \
git commit -m "chore(data): rescue false-invalidated iHerb codes via two-stage validator"
```

Don't push manually — the existing orchestrator git push flow will pick it up on the next scheduled tick, or you can trigger it with `curl -X POST http://localhost:8080/trigger/push` if that endpoint is enabled.

- [ ] **Step 8: Next-day verification**

Tomorrow after the nightly `01:00–02:00 UTC` scrape + `02:30–03:30 UTC` AI parse + `04:00–07:00 UTC` validate cycle, rerun Step 5. Active count should remain ≥15. If it drops, the orchestrator's regular validation run is re-invalidating the rescued codes — check logs for `echoed_promo mismatch` or stage-2 errors and iterate.

---

## Notes on things NOT to do

- Do **not** delete `browser_validate.py` — its `merge_browser_results` is reused by the new orchestrator.
- Do **not** delete `gutschein_scraper.py` — the gutschein scraping path is independent and still needs Playwright.
- Do **not** delete `claude_parser.py` — AI enrichment still produces `notes`, `discount`, `min_order` which feed the brand-code detection.
- Do **not** drop any of the 21 regions from `ALL_REGIONS` without updating the frontend's region filter — they're cross-referenced.
- Do **not** bypass the contamination fixture test. If it's flaky, make it less flaky; do NOT weaken the assertion. The bug it catches is exactly what this whole plan exists to fix.
