"""Poster service — automated social media posting for iHerb coupon codes."""

import json
import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

logger = logging.getLogger("poster")
logging.basicConfig(level=logging.INFO)

state = {
    "healthy": True,
    "last_run": None,
    "last_error": None,
    "running": False,
    "last_result": None,
}

DATA_DIR = os.environ.get("DATA_DIR", "/data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Poster service starting")
    yield
    logger.info("Poster service shutting down")


app = FastAPI(title="Poster Service", lifespan=lifespan)


@app.get("/status")
def get_status():
    return {
        "healthy": state["healthy"],
        "last_run": state["last_run"],
        "last_error": state["last_error"],
        "running": state["running"],
    }


@app.get("/best-coupon")
def get_best_coupon():
    """Return the top valid coupon (most recently validated)."""
    data_dir = os.environ.get("DATA_DIR", "/data")
    coupons_path = os.path.join(data_dir, "coupons.json")
    if not os.path.exists(coupons_path):
        raise HTTPException(status_code=404, detail="No coupons file found")
    with open(coupons_path) as f:
        coupons = json.load(f)
    valid = [c for c in coupons if c.get("status") == "valid"]
    if not valid:
        raise HTTPException(status_code=404, detail="No valid coupons")
    best = max(valid, key=lambda c: c.get("last_validated", ""))
    return best


@app.post("/run")
async def run_posting(platform: str = "all"):
    """Run posting. platform: 'twitter', 'reddit', or 'all'."""
    if state["running"]:
        raise HTTPException(status_code=409, detail="Posting already running")

    state["running"] = True
    start_time = datetime.now(timezone.utc)
    try:
        from json_writer import load_posts_json, append_post, write_posts_json

        # Load valid coupons
        coupons_path = os.path.join(DATA_DIR, "coupons.json")
        with open(coupons_path) as f:
            coupons = json.load(f)
        valid_coupons = [c for c in coupons if c.get("status") == "valid"]

        if not valid_coupons:
            return {"status": "success", "summary": {"posts_created": 0, "reason": "no valid coupons"}}

        best = max(valid_coupons, key=lambda c: c.get("last_validated", ""))

        from copy_generator import generate_copy
        copy_text = await generate_copy(best)

        from image_generator import generate_image
        image_path = await generate_image(best)

        posts_created = 0
        posts_path = os.path.join(DATA_DIR, "posts.json")
        existing_posts = load_posts_json(posts_path)

        # Post to Twitter (if platform is 'all' or 'twitter')
        if platform in ("all", "twitter"):
            try:
                from twitter_poster import TwitterPoster, create_tweet
                twitter = TwitterPoster()
                tweet_text = create_tweet(best, copy_text=copy_text)
                post_meta = twitter.post(tweet_text, image_path=image_path)
                post_meta["coupon_code"] = best["code"]
                existing_posts = append_post(existing_posts, post_meta)
                posts_created += 1
            except ValueError:
                logger.info("Twitter credentials not configured, skipping")
            except Exception as e:
                logger.error("Twitter posting failed: %s", e)

        # Post to Reddit (if platform is 'all' or 'reddit')
        if platform in ("all", "reddit"):
            try:
                from reddit_poster import RedditPoster
                reddit = RedditPoster()
                post_meta = reddit.post(best, copy_text=copy_text)
                existing_posts = append_post(existing_posts, post_meta)
                posts_created += 1
            except ValueError:
                logger.info("Reddit credentials not configured, skipping")
            except Exception as e:
                logger.error("Reddit posting failed: %s", e)

        write_posts_json(existing_posts, posts_path)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        summary = {"posts_created": posts_created, "coupon_promoted": best["code"]}

        state["last_run"] = datetime.now(timezone.utc).isoformat()
        state["last_error"] = None
        state["healthy"] = True
        state["last_result"] = summary

        return {"status": "success", "duration_seconds": round(duration, 1), "summary": summary}

    except Exception as e:
        state["last_error"] = str(e)
        state["healthy"] = False
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        logger.exception("Posting run failed")
        return {"status": "failure", "error": str(e)}
    finally:
        state["running"] = False
