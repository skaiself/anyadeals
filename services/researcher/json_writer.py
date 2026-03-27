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
    """Merge new research entries into existing, dedup by code (keeps first seen).

    If an existing entry has an empty raw_description but the new entry has one,
    the description is updated (scrapers may improve over time).
    """
    by_code = {entry["code"]: entry for entry in existing}
    for code_entry in new_codes:
        code = code_entry["code"]
        if code not in by_code:
            by_code[code] = code_entry
        elif not by_code[code].get("raw_description") and code_entry.get("raw_description"):
            by_code[code]["raw_description"] = code_entry["raw_description"]
    return list(by_code.values())


def write_research_json(data: list[dict], path: str) -> None:
    """Atomic write of research.json (tmp + rename)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_path, path)
