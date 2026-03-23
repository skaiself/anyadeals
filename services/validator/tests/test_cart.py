import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.cart import build_cart, clear_cart, CartError


@pytest.mark.asyncio
@patch("src.cart.human_delay", new_callable=AsyncMock)
async def test_clear_cart(mock_delay):
    page = AsyncMock()
    page.goto = AsyncMock()
    # locator() is synchronous in Playwright — use MagicMock so it returns a locator mock
    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=True)
    page.locator = MagicMock(return_value=mock_locator)

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
