import asyncio
import random
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page


def _random_delay_seconds() -> float:
    return random.uniform(1.0, 3.0)


async def human_delay() -> None:
    await asyncio.sleep(_random_delay_seconds())


async def dismiss_popups(page: Page) -> None:
    """Dismiss iHerb marketing overlays/popups that block interactions."""
    await page.evaluate("""
        document.querySelectorAll('.iherb-overlay, .modal-backdrop, .overlay')
            .forEach(el => el.remove());
    """)
    await asyncio.sleep(0.3)


def _parse_proxy(proxy_url: str) -> dict:
    parsed = urlparse(proxy_url)
    proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


async def create_browser_context(
    browser: Browser,
    region_config: dict,
    timeout_ms: int = 60000,
) -> BrowserContext:
    kwargs = {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    proxy_url = region_config.get("proxy", "")
    if proxy_url:
        kwargs["proxy"] = _parse_proxy(proxy_url)

    context = await browser.new_context(**kwargs)
    context.set_default_timeout(timeout_ms)
    context.set_default_navigation_timeout(timeout_ms)

    return context
