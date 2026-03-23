"""Reddit posting via praw for iHerb coupon promotion."""

import os
import logging
from datetime import datetime, timezone

import praw

logger = logging.getLogger("poster")

AFFILIATE_CODE = "OFR0296"
SITE_URL = "https://anyadeals.com/coupons/iherb/"


class RedditPoster:
    def __init__(self, subreddit: str = "iherb"):
        self.client_id = os.environ.get("REDDIT_CLIENT_ID", "")
        self.client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
        self.username = os.environ.get("REDDIT_USERNAME", "")
        self.password = os.environ.get("REDDIT_PASSWORD", "")
        self.subreddit_name = subreddit

        if not self.client_id:
            raise ValueError("REDDIT_CLIENT_ID environment variable required")

        self.reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            username=self.username,
            password=self.password,
            user_agent=f"anyadeals-poster/1.0 (by /u/{self.username})",
        )

    def post(self, coupon: dict, copy_text: str = "") -> dict:
        """Post a coupon deal to the configured subreddit."""
        code = coupon.get("code", "")
        discount = coupon.get("discount", "")
        title = f"Verified iHerb Code: {code} — {discount}"

        body = copy_text or (
            f"Just verified this iHerb promo code: **{code}**\n\n"
            f"- Discount: {discount}\n"
            f"- Stack with referral code **{AFFILIATE_CODE}** for extra savings\n"
            f"- All codes verified at: {SITE_URL}\n\n"
            f"Codes are auto-checked daily. Check the link for the latest verified codes!"
        )

        try:
            subreddit = self.reddit.subreddit(self.subreddit_name)
            submission = subreddit.submit(title=title, selftext=body)
            logger.info("Posted to r/%s: %s", self.subreddit_name, submission.id)
            return {
                "id": f"rd_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "platform": "reddit",
                "content": body,
                "image_url": "",
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "coupon_code": code,
                "reddit_id": submission.id,
                "subreddit": self.subreddit_name,
                "link": SITE_URL,
            }
        except praw.exceptions.RedditAPIException as e:
            logger.error("Reddit API error: %s", e)
            raise
