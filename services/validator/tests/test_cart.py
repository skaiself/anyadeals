import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.cart import build_cart, clear_cart, CartError


@pytest.mark.asyncio
@patch("src.cart.human_delay", new_callable=AsyncMock)
async def test_clear_cart(mock_delay):
    page = AsyncMock()
    page.goto = AsyncMock()

    # Mock for text-based empty cart detection (returns visible = True → cart is empty)
    empty_text_locator = AsyncMock()
    empty_text_locator.is_visible = AsyncMock(return_value=True)
    page.get_by_text = MagicMock(return_value=empty_text_locator)

    # Mock for CSS-based empty cart detection (fallback)
    empty_css_locator = AsyncMock()
    empty_css_locator.is_visible = AsyncMock(return_value=False)
    page.locator = MagicMock(return_value=empty_css_locator)

    await clear_cart(page, "https://www.iherb.com")
    page.goto.assert_called_once()


@pytest.mark.asyncio
@patch("src.cart.human_delay", new_callable=AsyncMock)
@patch("src.cart._get_cart_total", new=AsyncMock(return_value=55.0))
@patch("src.cart._add_products_from_category", new=AsyncMock(return_value=True))
async def test_build_cart_meets_minimum(mock_delay):
    page = AsyncMock()
    result = await build_cart(
        page, "https://www.iherb.com", 50.0, ["vitamins"], timeout_ms=60000
    )
    assert result >= 50.0


@pytest.mark.asyncio
@patch("src.cart.human_delay", new_callable=AsyncMock)
@patch("src.cart._get_cart_total", new=AsyncMock(return_value=10.0))
@patch("src.cart._add_products_from_category", new=AsyncMock(return_value=False))
async def test_build_cart_fails_below_minimum(mock_delay):
    page = AsyncMock()
    with pytest.raises(CartError, match="Could not build cart"):
        await build_cart(
            page, "https://www.iherb.com", 50.0, ["vitamins"], timeout_ms=60000
        )
