"""
HTTP-based coupon validator using iHerb's checkout API + IPRoyal Web Unblocker.
No browser needed — all validation via JSON API calls.

Flow:
1. GET www.iherb.com → establish session cookies
2. POST checkout.iherb.com/api/Carts/v3/catalog/lineItems → add product to cart
3. POST checkout.iherb.com/api/Carts/v2/applyCoupon → test coupon code
4. Parse response for valid/invalid status
"""

import httpx
import logging
from datetime import datetime, timezone

from src.results import CouponResult

logger = logging.getLogger("promocheckiherb")

# Cheap products to add to cart (needed for coupon input to appear)
CART_PRODUCTS = [
    {"productId": 61864, "quantity": 1},  # Vitamin C ~$5.57
    {"productId": 70316, "quantity": 1},  # Vitamin D3 ~$5.00
    {"productId": 10695, "quantity": 1},  # Calcium Mag Zinc ~$4.50
]

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
}


async def validate_coupon(
    coupon_code: str,
    region_key: str,
    proxy_url: str,
    iherb_url: str = "https://www.iherb.com",
    locale_path: str = "",
) -> CouponResult:
    """Validate a single coupon code via iHerb's API."""
    logger.info("[%s/%s] Starting HTTP validation", coupon_code, region_key)

    try:
        async with httpx.AsyncClient(
            proxy=proxy_url,
            headers=HEADERS,
            follow_redirects=True,
            verify=False,  # Web Unblocker uses MITM — skip SSL verification
            timeout=httpx.Timeout(60.0),
        ) as client:
            # Step 1: Visit iHerb to get session cookies
            logger.info("[%s/%s] Establishing session", coupon_code, region_key)
            resp = await client.get(iherb_url + locale_path)
            if resp.status_code != 200:
                return CouponResult(
                    coupon_code=coupon_code,
                    region=region_key,
                    valid="error",
                    discount_amount="",
                    discount_type="",
                    error_message=f"Failed to load iHerb: HTTP {resp.status_code}",
                )

            # Step 2: Add products to cart via API
            logger.info("[%s/%s] Adding products to cart", coupon_code, region_key)
            for product in CART_PRODUCTS:
                resp = await client.post(
                    "https://checkout.iherb.com/api/Carts/v3/catalog/lineItems",
                    json={"lineItems": [product]},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("lineItems"):
                        logger.info("[%s/%s] Added product %d to cart", coupon_code, region_key, product["productId"])
                        break
            else:
                logger.warning("[%s/%s] Could not add any products to cart", coupon_code, region_key)

            # Step 3: Apply coupon code
            logger.info("[%s/%s] Applying coupon code", coupon_code, region_key)
            resp = await client.post(
                "https://checkout.iherb.com/api/Carts/v2/applyCoupon",
                json={"couponCode": coupon_code},
            )

            if resp.status_code == 200:
                data = resp.json()
                # Valid code — full cart response with coupon applied
                applied_type = data.get("appliedCouponCodeType", 0)
                discount_raw = data.get("totalDiscountRawAmount", 0)
                order_total = data.get("orderTotalAmount", 0)
                breakdown = data.get("discountBreakdown", {})

                discount_amount = str(abs(discount_raw)) if discount_raw else ""
                discount_type = "percentage" if applied_type == 1 else "fixed" if applied_type == 2 else ""

                logger.info(
                    "[%s/%s] Coupon VALID — type=%s, discount=%s, total=%s",
                    coupon_code, region_key, applied_type, discount_amount, order_total,
                )
                return CouponResult(
                    coupon_code=coupon_code,
                    region=region_key,
                    valid="true",
                    discount_amount=discount_amount,
                    discount_type=discount_type,
                    error_message="",
                )

            elif resp.status_code == 400:
                data = resp.json()
                error_msg = data.get("message", "")
                reason = data.get("applyFailedReason", "")

                logger.info(
                    "[%s/%s] Coupon INVALID — %s (%s)",
                    coupon_code, region_key, error_msg, reason,
                )
                return CouponResult(
                    coupon_code=coupon_code,
                    region=region_key,
                    valid="false",
                    discount_amount="",
                    discount_type="",
                    error_message=error_msg,
                )

            else:
                logger.warning(
                    "[%s/%s] Unexpected status %d",
                    coupon_code, region_key, resp.status_code,
                )
                return CouponResult(
                    coupon_code=coupon_code,
                    region=region_key,
                    valid="error",
                    discount_amount="",
                    discount_type="",
                    error_message=f"Unexpected HTTP {resp.status_code}",
                )

    except httpx.TimeoutException as e:
        logger.error("[%s/%s] Timeout: %s", coupon_code, region_key, e)
        return CouponResult(
            coupon_code=coupon_code,
            region=region_key,
            valid="error",
            discount_amount="",
            discount_type="",
            error_message=f"Timeout: {e}",
        )
    except Exception as e:
        logger.error("[%s/%s] Error: %s", coupon_code, region_key, e)
        return CouponResult(
            coupon_code=coupon_code,
            region=region_key,
            valid="error",
            discount_amount="",
            discount_type="",
            error_message=str(e),
        )
