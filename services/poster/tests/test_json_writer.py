import json
import os
import pytest
from json_writer import load_posts_json, append_post, write_posts_json


def test_load_posts_json_missing(tmp_path):
    path = str(tmp_path / "posts.json")
    assert load_posts_json(path) == []


def test_append_post():
    existing = []
    new_post = {
        "id": "tw_20260323_1",
        "platform": "twitter",
        "content": "Test tweet",
        "image_url": "",
        "posted_at": "2026-03-23T10:00:00Z",
        "coupon_code": "GOLD60",
        "link": "https://anyadeals.com/coupons/iherb/",
    }
    result = append_post(existing, new_post)
    assert len(result) == 1
    assert result[0]["id"] == "tw_20260323_1"


def test_write_posts_json_atomic(tmp_path):
    path = str(tmp_path / "posts.json")
    data = [{"id": "test", "platform": "twitter"}]
    write_posts_json(data, path)
    with open(path) as f:
        assert json.load(f) == data
