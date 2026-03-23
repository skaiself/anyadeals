import pytest
from unittest.mock import MagicMock, patch
from twitter_poster import create_tweet, TwitterPoster


def test_create_tweet_content():
    coupon = {
        "code": "GOLD60",
        "discount": "20% off orders over $60",
        "status": "valid",
    }
    tweet = create_tweet(coupon, copy_text="Save big on supplements!")
    assert tweet == "Save big on supplements!"


def test_create_tweet_default():
    coupon = {
        "code": "GOLD60",
        "discount": "20% off orders over $60",
        "status": "valid",
    }
    tweet = create_tweet(coupon)
    assert "GOLD60" in tweet
    assert "OFR0296" in tweet


def test_twitter_poster_init_from_env():
    env = {
        "TWITTER_API_KEY": "key",
        "TWITTER_API_SECRET": "secret",
        "TWITTER_ACCESS_TOKEN": "token",
        "TWITTER_ACCESS_SECRET": "tsecret",
    }
    with patch.dict("os.environ", env):
        with patch("twitter_poster.tweepy") as mock_tweepy:
            poster = TwitterPoster()
            assert poster.api_key == "key"


def test_twitter_poster_raises_without_credentials():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="TWITTER_API_KEY"):
            TwitterPoster()
