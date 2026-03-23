# main.py
import asyncio
import sys
from datetime import datetime, timezone

from playwright.async_api import async_playwright, Error as PlaywrightError

try:
    from playwright_stealth import stealth_async
except ImportError:
    async def stealth_async(page):
        pass  # stealth not available, continue without it

from src.browser import create_browser_context, dismiss_popups, human_delay
from src.cart import CartError, build_cart, clear_cart
from src.config import ConfigError, load_config
from src.constants import CAPTCHA_INDICATOR
from src.coupon import apply_coupon
from src.logging_setup import setup_logging
from src.results import CouponResult, ResultsWriter

logger = setup_logging()


class TransientError(Exception):
    """Wraps errors that should trigger a retry (page timeout, network)."""
    pass


class ProxyError(Exception):
    """Proxy connection failure — skip entire region."""
    pass


class CaptchaDetected(Exception):
    """Anti-bot detection triggered."""
    pass


def expand_coupons(config: dict) -> list[tuple[dict, str]]:
    """Expand coupon+region combinations. Returns list of (coupon, region_key)."""
    all_regions = list(config["regions"].keys())
    combinations = []
    for coupon in config["coupons"]:
        if "*" in coupon["regions"]:
            regions = all_regions
        else:
            regions = coupon["regions"]
        for region_key in regions:
            combinations.append((coupon, region_key))
    return combinations


async def _check_captcha(page) -> None:
    """Check if a visible CAPTCHA challenge is on the page."""
    captcha = page.locator(CAPTCHA_INDICATOR)
    if await captcha.count() > 0 and await captcha.first.is_visible():
        raise CaptchaDetected("CAPTCHA detected on page")


async def test_coupon(
    browser,
    coupon: dict,
    region_key: str,
    region_config: dict,
    defaults: dict,
    results_writer: ResultsWriter,
) -> str:
    """Run a single coupon test. Returns 'ok' on completion (even if coupon invalid).
    Raises TransientError for retryable failures, ProxyError for proxy issues."""
    min_cart_value = coupon["min_cart_value"] or defaults["min_cart_value"]
    timeout_ms = defaults["timeout_seconds"] * 1000
    base_url = region_config["iherb_url"]
    full_url = base_url + region_config["locale_path"]
    code = coupon["code"]

    logger.info("[%s/%s] Starting test", code, region_key)

    try:
        context = await create_browser_context(browser, region_config, timeout_ms, region_key)
    except PlaywrightError as e:
        if "proxy" in str(e).lower() or "connect" in str(e).lower():
            raise ProxyError(f"Proxy connection failed: {e}")
        raise TransientError(f"Browser context creation failed: {e}")

    page = None
    try:
        page = await context.new_page()
        await stealth_async(page)

        # Go directly to checkout.iherb.com/cart — this domain has less
        # Cloudflare protection than www.iherb.com. We test coupon validity
        # without a cart (iHerb still reports valid/invalid codes on empty cart).
        cart_url = base_url.replace("www.iherb.com", "checkout.iherb.com") + "/cart"
        try:
            await page.goto(cart_url)
        except PlaywrightError as e:
            if "net::" in str(e).lower() or "proxy" in str(e).lower():
                raise ProxyError(f"Proxy connection failed: {e}")
            raise TransientError(f"Navigation failed: {e}")
        await human_delay()

        # Dismiss marketing popups/overlays
        await dismiss_popups(page)

        # Check for CAPTCHA
        await _check_captcha(page)

        # Apply coupon directly (skip cart building — validity check works without items)
        result = await apply_coupon(page, base_url, code, region_key, timeout_ms)

        # Screenshot only on errors, not on normal "invalid coupon" results
        if result.valid == "error":
            screenshot = await page.screenshot()
            path = results_writer.save_screenshot(screenshot, code, region_key)
            logger.info("[%s/%s] Screenshot saved: %s", code, region_key, path)

        results_writer.write_result(result)
        return "ok"

    except CaptchaDetected as e:
        logger.warning("[%s/%s] CAPTCHA detected: %s", code, region_key, e)
        if page:
            try:
                screenshot = await page.screenshot()
                results_writer.save_screenshot(screenshot, code, region_key)
            except Exception:
                pass
        results_writer.write_result(CouponResult(
            coupon_code=code,
            region=region_key,
            valid="error",
            discount_amount="",
            discount_type="",
            error_message="CAPTCHA detected",
        ))
        return "ok"  # continue to next coupon, don't skip region

    except ProxyError:
        raise  # re-raise for region-level handling

    except CartError as e:
        logger.error("[%s/%s] Cart error: %s", code, region_key, e)
        if page:
            try:
                screenshot = await page.screenshot()
                results_writer.save_screenshot(screenshot, code, region_key)
            except Exception:
                pass
        results_writer.write_result(CouponResult(
            coupon_code=code,
            region=region_key,
            valid="error",
            discount_amount="",
            discount_type="",
            error_message=str(e),
        ))
        return "ok"

    except PlaywrightError as e:
        # Page timeout, network error — retryable
        raise TransientError(f"Transient error: {e}")

    except Exception as e:
        logger.error("[%s/%s] Unexpected error: %s", code, region_key, e)
        if page:
            try:
                screenshot = await page.screenshot()
                results_writer.save_screenshot(screenshot, code, region_key)
            except Exception:
                pass
        results_writer.write_result(CouponResult(
            coupon_code=code,
            region=region_key,
            valid="error",
            discount_amount="",
            discount_type="",
            error_message=str(e),
        ))
        return "ok"

    finally:
        await context.close()


