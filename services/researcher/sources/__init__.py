from sources.iherb_official import IHerbOfficialScraper
from sources.couponfollow import CouponFollowScraper
from sources.simplycodes import SimpleCodesScraper
from sources.slickdeals import SlickDealsScraper
from sources.hotdeals import HotDealsScraper
from sources.reddit import RedditScraper
from sources.generic import GenericScraper

ALL_SCRAPERS = [
    IHerbOfficialScraper,   # Official iHerb sales page
    CouponFollowScraper,    # couponfollow.com
    SimpleCodesScraper,     # simplycodes.com
    SlickDealsScraper,      # slickdeals.net
    HotDealsScraper,        # hotdeals.com
    RedditScraper,          # Reddit subreddits + search
    GenericScraper,         # worthepenny, coupons.com, rakuten, couponcabin, savings, groupon, marieclaire
]
