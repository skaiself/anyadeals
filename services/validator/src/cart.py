import logging
import re

from playwright.async_api import Page

from src.browser import human_delay
from src.constants import (
    ADD_TO_CART_BUTTON,
    CART_EMPTY_INDICATOR,
    CART_EMPTY_TEXT,
    CART_ITEM_REMOVE,
    CART_ITEM_REMOVE_TEXT,
    CART_REMOVE_ALL_TEXT,
    CART_URL_PATH,
    CATEGORY_SEARCH_TERMS,
    PRODUCT_CARD,
    SEARCH_INPUT,
    SEARCH_SUBMIT,
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


async def _get_cart_total(page: Page, base_url: str) -> float:
    await page.goto(_cart_url(base_url))
    await human_delay()

    # Use text-based detection: find "Subtotal" label's sibling value
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


async def _add_products_from_category(
    page: Page, base_url: str, category: str, timeout_ms: int
) -> bool:
    search_term = CATEGORY_SEARCH_TERMS.get(category, category)
    logger.info("Searching for products: %s", search_term)

    await page.goto(base_url)
    await human_delay()

    search_box = page.locator(SEARCH_INPUT)
    await search_box.fill(search_term)
    await human_delay()

    await page.locator(SEARCH_SUBMIT).click()
    await human_delay()

    products = page.locator(PRODUCT_CARD)
    count = await products.count()
    if count == 0:
        logger.warning("No products found for category: %s", category)
        return False

    add_buttons = page.locator(ADD_TO_CART_BUTTON)
    added = 0
    for i in range(min(await add_buttons.count(), 5)):
        try:
            await add_buttons.nth(i).click()
            await human_delay()
            added += 1
        except Exception as e:
            logger.warning("Failed to add product %d: %s", i, e)

    logger.info("Added %d products from category '%s'", added, category)
    return added > 0


async def build_cart(
    page: Page,
    base_url: str,
    min_cart_value: float,
    product_categories: list[str],
    timeout_ms: int = 60000,
) -> float:
    logger.info("Building cart to minimum value: %.2f", min_cart_value)

    for category in product_categories:
        await _add_products_from_category(page, base_url, category, timeout_ms)
        total = await _get_cart_total(page, base_url)
        logger.info("Cart total after '%s': %.2f", category, total)

        if total >= min_cart_value:
            logger.info("Cart meets minimum value: %.2f >= %.2f", total, min_cart_value)
            return total

    final_total = await _get_cart_total(page, base_url)
    if final_total >= min_cart_value:
        return final_total

    raise CartError(
        f"Could not build cart to minimum value. "
        f"Reached {final_total:.2f}, needed {min_cart_value:.2f}"
    )
