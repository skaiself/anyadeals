import asyncio
import random
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page


def _random_delay_seconds() -> float:
    return random.uniform(1.0, 3.0)


async def human_delay() -> None:
    await asyncio.sleep(_random_delay_seconds())


async def dismiss_popups(page: Page) -> None:
    """Dismiss iHerb marketing overlays/popups and cookie consent."""
    # Accept cookie consent (TrustArc)
    try:
        accept_btn = page.get_by_text("Accept All")
        if await accept_btn.is_visible(timeout=3000):
            await accept_btn.click()
            await asyncio.sleep(1)
    except Exception:
        pass

    # Close email signup modal
    try:
        close_btn = page.locator('button:has-text("No thanks"), button[aria-label="close"]')
        if await close_btn.first.is_visible(timeout=2000):
            await close_btn.first.click()
            await asyncio.sleep(0.5)
    except Exception:
        pass

    # Remove overlay elements via JS
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


# Region-specific browser settings
REGION_LOCALES = {
    "us": ("en-US", "America/Chicago"),
    "de": ("de-DE", "Europe/Berlin"),
    "gb": ("en-GB", "Europe/London"),
    "fr": ("fr-FR", "Europe/Paris"),
    "ca": ("en-CA", "America/Toronto"),
    "au": ("en-AU", "Australia/Sydney"),
}


async def create_browser_context(
    browser: Browser,
    region_config: dict,
    timeout_ms: int = 60000,
    region_key: str = "us",
) -> BrowserContext:
    locale, timezone_id = REGION_LOCALES.get(region_key, ("en-US", "America/Chicago"))

    kwargs = {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "locale": locale,
        "timezone_id": timezone_id,
        "color_scheme": "light",
        "extra_http_headers": {
            "Accept-Language": f"{locale},{locale.split('-')[0]};q=0.9,en;q=0.8",
        },
    }

    proxy_url = region_config.get("proxy", "")
    if proxy_url:
        kwargs["proxy"] = _parse_proxy(proxy_url)

    context = await browser.new_context(**kwargs)
    context.set_default_timeout(timeout_ms)
    context.set_default_navigation_timeout(timeout_ms)

    return context
