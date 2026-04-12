"""HTTP API-based iHerb validator hitting checkout.iherb.com directly.

Stage 1 of the two-stage validator rescue. Ported from the sister project
(anyadealsplus/playwright_worker/validators/iherb_api.py). Much faster than
the Playwright-based validator (sub-second per code vs 30-90s) and avoids
the DOM/banner contamination bug that false-invalidates real codes.

Uses ``curl`` via subprocess for reliable session/cookie handling. iHerb's
checkout API (``checkout.iherb.com``) has no bot protection — it can be
called directly from any IP. The marketing site (``www.iherb.com``) is
behind Akamai/Cloudflare and will 403 datacenter IPs; we only ever hit
the checkout host here.

Optionally accepts an ``IHERB_PROXY_URL`` env var (e.g. IPRoyal Web
Unblocker) for region-specific testing, but the proxy is NOT required.

The CRITICAL detail ported verbatim from the sister project is the
``_parse_success`` confidence guard. iHerb returns a ``subscriptionDiscount``
field that carries the auto-promo banner ("10% off your first order with
GOLD60") which is shown to every unauthenticated session regardless of which
coupon was applied. Reading that field as a discount caused every API-
accepted code to be reported as "10% off" — even referral codes and codes
that didn't actually discount anything. We never read ``subscriptionDiscount``
as a discount source.

We also use ``promoCode`` echo as a confidence guard: when iHerb echoes the
exact code we sent, we're confident; when it echoes a *different* code, iHerb
resolved our input to something else entirely and we reject; when no echo is
present, we still call it valid but flag low confidence.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


class ProxyQuotaExhausted(Exception):
    """Raised when the proxy returns HTTP 402 (out of credits)."""


class CascadingFailure(Exception):
    """Raised when too many consecutive codes fail with transient errors,
    indicating the proxy or upstream is broken."""


# A consistent product to add to cart for testing.
# Vitamin C 500mg, ~$5.57 each × 20 = ~$111 (above $60 minimum for codes
# like GOLD60).
CART_PRODUCT = {"productId": 61864, "quantity": 20}

CHECKOUT_BASE = "https://checkout.iherb.com"
ADD_ITEM_URL = f"{CHECKOUT_BASE}/api/Carts/v3/catalog/lineItems"
APPLY_COUPON_URL = f"{CHECKOUT_BASE}/api/Carts/v2/applyCoupon"

SEARCH_URL_TMPL = "https://www.iherb.com/search?kw={brand}"
BRAND_ONLY_NOTE_RE = re.compile(r"^\s*(.+?)\s+brand only\.?\s*$", re.IGNORECASE)
PRODUCT_ID_RE = re.compile(r'"productId"\s*:\s*(\d+)')

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)

# Retry transient failures (proxy hiccups, connection drops, 5xx responses)
# up to this many times. Each retry uses exponential backoff.
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 1.5  # seconds; doubles per attempt

# How many concurrent validations are allowed inside validate_many.
DEFAULT_CONCURRENCY = 4

# How many results to accumulate before handing a chunk back to a caller.
DEFAULT_CHUNK_SIZE = 25

# Stop the entire run if this many consecutive codes fail with transient
# errors. Indicates the proxy is broken / quota exhausted / iHerb is down —
# no point burning credits on the rest.
CASCADING_FAILURE_THRESHOLD = 10


def is_available() -> bool:
    """Stage 1 is always available — no proxy required."""
    return True


class IHerbAPIValidator:
    """Validates iHerb codes via direct API calls to checkout.iherb.com.

    Stage 1 of the two-stage validator. Emits recognition-only signals:
    it confirms iHerb knows the code (or doesn't), but cannot speak to
    per-region eligibility — its single direct connection always lands on
    the US storefront. Stage 2 (the Playwright region validator) is
    responsible for per-region classification.

    Args:
        proxy_url: Optional. If None, reads from ``IHERB_PROXY_URL`` env var.
            An empty string disables the proxy entirely (direct connection).
        concurrency: Maximum concurrent ``validate()`` calls inside
            ``validate_many``. Defaults to 4.
        pace_seconds: Optional delay after each completed code inside
            ``validate_many``. With ``concurrency=1`` this produces strict
            serial pacing that defeats Cloudflare's per-IP rate limit on
            ``checkout.iherb.com`` — tested at 15s/code against proxy-local
            with 15/15 success. Ignored when ``concurrency > 1``.
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        pace_seconds: float = 0.0,
    ) -> None:
        if proxy_url is None:
            proxy_url = os.environ.get("IHERB_PROXY_URL", "")
        self.proxy_url = proxy_url  # may be empty string — direct connection
        self.concurrency = concurrency
        self.pace_seconds = pace_seconds
        # Cache of brand-name → resolved CART_PRODUCT override for brand-only
        # codes. Populated lazily inside validate_many.
        self._brand_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Result shape helper
    # ------------------------------------------------------------------
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
        """Normalise the flat result dict that the orchestrator consumes.

        Every key is always present so downstream code doesn't need to
        do defensive ``.get()`` calls.
        """
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

    # ------------------------------------------------------------------
    # curl subprocess wrapper
    # ------------------------------------------------------------------
    async def _curl(
        self,
        cookie_file: str,
        method: str,
        data: dict | None,
        url: str,
        timeout: int = 60,
    ) -> tuple[int, Any]:
        """Run a curl request with cookie persistence, optionally through
        a proxy.

        Returns (status_code, parsed_body). Body is parsed as JSON when
        possible, else returned as a string.

        When ``self.proxy_url`` is empty, curl connects directly. When set,
        the proxy is used. Special case: if the proxy itself responds with
        HTTP 402 to the CONNECT tunnel (IPRoyal Web Unblocker out-of-credits
        signal), curl exits with status 0 because no tunnel was established.
        We detect this by parsing curl's verbose stderr for the
        ``< HTTP/1.1 402`` line and surface 402.
        """
        cmd = [
            "curl", "-k", "-sv", "--max-time", str(timeout),
        ]
        if self.proxy_url:
            cmd.extend(["-x", self.proxy_url])
        cmd.extend([
            "-b", cookie_file,
            "-c", cookie_file,
            "-L",
            "-A", USER_AGENT,
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json",
            "-w", "\n%{http_code}",
        ])
        if method == "POST" and data is not None:
            cmd.extend(["-X", "POST", "-d", json.dumps(data)])
        elif method != "GET":
            cmd.extend(["-X", method])
        cmd.append(url)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace")

        # Last line is the HTTP status code (from -w)
        lines = output.rsplit("\n", 1)
        body = lines[0] if len(lines) > 1 else ""
        status_code = int(lines[-1]) if lines[-1].isdigit() else 0

        # Detect proxy-level 402 from curl's verbose stderr.
        # Curl reports status=0 when the CONNECT tunnel fails, but the
        # proxy's response code shows up as `< HTTP/1.1 402 ...` in -v.
        if status_code == 0 and "< HTTP/1.1 402" in err:
            status_code = 402

        try:
            parsed = json.loads(body) if body.startswith(("{", "[")) else body
        except json.JSONDecodeError:
            parsed = body

        return status_code, parsed

    # ------------------------------------------------------------------
    # Public single-code validation
    # ------------------------------------------------------------------
    async def validate(
        self,
        code: str,
        cart_product: dict | None = None,
    ) -> dict:
        """Validate a single coupon code with retries.

        Returns the normalised flat result dict (see ``_format_result``).
        Permanent failures (400 rejections, referral codes, echo mismatch)
        return immediately. Transient failures (timeout, 5xx, connection
        drop) retry up to ``RETRY_ATTEMPTS`` times with exponential backoff.

        Raises:
            ProxyQuotaExhausted: The proxy returned HTTP 402. Propagates to
                the caller so an entire batch can be aborted.
        """
        product = cart_product or CART_PRODUCT
        last_result: dict | None = None

        for attempt in range(RETRY_ATTEMPTS):
            # Let ProxyQuotaExhausted propagate — don't retry on quota.
            try:
                result = await self._validate_once(code, product)
            except ProxyQuotaExhausted:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "[iherb_api] Unexpected error validating %s: %s", code, exc
                )
                result = self._format_result(
                    code,
                    valid=False,
                    message=f"connection failed: {str(exc)[:160]}",
                    confidence="low",
                )

            # Success or permanent rejection — return immediately.
            if not _is_transient(result):
                return result

            last_result = result

            # Back off before the next attempt (but not after the last).
            if attempt < RETRY_ATTEMPTS - 1:
                delay = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.info(
                    "[iherb_api] Transient failure for %s (attempt %d/%d): %s"
                    " — retrying in %.1fs",
                    code, attempt + 1, RETRY_ATTEMPTS,
                    result.get("message"), delay,
                )
                await asyncio.sleep(delay)

        logger.warning(
            "[iherb_api] Gave up on %s after %d attempts: %s",
            code, RETRY_ATTEMPTS,
            last_result.get("message") if last_result else "unknown",
        )
        return last_result if last_result is not None else self._format_result(
            code, valid=False, message="unknown transient failure",
            confidence="low",
        )

    async def _validate_once(self, code: str, product: dict) -> dict:
        """Single-attempt validation with a fresh cookie jar."""
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, prefix="iherb_"
        ) as fh:
            cookie_file = fh.name

        try:
            # Step 1: Add product to cart. Checkout API accepts fresh
            # sessions without an explicit GET /cart so we skip that.
            status, _body = await self._curl(
                cookie_file, "POST",
                {"lineItems": [product]},
                ADD_ITEM_URL,
            )
            if status == 402 and self.proxy_url:
                raise ProxyQuotaExhausted("Proxy returned 402 on add_to_cart")
            if status == 0:
                return self._format_result(
                    code, valid=False,
                    message="connection failed on add_to_cart",
                    http_code=0, confidence="low",
                )
            if status >= 500:
                return self._format_result(
                    code, valid=False,
                    message=f"add_to_cart failed: HTTP {status}",
                    http_code=status, confidence="low",
                )
            if status >= 400 and status != 402:
                return self._format_result(
                    code, valid=False,
                    message=f"add_to_cart rejected: HTTP {status}",
                    http_code=status, confidence="high",
                )

            # Step 2: Apply coupon.
            status, data = await self._curl(
                cookie_file, "POST",
                {"couponCode": code},
                APPLY_COUPON_URL,
            )
            if status == 402 and self.proxy_url:
                raise ProxyQuotaExhausted("Proxy returned 402 on applyCoupon")

            if status == 200 and isinstance(data, dict):
                return self._parse_success(code, data)

            if status == 400 and isinstance(data, dict):
                msg = data.get("message", "invalid code")
                return self._format_result(
                    code, valid=False, message=msg,
                    http_code=400, confidence="high",
                )

            if status == 0:
                return self._format_result(
                    code, valid=False, message="applyCoupon timed out",
                    http_code=0, confidence="low",
                )

            if status >= 500:
                return self._format_result(
                    code, valid=False,
                    message=f"applyCoupon HTTP {status}",
                    http_code=status, confidence="low",
                )

            error_msg = (
                data.get("message") if isinstance(data, dict)
                else str(data)[:200]
            )
            return self._format_result(
                code, valid=False,
                message=f"HTTP {status}: {error_msg}",
                http_code=status, confidence="high",
            )

        finally:
            try:
                os.unlink(cookie_file)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Response classification — THE confidence guard
    # ------------------------------------------------------------------
    def _parse_success(self, code: str, data: dict) -> dict:
        """Parse a 200-OK applyCoupon response.

        Important: do NOT use ``subscriptionDiscount`` as a discount source.
        That field carries iHerb's auto-promo banner ("10% off your first
        order with GOLD60") which is shown to every unauthenticated session
        regardless of which coupon was applied. Using it caused every code
        accepted by the API to be reported as "10% off" — even referral
        codes and codes that didn't actually discount anything.

        What we CAN trust:

        - ``appliedCouponCodeType == 2`` → referral code (rejected per OFR0296)
        - ``appliedCouponCodeType == 1`` AND ``promoCode == our code`` →
          iHerb recognizes the string as a promo (high confidence)
        - ``couponDiscountPercent`` / raw discount fields, when populated,
          reflect what iHerb would apply if the cart were properly bound

        Confidence guard:

        - ``type=1`` + ``echoed_promo == code.upper()`` → valid, ``high``
        - ``type=1`` + ``echoed_promo`` empty → valid, ``low``
        - ``type=1`` + ``echoed_promo != code.upper()`` → **invalid**
          (iHerb resolved our input to a different known code — not a match)
        - ``type=2`` → invalid (referral)
        """
        applied_type = int(data.get("appliedCouponCodeType", 0) or 0)
        echoed_promo = (data.get("promoCode") or "").upper().strip()
        my_code = code.upper().strip()

        # Type 2 = referral / rewards code, rejected per OFR0296 policy.
        if applied_type == 2:
            return self._format_result(
                code, valid=False,
                applied_type=2,
                message="referral code (type=2) rejected",
                http_code=200,
                confidence="high",
            )

        # Type 1 with a mismatched promoCode echo: iHerb resolved our input
        # to a different known code, so it's not really a match for ours.
        if applied_type == 1 and echoed_promo and echoed_promo != my_code:
            return self._format_result(
                code, valid=False,
                applied_type=1,
                message=f"echoed promo mismatch: {echoed_promo}",
                http_code=200,
                confidence="high",
            )

        # Pull the real discount fields — NEVER subscriptionDiscount.
        discount_pct = float(data.get("couponDiscountPercent") or 0)
        discount_raw = float(
            data.get("totalDiscountRawAmount")
            or data.get("couponDiscountRawAmount")
            or data.get("totalSavingsRawAmount")
            or data.get("discountRawAmount")
            or 0
        )

        if applied_type == 1:
            # Confidence: high when iHerb echoes our exact code, low when
            # the echo is missing (still valid but we're less sure).
            confidence = "high" if echoed_promo == my_code else "low"
            message = (
                "code applied" if (discount_pct or discount_raw)
                else "code applied (no discount info)"
            )
            return self._format_result(
                code, valid=True,
                applied_type=1,
                discount_pct=abs(discount_pct),
                discount_raw=abs(discount_raw),
                message=message,
                http_code=200,
                confidence=confidence,
            )

        # No explicit applied_type but a raw discount was reported.
        if discount_raw:
            return self._format_result(
                code, valid=True,
                applied_type=applied_type,
                discount_raw=abs(discount_raw),
                message="code applied",
                http_code=200,
                confidence="low",
            )

        # Type 0 with no discount signal at all — iHerb accepted the POST
        # but didn't flag the code as a promo or a referral. Treat as
        # unrecognised.
        return self._format_result(
            code, valid=False,
            applied_type=applied_type,
            message="not recognised (type=0, no discount)",
            http_code=200,
            confidence="high",
        )

    # ------------------------------------------------------------------
    # Batch validation
    # ------------------------------------------------------------------
    async def validate_many(
        self,
        codes: list[str],
        brand_notes_map: dict[str, str],
    ) -> list[dict]:
        """Validate many codes concurrently.

        ``brand_notes_map`` maps code → AI-generated note string. If a note
        matches the "<Brand Name> brand only." shape, a brand-specific
        product is resolved (via iHerb search) and used in place of the
        default cart product for that single code. Brand resolutions are
        cached on the instance so repeated brand codes don't re-search.

        Raises:
            ProxyQuotaExhausted: propagated from any underlying validate().
            CascadingFailure: if ``CASCADING_FAILURE_THRESHOLD`` consecutive
                transient failures occur (proxy / upstream is broken).
        """
        semaphore = asyncio.Semaphore(self.concurrency)
        results: list[dict | None] = [None] * len(codes)
        consecutive_transient = 0
        cascading = False

        # We iterate codes in order but dispatch them concurrently via the
        # semaphore. The consecutive-transient counter is updated as each
        # result comes back, in index order, so we still detect runs even
        # when concurrency reorders completions.
        async def run_one(idx: int, code: str) -> dict:
            async with semaphore:
                product = await self._resolve_cart_product(
                    code, brand_notes_map.get(code, "")
                )
                result = await self.validate(code, cart_product=product)
                # Pacing: hold the semaphore while sleeping so concurrency=1
                # runs strictly serially at the requested rate. When
                # concurrency > 1 the pace applies per-slot, which is
                # intentional — higher concurrency means we've already
                # decided we can absorb more parallel load.
                if self.pace_seconds > 0 and idx < len(codes) - 1:
                    await asyncio.sleep(self.pace_seconds)
                return result

        tasks = [
            asyncio.create_task(run_one(i, c)) for i, c in enumerate(codes)
        ]

        try:
            for idx, task in enumerate(tasks):
                try:
                    result = await task
                except ProxyQuotaExhausted:
                    # Cancel outstanding work and propagate.
                    for other in tasks[idx + 1:]:
                        other.cancel()
                    raise
                results[idx] = result

                if _is_transient(result):
                    consecutive_transient += 1
                    if consecutive_transient >= CASCADING_FAILURE_THRESHOLD:
                        cascading = True
                        break
                else:
                    consecutive_transient = 0
        finally:
            # Cancel anything still pending so tasks don't leak.
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Drain cancellations so pytest doesn't complain about pending
            # tasks.
            await asyncio.gather(*tasks, return_exceptions=True)

        if cascading:
            raise CascadingFailure(
                f"{consecutive_transient} consecutive transient failures"
            )

        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # Brand-only product resolution
    # ------------------------------------------------------------------
    async def _resolve_cart_product(self, code: str, note: str) -> dict:
        """Return a cart product override for brand-only codes.

        Parses notes of the form ``"Brand Name brand only."`` and calls
        iHerb search to find a matching productId. Falls back to the
        default ``CART_PRODUCT`` on any failure. Results are cached per
        brand string on the instance.
        """
        if not note:
            return CART_PRODUCT
        match = BRAND_ONLY_NOTE_RE.match(note)
        if not match:
            return CART_PRODUCT

        brand = match.group(1).strip()
        if brand in self._brand_cache:
            return self._brand_cache[brand]

        try:
            product = await self._search_brand_product(brand)
        except ProxyQuotaExhausted:
            raise
        except Exception as exc:
            logger.warning(
                "[iherb_api] Brand resolution failed for %r (%s): %s — "
                "falling back to default cart product", brand, code, exc,
            )
            product = CART_PRODUCT

        self._brand_cache[brand] = product
        return product

    async def _search_brand_product(self, brand: str) -> dict:
        """Hit iHerb search and return the first productId as a cart entry.

        On any parsing failure or non-200 response, returns the default
        ``CART_PRODUCT``. The caller caches the result.
        """
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, prefix="iherb_search_"
        ) as fh:
            cookie_file = fh.name
        try:
            url = SEARCH_URL_TMPL.format(brand=brand.replace(" ", "+"))
            status, body = await self._curl(cookie_file, "GET", None, url)
            if status == 402 and self.proxy_url:
                raise ProxyQuotaExhausted("Proxy returned 402 on brand search")
            if status != 200 or not isinstance(body, str):
                logger.warning(
                    "brand product search for %r returned HTTP %s — "
                    "using default CART_PRODUCT (brand resolution unavailable)",
                    brand, status,
                )
                return CART_PRODUCT
            m = PRODUCT_ID_RE.search(body)
            if not m:
                return CART_PRODUCT
            product_id = int(m.group(1))
            return {"productId": product_id, "quantity": 1}
        finally:
            try:
                os.unlink(cookie_file)
            except OSError:
                pass


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------
def _is_transient(result: dict) -> bool:
    """Decide whether a validation result indicates a transient failure.

    Permanent rejections (invalid code, referral code, echo mismatch, and
    any success) are NOT transient.  Transient conditions are connection
    failures (http_code == 0) and server errors (http_code >= 500) — exactly
    the cases where retrying makes sense.  The public ``confidence`` field is
    never set to ``"transient"``; this helper uses ``http_code`` instead so
    the detection logic stays internal.
    """
    if result.get("valid"):
        return False
    http_code = result.get("http_code", -1)
    return http_code == 0 or http_code == 429 or http_code >= 500
