import logging
import re

from playwright.async_api import Page

from src.browser import human_delay
from src.constants import (
    COUPON_APPLY_BUTTON,
    COUPON_ERROR_MESSAGE,
    COUPON_INPUT,
    COUPON_NOT_APPLIED_TEXT,
)
from src.results import CouponResult

logger = logging.getLogger("promocheckiherb")


def parse_discount_type(text: str) -> str:
    if not text:
        return ""
    lower = text.lower()
    if "free shipping" in lower or "free delivery" in lower:
        return "free_shipping"
    if "%" in text:
        return "percentage"
    if re.search(r"[$€£¥]|[\d]+[.,]\d{2}", text):
        return "fixed"
    return ""


def parse_discount_amount(text: str) -> str:
    if not text:
        return ""
    numbers = re.findall(r"[\d]+[.]?\d*", text.replace(",", "."))
    return numbers[0] if numbers else ""


async def apply_coupon(
    page: Page,
    base_url: str,
    coupon_code: str,
    region: str,
    timeout_ms: int = 60000,
) -> CouponResult:
    logger.info("[%s/%s] Applying coupon: %s", coupon_code, region, coupon_code)

    try:
        # Cart page is on checkout.iherb.com
        cart_url = base_url.replace("www.iherb.com", "checkout.iherb.com") + "/cart"

        # Only navigate if we're not already on the cart page
        # IMPORTANT: don't reload if already on cart — checkout.iherb.com
        # blocks repeated navigation (ERR_CONNECTION_CLOSED)
        current_url = page.url or ""
        if "checkout.iherb.com/cart" not in current_url:
            await page.goto(cart_url)
            await human_delay()

        # Wait for coupon input to appear (may need scroll or time to render)
        try:
            await page.wait_for_selector(COUPON_INPUT, state="visible", timeout=10000)
        except Exception:
            # Scroll down — coupon input might be below the fold
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await human_delay()

        await page.locator(COUPON_INPUT).fill(coupon_code)
        await human_delay()

        await page.locator(COUPON_APPLY_BUTTON).click()
        await human_delay()

        # Wait for either error message or coupon status change (text-based detection)
        error_locator = page.get_by_text(COUPON_ERROR_MESSAGE)
        not_applied_locator = page.get_by_text(
            re.compile(rf"{re.escape(coupon_code)}.*{COUPON_NOT_APPLIED_TEXT}", re.IGNORECASE)
        )
        applied_locator = page.get_by_text(
            re.compile(rf"{re.escape(coupon_code)}.*applied(?!.*not applied)", re.IGNORECASE)
        )

        try:
            # Wait for page to settle after clicking apply
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass  # Continue even if networkidle times out

        # Check for error message first
        if await error_locator.is_visible():
            logger.info("[%s/%s] Coupon invalid: %s", coupon_code, region, COUPON_ERROR_MESSAGE)
            return CouponResult(
                coupon_code=coupon_code,
                region=region,
                valid="false",
                discount_amount="",
                discount_type="",
                error_message=COUPON_ERROR_MESSAGE,
            )

        # Check for "not applied" status (coupon recognized but not eligible)
        if await not_applied_locator.is_visible():
            # Try to get the reason text from nearby elements
            status_text = await not_applied_locator.text_content() or ""
            logger.info("[%s/%s] Coupon not applied: %s", coupon_code, region, status_text)
            return CouponResult(
                coupon_code=coupon_code,
                region=region,
                valid="false",
                discount_amount="",
                discount_type="",
                error_message=status_text.strip(),
            )

        # Check for successful application
        if await applied_locator.is_visible():
            # Look for discount amount in the page text
            page_text = await page.text_content("body") or ""
            discount_text = ""
            # Look for discount values near the coupon code
            discount_match = re.search(
                rf"{re.escape(coupon_code)}.*?(-?\$[\d.,]+|[\d.,]+%)", page_text, re.IGNORECASE
            )
            if discount_match:
                discount_text = discount_match.group(1)

            discount_type = parse_discount_type(discount_text)
            discount_amount = parse_discount_amount(discount_text)

            logger.info(
                "[%s/%s] Coupon valid: %s %s",
                coupon_code, region, discount_amount, discount_type,
            )
            return CouponResult(
                coupon_code=coupon_code,
                region=region,
                valid="true",
                discount_amount=discount_amount,
                discount_type=discount_type,
                error_message="",
            )

        return CouponResult(
            coupon_code=coupon_code,
            region=region,
            valid="error",
            discount_amount="",
            discount_type="",
            error_message="Ambiguous result: no clear indicator",
        )

    except Exception as e:
        logger.error("[%s/%s] Error applying coupon: %s", coupon_code, region, e)
        return CouponResult(
            coupon_code=coupon_code,
            region=region,
            valid="error",
            discount_amount="",
            discount_type="",
            error_message=str(e),
        )