async def run(config_path: str, headed: bool = False) -> None:
    try:
        config = load_config(config_path)
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    combinations = expand_coupons(config)
    logger.info("Testing %d coupon+region combinations", len(combinations))

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = f"results/{timestamp}.csv"
    results_writer = ResultsWriter(csv_path, "screenshots")

    # Track regions to skip (proxy failure)
    skip_regions: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not headed,
            channel="chrome",
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1280,800',
            ],
        )

        for coupon, region_key in combinations:
            code = coupon["code"]

            # Skip if region is marked as failed
            if region_key in skip_regions:
                logger.info("[%s/%s] Skipping — region marked as failed", code, region_key)
                results_writer.write_result(CouponResult(
                    coupon_code=code,
                    region=region_key,
                    valid="error",
                    discount_amount="",
                    discount_type="",
                    error_message="Skipped: region failed (proxy error)",
                ))
                continue

            region_config = config["regions"][region_key]
            retry_delay = config["defaults"]["retry_delay_seconds"]

            try:
                await test_coupon(
                    browser, coupon, region_key, region_config,
                    config["defaults"], results_writer,
                )

            except ProxyError as e:
                logger.error("[%s/%s] Proxy failed: %s — skipping region '%s'", code, region_key, e, region_key)
                skip_regions.add(region_key)
                results_writer.write_result(CouponResult(
                    coupon_code=code,
                    region=region_key,
                    valid="error",
                    discount_amount="",
                    discount_type="",
                    error_message=f"Proxy failed: {e}",
                ))

            except TransientError as e:
                logger.warning(
                    "[%s/%s] Transient failure (%s), retrying after %ds...",
                    code, region_key, e, retry_delay,
                )
                await asyncio.sleep(retry_delay)
                try:
                    await test_coupon(
                        browser, coupon, region_key, region_config,
                        config["defaults"], results_writer,
                    )
                except (TransientError, ProxyError, Exception) as e2:
                    logger.error("[%s/%s] Retry also failed: %s", code, region_key, e2)
                    results_writer.write_result(CouponResult(
                        coupon_code=code,
                        region=region_key,
                        valid="error",
                        discount_amount="",
                        discount_type="",
                        error_message=f"Failed after retry: {e2}",
                    ))

        await browser.close()

    summary = results_writer.get_summary()
    results_writer.close()
    logger.info(
        "Done! %d valid, %d invalid, %d errors. Results: %s",
        summary["valid"], summary["invalid"], summary["errors"], csv_path,
    )


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    headed = "--headed" in sys.argv
    asyncio.run(run(config_path, headed=headed))


if __name__ == "__main__":
    main()
