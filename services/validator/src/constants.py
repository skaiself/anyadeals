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

# Direct product URLs (primary method — avoids search page, less bot detection)
# Cheap, popular products that are always in stock
DIRECT_PRODUCT_URLS = [
    "/pr/california-gold-nutrition-gold-c-usp-grade-vitamin-c-1-000-mg-60-veggie-capsules/61864",
    "/pr/california-gold-nutrition-vitamin-d3-125-mcg-5-000-iu-90-fish-gelatin-softgels/70316",
    "/pr/21st-century-calcium-magnesium-zinc-d3-90-tablets/10695",
    "/pr/california-gold-nutrition-omega-3-premium-fish-oil-100-fish-gelatin-softgels-1-100-mg-per-softgel/62118",
    "/pr/now-foods-vitamin-d3-k2-120-capsules/10056",
]

# Add to cart button on product detail pages (multiple selectors for locale variants)
PRODUCT_PAGE_ADD_TO_CART = '.btn-add-to-cart'
