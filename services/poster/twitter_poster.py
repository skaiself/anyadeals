"""Twitter/X posting via tweepy v2 API."""

import os
import logging
from datetime import datetime, timezone

import tweepy

logger = logging.getLogger("poster")

AFFILIATE_CODE = "OFR0296"
SITE_URL = "https://anyadeals.com/coupons/iherb/"


def create_tweet(coupon: dict, copy_text: str = "", image_path: str | None = None) -> str:
    """Format a tweet for a coupon code."""
    if copy_text:
        return copy_text
    code = coupon.get("code", "")
    discount = coupon.get("discount", "")
    return (
        f"Verified iHerb code: {code}\n"
        f"{discount}\n\n"
        f"Stack with referral code {AFFILIATE_CODE} for extra savings!\n\n"
        f"{SITE_URL}\n"
        f"#iHerb #supplements #deals"
    )


class TwitterPoster:
    def __init__(self):
        self.api_key = os.environ.get("TWITTER_API_KEY", "")
        self.api_secret = os.environ.get("TWITTER_API_SECRET", "")
        self.access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        self.access_secret = os.environ.get("TWITTER_ACCESS_SECRET", "")

        if not self.api_key:
            raise ValueError("TWITTER_API_KEY environment variable required")

        self.client = tweepy.Client(
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_secret,
        )
        auth = tweepy.OAuth1UserHandler(
            self.api_key, self.api_secret,
            self.access_token, self.access_secret,
        )
        self.api_v1 = tweepy.API(auth)

    def post(self, text: str, image_path: str | None = None) -> dict:
        """Post a tweet, optionally with an image. Returns post metadata."""
        media_ids = []
        if image_path and os.path.exists(image_path):
            try:
                media = self.api_v1.media_upload(image_path)
                media_ids = [media.media_id]
            except Exception as e:
                logger.warning("Failed to upload media: %s", e)

        try:
            response = self.client.create_tweet(
                text=text,
                media_ids=media_ids if media_ids else None,
            )
            tweet_id = response.data["id"]
            logger.info("Posted tweet %s", tweet_id)
            return {
                "id": f"tw_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "platform": "twitter",
                "content": text,
                "image_url": image_path or "",
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "tweet_id": tweet_id,
                "link": SITE_URL,
            }
        except tweepy.TooManyRequests:
            logger.warning("Twitter rate limit hit, deferring to next slot")
            raise
        except tweepy.TweepyException as e:
            logger.error("Twitter API error: %s", e)
            raise
