# src/constants.py
"""
CSS selectors and UI identifiers for iHerb pages.
Centralized here for easy updates when iHerb changes their UI.
"""

# Search
SEARCH_INPUT = '#txtSearch, input[name="kw"]'
SEARCH_SUBMIT = 'button[type="submit"], .iherb-header-search-button'

# Product listing
PRODUCT_CARD = '.product-card, .product-cell'
ADD_TO_CART_BUTTON = 'button[data-ga-event-action="addToCart"], .add-to-cart'

# Cart (checkout.iherb.com)
CART_URL_PATH = "/cart"
CART_ITEM_REMOVE = '.cart-item-remove, .remove-item'
CART_EMPTY_INDICATOR = '.empty-cart, .cart-empty-message'

# Coupon (applied on cart page, no checkout/login needed)
COUPON_INPUT = '#coupon-input'
COUPON_APPLY_BUTTON = '#coupon-apply'
COUPON_ERROR_MESSAGE = "Please enter a valid promo or Rewards code."
COUPON_NOT_APPLIED_TEXT = "not applied"

# Anti-bot / CAPTCHA detection
# Only detect visible CAPTCHA challenges, not invisible background reCAPTCHA
CAPTCHA_INDICATOR = '.g-recaptcha:not([data-size="invisible"]), iframe[src*="hcaptcha"], #captcha-container, .captcha-challenge'

# Category search terms (used to build cart)
CATEGORY_SEARCH_TERMS = {
    "vitamins": "vitamins",
    "supplements": "supplements",
    "beauty": "beauty products",
}
