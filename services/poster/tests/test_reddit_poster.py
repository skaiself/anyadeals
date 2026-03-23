import pytest
from unittest.mock import patch
from reddit_poster import RedditPoster


def test_reddit_poster_raises_without_credentials():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="REDDIT_CLIENT_ID"):
            RedditPoster()


def test_reddit_poster_init_from_env():
    env = {
        "REDDIT_CLIENT_ID": "id",
        "REDDIT_CLIENT_SECRET": "secret",
        "REDDIT_USERNAME": "user",
        "REDDIT_PASSWORD": "pass",
    }
    with patch.dict("os.environ", env):
        with patch("reddit_poster.praw") as mock_praw:
            poster = RedditPoster()
            assert poster.subreddit_name == "iherb"
