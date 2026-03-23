# src/constants.py
"""
CSS selectors and UI identifiers for iHerb pages.
Centralized here for easy updates when iHerb changes their UI.
Last updated: 2026-03-23
"""

# Search
SEARCH_INPUT = '#txtSearch, input[name="kw"]'
SEARCH_SUBMIT = 'button[type="submit"], .iherb-header-search-button'

# Product listing
PRODUCT_CARD = '.product-card, .product-cell'
ADD_TO_CART_BUTTON = 'button[data-ga-event-action="addToCart"], .add-to-cart'

# Cart (checkout.iherb.com/cart)
CART_URL_PATH = "/cart"
# iHerb 2026: remove buttons use hashed CSS classes, use text-based selectors
CART_ITEM_REMOVE_TEXT = "Delete Product"
CART_REMOVE_ALL_TEXT = "Remove all"
# Legacy selector kept as fallback
CART_ITEM_REMOVE = '.cart-item-remove, .remove-item'
CART_EMPTY_TEXT = "Your Shopping Cart is Empty"
# Legacy selector kept as fallback
CART_EMPTY_INDICATOR = '.empty-cart, .cart-empty-message'

# Coupon (applied on cart page at checkout.iherb.com/cart)
COUPON_INPUT = '#coupon-input'
COUPON_APPLY_BUTTON = '#coupon-apply'
COUPON_ERROR_MESSAGE = "Please enter a valid promo or Rewards code."
COUPON_NOT_APPLIED_TEXT = "not applied"

# Anti-bot / CAPTCHA detection
# Only detect visible CAPTCHA challenges, not invisible background reCAPTCHA
CAPTCHA_INDICATOR = '.g-recaptcha:not([data-size="invisible"]), iframe[src*="hcaptcha"], #captcha-container, .captcha-challenge'

# Category search terms (used to build cart via search — fallback method)
CATEGORY_SEARCH_TERMS = {
    "vitamins": "vitamins",
    "supplements": "supplements",
    "beauty": "beauty products",
}

# Direct product IDs (used to add to cart via checkout.iherb.com API)
# Cheap, popular products that are always in stock
DIRECT_PRODUCT_IDS = [
    61864,   # California Gold Nutrition, Vitamin C, 60 caps (~$5.57)
    70316,   # California Gold Nutrition, Vitamin D3, 90 softgels (~$5.00)
    10695,   # 21st Century, Calcium Magnesium Zinc + D3, 90 tabs (~$4.50)
    62118,   # California Gold Nutrition, Omega-3, 100 softgels (~$8.00)
    10056,   # NOW Foods, Vitamin D3 + K2, 120 caps (~$12.00)
]
