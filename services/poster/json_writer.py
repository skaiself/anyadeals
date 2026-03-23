"""Read/write posts.json — log of all social media posts."""

import json
import os
import logging

logger = logging.getLogger("poster")


def load_posts_json(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def append_post(existing: list[dict], new_post: dict) -> list[dict]:
    """Append a new post entry. No dedup needed — each post is unique."""
    existing.append(new_post)
    return existing


def write_posts_json(data: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_path, path)
