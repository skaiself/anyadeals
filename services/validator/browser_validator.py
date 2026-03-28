#!/usr/bin/env python3
"""
Playwright-based browser validator for iHerb coupon codes.

Automates a real Chromium browser to validate coupon codes on iHerb's cart page
across multiple shipping regions. Outputs JSON results to stdout compatible with
browser_validate.py processor.

Usage:
    python browser_validator.py --codes WELCOME25 GOLD60 --regions us de --headless
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

logger = logging.getLogger("browser_validator")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

PRODUCT_URL = "https://www.iherb.com/pr/61864"
CART_URL = "https://checkout.iherb.com/cart"

# Selectors (from constants.py + task spec)
COUPON_INPUT = "#coupon-input"
COUPON_APPLY = 'button:has-text("Apply"):near(#coupon-input)'
PROMO_RESULT_CLASS = ".css-1x4pyzj"
REMOVE_PROMO_BUTTON = 'button[aria-label="Remove Promo Code"]'

# Region config: country display name, optional zip code
REGION_CONFIG: dict[str, dict[str, Any]] = {
    "us": {"country": "United States", "zip": "32301"},
    "de": {"country": "Germany", "zip": ""},
    "gb": {"country": "United Kingdom", "zip": ""},
    "au": {"country": "Australia", "zip": ""},
    "ca": {"country": "Canada", "zip": ""},
    "jp": {"country": "Japan", "zip": ""},
    "kr": {"country": "South Korea", "zip": ""},
}

# Patterns for interpreting promo result messages
DISCOUNT_PCT_PATTERN = re.compile(r"(\d+)%\s*off\s+with", re.IGNORECASE)
DISCOUNT_FIXED_PATTERN = re.compile(r"\$(\d+(?:\.\d+)?)\s*off\s+with", re.IGNORECASE)
MIN_CART_PATTERN = re.compile(r"Add\s+\$(\d+(?:\.\d+)?)\s+to\s+unlock\s+(\d+)%\s*off", re.IGNORECASE)
NOT_ELIGIBLE_REGION = re.compile(r"shipping destination is not eligible", re.IGNORECASE)
INVALID_CODE_PATTERN = re.compile(r"valid promo or Rewards code", re.IGNORECASE)
WRONG_PRODUCT_PATTERN = re.compile(r"Items in cart are not eligible", re.IGNORECASE)


def parse_promo_message(text: str) -> dict[str, Any]:
    """Parse the promo result text into a structured result dict."""
    text = text.strip()
    result: dict[str, Any] = {"valid": False, "discount": "", "min_cart": 0, "message": text}

    # "X% off with CODE" — valid, discount percentage
    m = DISCOUNT_PCT_PATTERN.search(text)
    if m:
        pct = int(m.group(1))
        result["valid"] = True
        result["discount"] = f"{pct}% off"
        return result

    # "$X off with CODE" — valid, fixed discount
    m = DISCOUNT_FIXED_PATTERN.search(text)
    if m:
        amt = m.group(1)
        result["valid"] = True
        result["discount"] = f"${amt} off"
        return result

    # "Add $X to unlock Y% off" — valid but needs min cart
    m = MIN_CART_PATTERN.search(text)
    if m:
        min_cart = float(m.group(1))
        pct = int(m.group(2))
        result["valid"] = True
        result["discount"] = f"{pct}% off"
        result["min_cart"] = min_cart
        return result

    # "shipping destination is not eligible" — invalid for region
    if NOT_ELIGIBLE_REGION.search(text):
        result["valid"] = False
        result["message"] = "Shipping destination not eligible"
        return result

    # "valid promo or Rewards code" — invalid code
    if INVALID_CODE_PATTERN.search(text):
        result["valid"] = False
        result["message"] = "Invalid promo code"
        return result

    # "Items in cart are not eligible" — valid code, wrong product
    if WRONG_PRODUCT_PATTERN.search(text):
        result["valid"] = True
        result["discount"] = ""
        result["message"] = "Items in cart are not eligible"
        return result

    return result


def add_product_to_cart(page: Page) -> bool:
    """Add a product to cart from the checkout.iherb.com recommended section.

    Key: we must stay on checkout.iherb.com domain to preserve session cookies.
    The empty cart page shows "Recommended for you" products with Add to Cart
    buttons — clicking these adds items within the same domain session.
    """
    logger.info("Adding product from cart page recommendations")
    try:
        page.goto(CART_URL, wait_until="commit", timeout=30000)
        page.wait_for_timeout(8000)

        # Click Add to Cart from recommended products on the cart page
        add_btn = page.locator('button:has-text("Add to Cart"):visible').first
        add_btn.click(force=True)
        logger.info("Clicked Add to Cart from recommendations")
        page.wait_for_timeout(3000)

        # Reload to see cart with items
        page.reload(wait_until="commit", timeout=30000)
        page.wait_for_timeout(5000)

        # Check we have items
        empty_indicator = page.locator('text="Your shopping cart is empty"')
        if empty_indicator.count() > 0:
            logger.warning("Cart appears empty after adding product")
            return False

        logger.info("Product added to cart successfully")
        return True

    except PlaywrightTimeout:
        logger.error("Timeout while adding product to cart")
        return False
    except Exception as e:
        logger.error("Error adding product to cart: %s", e)
        return False


def change_shipping_region(page: Page, region_key: str) -> bool:
    """Change the shipping region on the cart page.

    Returns True if the region was changed successfully.
    """
    config = REGION_CONFIG.get(region_key)
    if not config:
        logger.error("Unknown region: %s", region_key)
        return False

    country_name = config["country"]
    zip_code = config.get("zip", "")

    logger.info("Changing shipping region to %s (%s)", region_key, country_name)

    try:
        # Click the "Ship to" button
        ship_to_btn = page.locator('button:has-text("Ship to")').first
        ship_to_btn.wait_for(state="visible", timeout=10000)
        ship_to_btn.click()
        page.wait_for_timeout(1500)

        # Select country from dropdown
        country_select = page.locator(
            'select:near(:text("Country")), '
            'select:near(:text("Region")), '
            '[data-testid="country-select"], '
            'select[name="country"]'
        ).first
        country_select.wait_for(state="visible", timeout=10000)
        country_select.select_option(label=country_name)
        page.wait_for_timeout(1000)

        # Fill zip code if needed
        if zip_code:
            zip_input = page.locator(
                'input[name="zipCode"], '
                'input[placeholder*="Zip"], '
                'input[placeholder*="zip"], '
                'input[placeholder*="Postal"], '
                'input:near(:text("Zip"))'
            ).first
            try:
                zip_input.wait_for(state="visible", timeout=5000)
                zip_input.fill(zip_code)
                page.wait_for_timeout(500)
            except PlaywrightTimeout:
                logger.info("No zip code input found for %s, continuing", region_key)

        # Click Save button
        save_btn = page.locator(
            'button:has-text("Save"), '
            'button:has-text("Apply"), '
            'button[type="submit"]:near(:text("Country"))'
        ).first
        save_btn.wait_for(state="visible", timeout=5000)
        save_btn.click()
        page.wait_for_timeout(3000)

        logger.info("Shipping region changed to %s", region_key)
        return True

    except PlaywrightTimeout:
        logger.error("Timeout changing shipping region to %s", region_key)
        return False
    except Exception as e:
        logger.error("Error changing shipping region to %s: %s", region_key, e)
        return False


def test_coupon_code(page: Page, code: str) -> dict[str, Any]:
    """Apply a coupon code on the cart page and read the result.

    Returns parsed result dict with keys: valid, discount, min_cart, message.
    """
    logger.info("Testing coupon code: %s", code)

    try:
        # Make sure we're on the cart page
        if "checkout.iherb.com/cart" not in page.url:
            page.goto(CART_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

        # Find and fill the coupon input — try multiple selectors
        coupon_input = page.locator("#coupon-input")
        try:
            coupon_input.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeout:
            # Try scrolling to it or finding by placeholder
            coupon_input = page.locator('input[placeholder*="promo" i], input[placeholder*="code" i]').first
            try:
                coupon_input.wait_for(state="visible", timeout=5000)
            except PlaywrightTimeout:
                # Last resort: scroll down and try Enter promo code text
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)
                # Save debug screenshot
                page.screenshot(path="/tmp/debug_coupon_input.png")
                logger.error("Could not find coupon input, saved debug screenshot")
                return {"valid": False, "discount": "", "min_cart": 0, "message": "Coupon input not found"}

        coupon_input.fill("")
        page.wait_for_timeout(300)
        coupon_input.fill(code)
        page.wait_for_timeout(500)

        # Click Apply button — try multiple approaches
        apply_btn = page.locator('button:has-text("Apply")').first
        try:
            apply_btn.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeout:
            # Try pressing Enter instead
            coupon_input.press("Enter")
            logger.info("Pressed Enter instead of clicking Apply")
            page.wait_for_timeout(3000)
            apply_btn = None

        if apply_btn:
            apply_btn.click()
        logger.info("Clicked Apply for code: %s", code)

        # Wait for result to appear
        page.wait_for_timeout(3000)

        # Read the promo result section
        result_text = ""
        promo_section = page.locator(PROMO_RESULT_CLASS)
        try:
            promo_section.wait_for(state="visible", timeout=10000)
            result_text = promo_section.inner_text(timeout=5000)
            logger.info("Promo result text for %s: %s", code, result_text[:200])
        except PlaywrightTimeout:
            # Try alternative: check for error message in any nearby element
            logger.warning("Promo result section not found for %s, checking alternatives", code)
            error_el = page.locator('text="Please enter a valid promo or Rewards code"')
            if error_el.count() > 0:
                result_text = "Please enter a valid promo or Rewards code."
            else:
                # Try to get any text near the coupon input area
                coupon_section = page.locator(COUPON_INPUT).locator("..").locator("..")
                try:
                    result_text = coupon_section.inner_text(timeout=3000)
                except Exception:
                    result_text = "Unable to read promo result"

        # Parse the result
        parsed = parse_promo_message(result_text)

        # Try to remove the applied code for the next test
        _remove_promo_code(page)

        return parsed

    except PlaywrightTimeout:
        logger.error("Timeout testing coupon code: %s", code)
        return {
            "valid": False,
            "discount": "",
            "min_cart": 0,
            "message": "Timeout waiting for promo result",
        }
    except Exception as e:
        logger.error("Error testing coupon code %s: %s", code, e)
        return {
            "valid": False,
            "discount": "",
            "min_cart": 0,
            "message": f"Error: {e}",
        }


def _remove_promo_code(page: Page) -> None:
    """Remove any applied promo code by clicking the trash button."""
    try:
        remove_btn = page.locator(REMOVE_PROMO_BUTTON)
        if remove_btn.count() > 0:
            remove_btn.first.click()
            page.wait_for_timeout(2000)
            logger.info("Removed applied promo code")
        else:
            logger.debug("No promo code to remove")
    except Exception as e:
        logger.warning("Could not remove promo code: %s", e)


def run_validation(
    codes: list[str],
    regions: list[str],
    headless: bool = False,
    timeout_ms: int = 60000,
) -> list[dict[str, Any]]:
    """Run full browser-based validation for all codes across all regions.

    Returns list of result dicts in browser_validate.py format.
    """
    results: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        # Use IPRoyal Web Unblocker as proxy to bypass CAPTCHA
        proxy_url = os.environ.get("BROWSER_PROXY_URL") or os.environ.get("PROXY_URL", "")
        launch_opts = {
            "headless": headless,
            "channel": "chrome",
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--ignore-certificate-errors",
            ],
        }
        if proxy_url:
            launch_opts["proxy"] = {"server": proxy_url}
            logger.info("Using proxy: %s", proxy_url)

        browser = pw.chromium.launch(**launch_opts)

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            ignore_https_errors=True,
        )

        # Mask webdriver detection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        # Step 1: Add product to cart
        if not add_product_to_cart(page):
            logger.error("Failed to add product to cart, aborting")
            browser.close()
            return results

        # Step 2: For each region, test all codes
        for region_idx, region in enumerate(regions):
            logger.info("=== Testing region: %s (%d/%d) ===", region, region_idx + 1, len(regions))

            # Change shipping region (skip for the first region if it's US, which is default)
            if region_idx > 0 or region != "us":
                if not change_shipping_region(page, region):
                    logger.warning("Failed to change region to %s, skipping", region)
                    # Record error for all codes in this region
                    for code in codes:
                        _ensure_code_entry(results, code)
                        entry = _find_code_entry(results, code)
                        entry["results"][region] = {
                            "valid": False,
                            "discount": "",
                            "min_cart": 0,
                            "message": f"Failed to change region to {region}",
                        }
                    continue

            # Test each code
            for code in codes:
                _ensure_code_entry(results, code)
                entry = _find_code_entry(results, code)

                result = test_coupon_code(page, code)
                entry["results"][region] = result
                logger.info(
                    "Code %s in %s: valid=%s, discount=%s",
                    code, region, result["valid"], result.get("discount", ""),
                )

        browser.close()

    return results


def _ensure_code_entry(results: list[dict], code: str) -> None:
    """Ensure a result entry exists for the given code."""
    for entry in results:
        if entry["code"] == code:
            return
    results.append({"code": code, "results": {}})


def _find_code_entry(results: list[dict], code: str) -> dict:
    """Find the result entry for the given code."""
    for entry in results:
        if entry["code"] == code:
            return entry
    raise ValueError(f"No entry found for code: {code}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate iHerb coupon codes using a real browser (Playwright/Chromium).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python browser_validator.py --codes WELCOME25 GOLD60 IHERB22OFF
  python browser_validator.py --codes WELCOME25 --regions us de gb --headless
  python browser_validator.py --codes WELCOME25 GOLD60 --regions us --timeout 90000
        """,
    )
    parser.add_argument(
        "--codes",
        nargs="+",
        required=True,
        help="Coupon codes to validate",
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        default=["us", "de"],
        choices=list(REGION_CONFIG.keys()),
        help="Shipping regions to test (default: us de)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: headed for debugging)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60000,
        help="Default timeout in milliseconds for page operations (default: 60000)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable verbose logging to stderr",
    )

    args = parser.parse_args()

    # Configure logging to stderr so JSON output goes cleanly to stdout
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    codes = [c.upper().strip() for c in args.codes]
    regions = [r.lower().strip() for r in args.regions]

    logger.info("Validating %d codes across %d regions", len(codes), len(regions))
    logger.info("Codes: %s", ", ".join(codes))
    logger.info("Regions: %s", ", ".join(regions))
    logger.info("Headless: %s", args.headless)

    results = run_validation(
        codes=codes,
        regions=regions,
        headless=args.headless,
        timeout_ms=args.timeout,
    )

    # Output JSON to stdout
    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")

    # Summary to stderr
    valid_count = sum(
        1 for entry in results
        for region_result in entry["results"].values()
        if region_result.get("valid")
    )
    total_tests = sum(len(entry["results"]) for entry in results)
    logger.info("Done: %d/%d tests valid", valid_count, total_tests)


if __name__ == "__main__":
    main()
