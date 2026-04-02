"""Process browser-based coupon validation results and update coupons.json.

Reads a JSON file of per-region browser validation results, merges them into
the existing coupons.json, and writes the file atomically (tmp + rename).
"""

import json
import os
import sys
from datetime import datetime, timezone

from json_writer import (
    load_coupons_json,
    parse_discount_from_text,
    write_coupons_json,
)


def load_browser_results(path: str) -> list[dict]:
    """Load browser validation results from a JSON file."""
    with open(path) as f:
        return json.load(f)


def merge_browser_results(existing: list[dict], browser_results: list[dict], research_notes: dict[str, str] | None = None) -> tuple[list[dict], list[str]]:
    """Merge browser validation results into existing coupons data.

    Args:
        research_notes: optional {code: notes} from research.json AI parsing.
            Used to populate notes for new coupons and fill empty notes on existing ones.

    Returns (updated_coupons, summary_lines).
    """
    research_notes = research_notes or {}
    now = datetime.now(timezone.utc).isoformat()
    coupon_map = {c["code"]: dict(c) for c in existing}
    summary: list[str] = []

    for item in browser_results:
        code = item["code"]
        results = item.get("results", {})

        valid_regions: list[str] = []
        invalid_regions: list[str] = []
        first_valid: dict | None = None

        for region, info in results.items():
            if info.get("valid"):
                valid_regions.append(region)
                if first_valid is None:
                    first_valid = info
            else:
                invalid_regions.append(region)

        # Determine status
        if valid_regions and invalid_regions:
            status = "region_limited"
        elif valid_regions:
            status = "valid"
        else:
            status = "invalid"

        # Resolve discount and min_cart from first valid result
        discount = ""
        min_cart_value = 0
        if first_valid:
            discount = first_valid.get("discount", "")
            min_cart_value = first_valid.get("min_cart", 0)
            # If discount text is empty, try parsing from code
            if not discount:
                amt, typ = parse_discount_from_text(code)
                if amt and typ == "percentage":
                    discount = f"{amt}% off"
                elif amt:
                    discount = f"${amt} off"

        if code in coupon_map:
            entry = coupon_map[code]
            old_status = entry.get("status", "")
            old_regions = entry.get("regions", [])

            if valid_regions:
                entry["regions"] = sorted(valid_regions)
                entry["status"] = status
                entry["last_validated"] = now
                entry["fail_count"] = 0
                entry["last_failed"] = None
                if discount:
                    entry["discount"] = discount
                if min_cart_value:
                    entry["min_cart_value"] = min_cart_value
                # Fill empty notes from AI-parsed research data
                if not entry.get("notes") and code in research_notes:
                    entry["notes"] = research_notes[code]
            else:
                entry["fail_count"] = entry.get("fail_count", 0) + 1
                entry["last_failed"] = now
                # Only invalidate after 3 consecutive failures to avoid
                # a single bad validation run wiping all coupons
                if entry["fail_count"] >= 3:
                    entry["status"] = "invalid"
                    entry["regions"] = []

            changes = []
            if old_status != entry["status"]:
                changes.append(f"status: {old_status} -> {entry['status']}")
            if sorted(old_regions) != entry["regions"]:
                changes.append(f"regions: {old_regions} -> {entry['regions']}")
            change_str = "; ".join(changes) if changes else "no change"
            summary.append(f"  {code}: {change_str}")
        else:
            new_entry = {
                "code": code,
                "type": "promo",
                "discount": discount,
                "regions": sorted(valid_regions),
                "min_cart_value": min_cart_value,
                "status": status,
                "first_seen": now[:10],
                "last_validated": now if valid_regions else "",
                "last_failed": now if not valid_regions else None,
                "fail_count": 0 if valid_regions else 1,
                "source": "browser_validation",
                "stackable_with_referral": False,
                "notes": research_notes.get(code, ""),
            }
            coupon_map[code] = new_entry
            summary.append(f"  {code}: NEW ({status}, regions={sorted(valid_regions)})")

    return list(coupon_map.values()), summary


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: browser_validate.py <browser_results.json>", file=sys.stderr)
        sys.exit(1)

    results_path = sys.argv[1]
    if not os.path.exists(results_path):
        print(f"Error: file not found: {results_path}", file=sys.stderr)
        sys.exit(1)

    data_dir = os.environ.get("DATA_DIR", "/data")
    coupons_path = os.path.join(data_dir, "coupons.json")

    browser_results = load_browser_results(results_path)
    existing = load_coupons_json(coupons_path)

    updated, summary = merge_browser_results(existing, browser_results)

    write_coupons_json(updated, coupons_path)

    print(f"Browser validation summary ({len(browser_results)} codes processed):")
    for line in summary:
        print(line)
    print(f"Wrote {len(updated)} coupons to {coupons_path}")


if __name__ == "__main__":
    main()
