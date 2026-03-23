"""Read/write research.json with deduplication by coupon code."""

import json
import os
import logging

logger = logging.getLogger("researcher")


def load_research_json(path: str) -> list[dict]:
    """Load research.json, returning [] if file doesn't exist."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def merge_research(existing: list[dict], new_codes: list[dict]) -> list[dict]:
    """Merge new research entries into existing, dedup by code (keeps first seen)."""
    by_code = {entry["code"]: entry for entry in existing}
    for code_entry in new_codes:
        if code_entry["code"] not in by_code:
            by_code[code_entry["code"]] = code_entry
    return list(by_code.values())


def write_research_json(data: list[dict], path: str) -> None:
    """Atomic write of research.json (tmp + rename)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_path, path)
