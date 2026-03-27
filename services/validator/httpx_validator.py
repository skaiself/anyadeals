"""
HTTP-based coupon validator using iHerb's checkout API + IPRoyal Web Unblocker.
Uses curl subprocess for reliable session/cookie handling through the unblocker proxy.

Flow:
1. GET checkout.iherb.com/cart → establish session cookies
2. POST checkout.iherb.com/api/Carts/v3/catalog/lineItems → add product to cart
3. POST checkout.iherb.com/api/Carts/v2/applyCoupon → test coupon code
4. Parse JSON response for valid/invalid status
"""

import asyncio
import json
import logging
import os
import tempfile

from src.results import CouponResult

logger = logging.getLogger("promocheckiherb")

CART_PRODUCT = {"productId": 61864, "quantity": 20}  # Vitamin C ~$5.57 × 20 ≈ $111


async def _curl(proxy_url: str, cookie_file: str, method: str, url: str, data: dict | None = None) -> tuple[int, dict | str]:
    """Run a curl request through the unblocker proxy with cookie persistence."""
    cmd = [
        "curl", "-k", "-s", "--max-time", "60",
        "-x", proxy_url,
        "-b", cookie_file,
        "-c", cookie_file,
        "-L",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "-w", "\n%{http_code}",
    ]
    if method == "POST" and data is not None:
        cmd.extend(["-X", "POST", "-d", json.dumps(data)])
    cmd.append(url)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace").strip()

    # Last line is the HTTP status code (from -w)
    lines = output.rsplit("\n", 1)
    body = lines[0] if len(lines) > 1 else ""
    status_code = int(lines[-1]) if lines[-1].isdigit() else 0

    try:
        parsed = json.loads(body) if body.startswith("{") or body.startswith("[") else body
    except json.JSONDecodeError:
        parsed = body

    return status_code, parsed


async def validate_coupon(
    coupon_code: str,
    region_key: str,
    proxy_url: str,
    iherb_url: str = "https://www.iherb.com",
    locale_path: str = "",
) -> CouponResult:
    """Validate a single coupon code via iHerb's API using curl + Web Unblocker."""
    logger.info("[%s/%s] Starting HTTP validation", coupon_code, region_key)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, prefix="iherb_cookies_") as f:
        cookie_file = f.name

    try:
        checkout_base = iherb_url.replace("www.iherb.com", "checkout.iherb.com")

        # Step 1: Establish session on checkout domain
        logger.info("[%s/%s] Establishing session", coupon_code, region_key)
        status, _ = await _curl(proxy_url, cookie_file, "GET", checkout_base + "/cart")
        if status == 0:
            return CouponResult(coupon_code=coupon_code, region=region_key, valid="error",
                                discount_amount="", discount_type="", error_message="Connection failed to checkout")

        # Step 2: Add product to cart via API
        logger.info("[%s/%s] Adding product to cart", coupon_code, region_key)
        status, data = await _curl(
            proxy_url, cookie_file, "POST",
            "https://checkout.iherb.com/api/Carts/v3/catalog/lineItems",
            {"lineItems": [CART_PRODUCT]},
        )
        if status == 200 and isinstance(data, dict):
            items = data.get("lineItems", [])
            total = data.get("cartTotal", "$0")
            logger.info("[%s/%s] Cart: %d items, total %s", coupon_code, region_key, len(items), total)
        else:
            logger.warning("[%s/%s] Add to cart returned %d", coupon_code, region_key, status)

        # Step 3: Apply coupon code
        logger.info("[%s/%s] Applying coupon", coupon_code, region_key)
        status, data = await _curl(
            proxy_url, cookie_file, "POST",
            "https://checkout.iherb.com/api/Carts/v2/applyCoupon",
            {"couponCode": coupon_code},
        )

        if status == 200 and isinstance(data, dict):
            # Valid code — full cart response
            applied_type = data.get("appliedCouponCodeType", 0)

            # Try multiple discount fields — iHerb's API isn't consistent
            discount_raw = (
                data.get("totalDiscountRawAmount")
                or data.get("couponDiscountRawAmount")
                or data.get("totalSavingsRawAmount")
                or data.get("discountRawAmount")
                or 0
            )

            # For percentage coupons, check couponDiscountPercent
            discount_pct = data.get("couponDiscountPercent", 0)

            if applied_type == 1 and discount_pct:
                # Percentage coupon — use the percentage value directly
                discount_amount = str(abs(discount_pct))
                discount_type = "percentage"
            elif discount_raw:
                discount_amount = str(abs(discount_raw))
                discount_type = "percentage" if applied_type == 1 else "fixed" if applied_type == 2 else ""
            else:
                discount_amount = ""
                discount_type = "percentage" if applied_type == 1 else "fixed" if applied_type == 2 else ""

            # Log response keys for debugging discount extraction
            discount_keys = {k: v for k, v in data.items()
                            if any(w in k.lower() for w in ("discount", "coupon", "saving", "promo"))}
            logger.info("[%s/%s] Coupon VALID — type=%s, discount=%s, fields=%s",
                        coupon_code, region_key, applied_type, discount_amount, discount_keys)

            return CouponResult(
                coupon_code=coupon_code, region=region_key, valid="true",
                discount_amount=discount_amount, discount_type=discount_type, error_message="",
            )

        elif status == 400 and isinstance(data, dict):
            error_msg = data.get("message", "Invalid code")
            reason = data.get("applyFailedReason", "")
            logger.info("[%s/%s] Coupon INVALID — %s", coupon_code, region_key, error_msg)
            return CouponResult(
                coupon_code=coupon_code, region=region_key, valid="false",
                discount_amount="", discount_type="", error_message=error_msg,
            )

        else:
            error_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)[:200]
            logger.warning("[%s/%s] Unexpected response: %d", coupon_code, region_key, status)
            return CouponResult(
                coupon_code=coupon_code, region=region_key, valid="error",
                discount_amount="", discount_type="", error_message=f"HTTP {status}: {error_msg}",
            )

    except Exception as e:
        logger.error("[%s/%s] Error: %s", coupon_code, region_key, e)
        return CouponResult(
            coupon_code=coupon_code, region=region_key, valid="error",
            discount_amount="", discount_type="", error_message=str(e),
        )
    finally:
        try:
            os.unlink(cookie_file)
        except OSError:
            pass
