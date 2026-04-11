# iHerb Validator Rescue — Design Spec

**Date:** 2026-04-11
**Topic:** Replace DOM-reading Playwright validator with HTTP-API-first two-stage validator; rescue false-invalidated codes; centralise code-filter heuristics.
**Reference implementation:** sister project `anyadealsplus` (`playwright_worker/validators/iherb_api.py`, `worker/parsers/code_parser.py`, `docs/iherb-validation.md`).

## 1. Problem

Current validator (`services/validator/browser_validator.py`) uses Playwright to load `checkout.iherb.com/cart`, apply each code, and read the page DOM for the result. It has two concrete problems:

1. **DOM contamination false-invalidates real codes.** `checkout.iherb.com/cart` shows an auto-promo banner like *"Add $X to unlock 10% off with GOLD60"*. The DOM parser sometimes reads this banner instead of the result of the code under test, reporting the same message for every code. Current active set is **5** codes; sister project using HTTP API gets **18**. Overlap with sister is only 2 codes (GOLD60, THANKYOU15), strongly suggesting the other 13 are sitting in our "invalid" pile.
2. **Slow.** ~30–90s per code per region × 21 regions × N codes. Bounded by this, we can't afford to retest "invalid" codes often, so false invalidations stick.

## 2. Goal

- Match or exceed sister project's 18 active codes.
- Cut per-code validation time by ~10–20×.
- Fix the DOM contamination bug at the root (stop reading DOM for recognition).
- Preserve per-region `region_limited` granularity (the site's region filter depends on it).
- Preserve brand-code detection (notes-driven auto-add-to-cart for brand-only codes).

## 3. Non-goals

- No change to storage format (`site/data/coupons.json` stays). No SQLite migration.
- No change to scheduler, orchestrator, poster, or frontend.
- No change to `claude_parser.py` AI enrichment — keeps producing `discount`, `notes`, `min_order`.
- No new containers. All new code runs inside the existing `validator` service.

## 4. Architecture

Two-stage validator, both stages inside the existing `validator` container:

```
┌──────────────────────────── validator (:8002) ────────────────────────────┐
│                                                                            │
│  Stage 1 — iherb_api_validator.py  (HTTP, curl-based, ~3s/code)           │
│    ├─ POST /api/Carts/v3/catalog/lineItems  (seed cart)                   │
│    ├─ POST /api/Carts/v2/applyCoupon        (test code)                    │
│    └─ Classify: valid | invalid | referral(type=2) | transient            │
│                                                                            │
│           │  only codes classified `valid` continue                        │
│           ▼                                                                │
│  Stage 2 — iherb_region_validator.py  (Playwright, HTML scan)              │
│    ├─ For each surviving code × each region:                               │
│    │    • set `sccode` cookie                                              │
│    │    • load /cart with code pre-applied                                 │
│    │    • scan HTML for eligibility text                                   │
│    └─ Emit region list → coupons.json                                      │
│                                                                            │
│  Brand-code helper (unchanged): if notes say "X brand only", stage 1 also  │
│  seeds cart with a matching product via www.iherb.com/search.              │
└────────────────────────────────────────────────────────────────────────────┘
```

**Why two-stage:** sister's docs verify that the `applyCoupon` endpoint is region-blind — same JSON response regardless of `sccode`. Region eligibility only exists in the rendered `/cart` HTML. So stage 1 (HTTP) is enough for `valid`/`invalid`, and stage 2 (HTML scan) is only paid for the small surviving set. With ~18 valid codes × 21 regions, stage 2 is ~378 page loads vs today's ~7000 and only runs after the cheap stage-1 filter.

## 5. Components

### 5.1 `services/validator/iherb_api_validator.py` (new)

Ported from sister `playwright_worker/validators/iherb_api.py`. Public surface:

```python
class IHerbAPIValidator:
    def __init__(self, user_agent: str = ..., cart_product: dict = CART_PRODUCT):
        ...

    async def validate(self, code: str, brand_notes: str | None = None) -> APIResult:
        """Returns APIResult(status, applied_type, discount_pct, message, http_code)."""

    async def validate_many(self, codes: list[str], brand_notes_map: dict) -> list[APIResult]:
        """Runs validate() in bounded concurrency (default 4), reuses one cart jar per code."""
```

Constants (match sister):
- `CART_PRODUCT = {"productId": 61864, "quantity": 20}` (Vitamin C 500mg × 20 ≈ $111, clears $60 minimums)
- `CHECKOUT_BASE = "https://checkout.iherb.com"`
- `ADD_ITEM_URL = f"{CHECKOUT_BASE}/api/Carts/v3/catalog/lineItems"`
- `APPLY_COUPON_URL = f"{CHECKOUT_BASE}/api/Carts/v2/applyCoupon"`

Classification rules (also from sister docs):
- **HTTP 200 + `appliedCouponCodeType: 1`** → `valid`, extract `couponDiscountPercent` / `totalDiscountRawAmount`.
- **HTTP 200 + `appliedCouponCodeType: 2`** → `referral`, reject (per existing OFR0296 policy).
- **HTTP 400** with rejection message → `invalid` (permanent).
- **HTTP 402 on CONNECT / 5xx / connection error** → `transient`, retryable with exponential backoff (max 3).
- **Cascading failure:** 10 consecutive transient → abort the run.
- **Chunk size:** 25 results before intermediate persist.

Brand-code support: if `brand_notes` matches the pattern "X brand only", the cart-seed step first searches `www.iherb.com/search?kw=X`, picks the first productId, seeds that instead of the default. Same cache lookup the existing `browser_validator._brand_code_cache` uses.

### 5.2 `services/validator/iherb_region_validator.py` (new)

Lightweight Playwright path. Inputs: a list of codes already known to be recognised by iHerb; outputs a `{code: [region, …]}` map.

For each `(code, region)`:
1. New browser context per region (cookies isolated).
2. Set `iher-pref1` cookie with the appropriate `sccode` value (existing region map already defines this).
3. Navigate to `checkout.iherb.com/cart?appliedCoupon={code}`.
4. Wait for cart React app to hydrate (`networkidle`, max 10s).
5. Scan HTML (not the auto-promo banner element) for the eligibility string. Specifically, query the `data-testid` nodes around the applied coupon row; explicitly skip the `[class*=promo-unlock]` banner that contaminated the old validator.
6. Classify region as `eligible` or `not-eligible`.

Concurrency: 4 contexts in parallel, 30–120s random jitter between requests (polite-scraping rule from CLAUDE.md).

**Contamination guard:** a unit test that mounts a saved HTML fixture containing the auto-promo banner and asserts the parser does NOT pick it up. This is the regression gate for the bug.

### 5.3 `services/researcher/parsers/code_filter.py` (new)

Centralises false-positive and referral-phrase filters that are currently inlined across scrapers.

```python
FALSE_POSITIVES: frozenset[str] = frozenset({
    "HTTP", "HTML", "HEAD", "BODY", "META", "LINK", "NONE",
    "TRUE", "FALSE", "NULL", "JSON", "SELF", "POST", "NSFW",
    "REDDIT", "SUBREDDIT", "COMMENT", "HTTPS", "HREF", "TITLE",
    "IHERB", "HERB", "VITAMIN", "PROMO", "CODE", "COUPON",
    "EDIT", "UPDATE", "DELETED", "REMOVED", "TLDR", "NBSP",
    "IMGUR", "JPEG", "WEBP",
})

REFERRAL_PHRASES: tuple[str, ...] = (
    "my code", "use my", "my referral", "my link",
    "my iherb code", "new customer discount with", "first order with code",
)

def is_false_positive(code: str) -> bool: ...
def looks_like_referral(context: str) -> bool: ...
def filter_results(results: list[dict]) -> list[dict]:
    """Drop results whose code is a false positive or whose raw_context triggers a referral phrase."""
```

Every scraper in `services/researcher/sources/` calls `filter_results()` before returning. Inlined `FALSE_POSITIVES` sets are removed from `reddit.py`, `couponfollow.py`, `generic.py`.

This is parse-time defence-in-depth on top of the existing `claude_parser.py` check. AI parser stays untouched — it still does discount/notes/min-order enrichment and the owner-referral (`OFR0296`) competition check.

### 5.4 `services/validator/browser_validator.py` (modified)

Becomes a thin orchestrator:

```python
async def validate_all(codes, brand_notes_map):
    api = IHerbAPIValidator()
    api_results = await api.validate_many(codes, brand_notes_map)

    surviving = [r.code for r in api_results if r.status == "valid"]
    if surviving:
        region_results = await IHerbRegionValidator().validate(surviving)
    else:
        region_results = {}

    return merge(api_results, region_results)
```

The old DOM-reading code path (`parse_promo_message`, page-reload loop, etc.) is deleted. Any helpers still needed (e.g. `_ensure_cart_has_product`) move into `iherb_api_validator.py`.

### 5.5 `services/validator/rescue_backfill.py` (new, one-shot)

A CLI script that:
1. Reads `site/data/coupons.json`.
2. Selects all rows with `status == "invalid"` (currently 320).
3. Runs them through `IHerbAPIValidator`.
4. For any that now classify `valid`: resets `status`, `fail_count=0`, writes a `rescued_at` timestamp, then queues them for stage 2 region testing.
5. Writes back `coupons.json` using the existing merge helper so format/ordering is preserved.

Invoked once, manually:

```bash
docker exec anyadeals-validator python rescue_backfill.py
```

Not scheduled. After the one-shot rescue, the regular nightly validator handles ongoing rechecks.

### 5.6 `services/validator/server.py` (modified)

`/run` endpoint now calls the two-stage orchestrator. `/scrape-gutschein` is untouched (gutschein scraper still uses Playwright via its own path). Adds a new `/rescue` endpoint that invokes `rescue_backfill.py` for manual re-runs.

## 6. Data flow

```
coupons.json
    │
    ▼
load rows where status ∈ {pending, invalid (rescue), valid, region_limited}
    │
    ▼
Stage 1: IHerbAPIValidator.validate_many()
    │  (parallelism=4, chunk=25, retries=3, cascading-abort=10)
    │
    ├─ valid   ──► Stage 2
    ├─ referral──► drop (policy)
    ├─ invalid ──► status=invalid, fail_count+=1
    └─ transient──► status unchanged, try next run
    │
    ▼
Stage 2: IHerbRegionValidator.validate()
    │  (21 regions × surviving codes, bounded concurrency)
    │
    ▼
merge into coupons.json
    │  (status: valid if all regions eligible, region_limited otherwise)
    ▼
orchestrator.git_push (existing)
```

## 7. Error handling

- **Transient failures:** exponential backoff, max 3 retries per code.
- **Cascading failure detection:** 10 consecutive transients → abort run, mark remaining codes unchanged, log + expose in `dashboard.json`.
- **Cart product unavailable:** a health check at the start of every run adds the cart product and verifies HTTP 200; if it fails, abort with `cart_health_failed` status so we don't burn a run on a broken fixture.
- **Chunked persist:** every 25 results, merge into `coupons.json` and fsync so a mid-run crash doesn't lose everything.
- **Dry-run mode:** `--dry-run` CLI flag on `rescue_backfill.py` writes to `coupons.rescue_preview.json` instead of mutating production state.

## 8. Testing

New tests under `services/validator/tests/`:

- `test_iherb_api_validator.py`
  - Valid response (200, type=1): parses discount correctly.
  - Referral response (200, type=2): returns `referral`, discards.
  - Invalid response (400 + rejection payload): returns `invalid`.
  - Transient (5xx) triggers retry, succeeds on second attempt.
  - 10 consecutive transients aborts run.
- `test_iherb_region_validator.py`
  - **Regression fixture:** saved HTML snippet containing auto-promo banner + applied coupon row. Parser must pick the applied row, not the banner.
  - `not-eligible` banner → region excluded.
  - Cookie is set before navigation.
- `test_code_filter.py`
  - `FALSE_POSITIVES` membership.
  - `looks_like_referral` true/false cases.
  - `filter_results` drops correctly without mutating surviving rows.
- `test_rescue_backfill.py`
  - Given a synthetic coupons.json with 5 invalid rows, 3 of which mock-validate as valid: asserts `status=valid`, `fail_count=0`, `rescued_at` set.

Sister project has 252 tests; we add ~15. Runs in the existing `pytest` harness inside the validator container.

## 9. Rollout

1. Merge code behind no flag; new code paths are dormant until `/rescue` is hit or the next scheduled `/run`.
2. Run `rescue_backfill.py` once manually, inspect diff before git-pushing the updated `coupons.json`.
3. Let the nightly pipeline pick it up. Compare next-day active count against sister's DB. Target: ≥15 active codes.
4. If numbers match, delete the old DOM-reading helpers (nothing references them after step 1).

## 10. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| iHerb changes `applyCoupon` response shape | low | Snapshot test of response JSON; alert if schema drift. |
| Cart product 61864 goes OOS | medium | Pre-run health check; fall back to a second product ID from a small whitelist. |
| Sister's HTTP approach gets bot-blocked under our load | low | Start conservative: concurrency=4, backoff jitter; sister runs similar cadence without issues. |
| Stage-2 region scan still contaminated by banner | medium | HTML-fixture regression test is the gate; if the test can't be made reliable, fall back to marking everything `valid` globally (B1 tradeoff). |
| Rescue backfill re-validates referral codes that compete with OFR0296 | low | Filter applies first; stage 1 rejects type=2. |

## 11. Key files touched

| File | Change |
|---|---|
| `services/validator/iherb_api_validator.py` | **new** |
| `services/validator/iherb_region_validator.py` | **new** |
| `services/validator/rescue_backfill.py` | **new** |
| `services/validator/browser_validator.py` | gut old DOM path, become orchestrator |
| `services/validator/server.py` | swap `/run` wiring, add `/rescue` |
| `services/validator/tests/test_iherb_api_validator.py` | **new** |
| `services/validator/tests/test_iherb_region_validator.py` | **new** |
| `services/validator/tests/test_rescue_backfill.py` | **new** |
| `services/researcher/parsers/__init__.py` | **new** |
| `services/researcher/parsers/code_filter.py` | **new** |
| `services/researcher/sources/reddit.py` | call `filter_results`, drop inlined FP set |
| `services/researcher/sources/couponfollow.py` | call `filter_results`, drop inlined FP set |
| `services/researcher/sources/generic.py` | call `filter_results` |
| `services/researcher/tests/test_code_filter.py` | **new** |

## 12. Success criteria

- Active coupon count (`valid` + `region_limited`) rises from 5 → ≥15 after first rescue run.
- Median per-code validation time drops from ~30s to ≤5s (stage 1) plus ≤2s × surviving-region combos.
- Auto-promo banner regression test passes.
- No referral codes of type=2 appear in `coupons.json`.
- `OFR0296` owner-referral remains untouched.
