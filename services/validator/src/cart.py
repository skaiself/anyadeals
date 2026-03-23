import logging
import re

from playwright.async_api import Page

from src.browser import human_delay
from src.constants import (
    CART_EMPTY_INDICATOR,
    CART_EMPTY_TEXT,
    CART_ITEM_REMOVE,
    CART_ITEM_REMOVE_TEXT,
    CART_REMOVE_ALL_TEXT,
    CART_URL_PATH,
    DIRECT_PRODUCT_IDS,
)

logger = logging.getLogger("promocheckiherb")


class CartError(Exception):
    pass


def _cart_url(base_url: str) -> str:
    return base_url.replace("www.iherb.com", "checkout.iherb.com") + CART_URL_PATH


async def clear_cart(page: Page, base_url: str) -> None:
    logger.info("Clearing cart")
    await page.goto(_cart_url(base_url))
    await human_delay()

    # Check if cart is empty — try text-based first, then legacy CSS selector
    empty_text = page.get_by_text(CART_EMPTY_TEXT)
    empty_css = page.locator(CART_EMPTY_INDICATOR)
    if await empty_text.is_visible() or await empty_css.is_visible():
        logger.info("Cart is already empty")
        return

    # Try "Remove all" button first (faster than removing one by one)
    remove_all = page.get_by_role("button", name=CART_REMOVE_ALL_TEXT)
    if await remove_all.is_visible():
        await remove_all.click()
        await human_delay()
        logger.info("Cart cleared via 'Remove all'")
        return

    # Fall back to removing items one by one — try text-based, then CSS
    while True:
        text_btn = page.get_by_role("button", name=CART_ITEM_REMOVE_TEXT)
        css_btn = page.locator(CART_ITEM_REMOVE)
        if await text_btn.count() > 0:
            await text_btn.first.click()
            await human_delay()
        elif await css_btn.count() > 0:
            await css_btn.first.click()
            await human_delay()
        else:
            break

    logger.info("Cart cleared")


async def _get_cart_total(page: Page, base_url: str = "") -> float:
    # Reads total from the currently loaded cart page (no navigation)
    total_el = page.get_by_text(re.compile(r"^\$[\d.,]+$")).last
    text = await total_el.text_content() or "0"
    # Strip thousand separators and normalize decimal separator
    cleaned = re.sub(r"[^\d.,]", "", text)
    if "," in cleaned and "." in cleaned:
        if cleaned.rindex(",") > cleaned.rindex("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


async def _add_product_via_api(page: Page, base_url: str, product_id: int) -> bool:
    """Add a product to cart via checkout.iherb.com API. No product page visit needed."""
    logger.info("Adding product via API: %d", product_id)
    try:
        result = await page.evaluate("""
            async (productId) => {
                const resp = await fetch('https://checkout.iherb.com/api/Carts/v3/catalog/lineItems', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ productId: productId, quantity: 1 })
                });
                return { status: resp.status, ok: resp.ok };
            }
        """, product_id)
        if result.get("ok"):
            logger.info("Product %d added to cart via API", product_id)
            return True
        else:
            logger.warning("API returned status %s for product %d", result.get("status"), product_id)
            return False
    except Exception as e:
        logger.warning("Failed to add product %d via API: %s", product_id, e)
        return False


async def build_cart(
    page: Page,
    base_url: str,
    min_cart_value: float,
    product_categories: list[str],
    timeout_ms: int = 60000,
) -> float:
    logger.info("Building cart to minimum value: %.2f", min_cart_value)

    # Add products via checkout.iherb.com API (no www.iherb.com visit needed)
    # Page must already be on checkout.iherb.com for cookies/session
    added_count = 0
    for product_id in DIRECT_PRODUCT_IDS:
        if await _add_product_via_api(page, base_url, product_id):
            added_count += 1
            if added_count >= 3:
                break

    # Reload cart page to see updated total
    await page.goto(_cart_url(base_url))
    await human_delay()

    total = await _get_cart_total(page, base_url)
    logger.info("Cart total after %d API adds: %.2f", added_count, total)

    if total >= min_cart_value:
        logger.info("Cart meets minimum value: %.2f >= %.2f", total, min_cart_value)
        return total

    # Add remaining products
    for product_id in DIRECT_PRODUCT_IDS[added_count:]:
        await _add_product_via_api(page, base_url, product_id)

    await page.goto(_cart_url(base_url))
    await human_delay()
    total = await _get_cart_total(page, base_url)
    logger.info("Cart total after all API adds: %.2f", total)

    if total >= min_cart_value:
        return total

    raise CartError(
        f"Could not build cart to minimum value. "
        f"Reached {total:.2f}, needed {min_cart_value:.2f}"
    )
