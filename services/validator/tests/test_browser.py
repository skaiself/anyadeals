import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.browser import create_browser_context, human_delay


def test_human_delay_range():
    """human_delay returns a coroutine that sleeps 1-3 seconds."""
    import random
    random.seed(42)
    from src.browser import _random_delay_seconds
    delay = _random_delay_seconds()
    assert 1.0 <= delay <= 3.0


@pytest.mark.asyncio
async def test_create_browser_context_sets_proxy():
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    region_config = {
        "proxy": "http://user:pass@proxy:8080",
        "currency": "USD",
        "iherb_url": "https://www.iherb.com",
        "locale_path": "",
    }

    ctx = await create_browser_context(mock_browser, region_config, timeout_ms=60000)

    mock_browser.new_context.assert_called_once()
    call_kwargs = mock_browser.new_context.call_args.kwargs
    assert call_kwargs["proxy"]["server"] == "http://proxy:8080"
    assert call_kwargs["proxy"]["username"] == "user"
    assert call_kwargs["proxy"]["password"] == "pass"
