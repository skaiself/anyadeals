import json
import os
from datetime import datetime, timezone


def merge_results(existing: list[dict], results: list[dict]) -> list[dict]:
    """Merge CSV-style validation results into existing coupons.json data."""
    now = datetime.now(timezone.utc).isoformat()
    coupon_map = {c["code"]: dict(c) for c in existing}

    for r in results:
        code = r["coupon_code"]
        region = r["region"]
        is_valid = r["valid"] == "true"

        if code in coupon_map:
            entry = coupon_map[code]
            if is_valid:
                entry["last_validated"] = now
                entry["fail_count"] = 0
                entry["status"] = "valid"
                entry["last_failed"] = None
                if region not in entry.get("regions", []):
                    entry.setdefault("regions", []).append(region)
                if r.get("discount_amount") and r.get("discount_type"):
                    amt = r["discount_amount"]
                    typ = r["discount_type"]
                    entry["discount"] = f"{amt}% off" if typ == "percentage" else f"${amt} off"
            else:
                entry["fail_count"] = entry.get("fail_count", 0) + 1
                entry["last_failed"] = now
                if entry["fail_count"] >= 3:
                    entry["status"] = "expired"
        else:
            is_pct = r.get("discount_type") == "percentage"
            amt = r.get("discount_amount", "")
            discount = f"{amt}% off" if is_pct and amt else f"${amt} off" if amt else ""
            new_entry = {
                "code": code,
                "type": "promo",
                "discount": discount,
                "regions": [region],
                "min_cart_value": 0,
                "status": "valid" if is_valid else "invalid",
                "first_seen": now[:10],
                "last_validated": now if is_valid else "",
                "last_failed": now if not is_valid else None,
                "fail_count": 0 if is_valid else 1,
                "source": "",
                "stackable_with_referral": False,
                "notes": "",
            }
            coupon_map[code] = new_entry

    return list(coupon_map.values())


def write_coupons_json(data: list[dict], path: str) -> None:
    """Write coupons data to JSON file atomically."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def load_coupons_json(path: str) -> list[dict]:
    """Load existing coupons.json or return empty list."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def load_research_codes(path: str) -> list[dict]:
    """Load research.json and return pending codes in config-coupon format.

    Returns list of dicts with keys: code, regions, min_cart_value, source.
    Only includes entries with validation_status == "pending".
    """
    if not os.path.exists(path):
        return []
    with open(path) as f:
        research = json.load(f)
    return [
        {
            "code": entry["code"],
            "regions": entry.get("regions", ["*"]),
            "min_cart_value": None,
            "source": entry.get("source", ""),
        }
        for entry in research
        if entry.get("validation_status") == "pending"
    ]


def update_research_status(research_path: str, results: list[dict]) -> None:
    """Update validation_status in research.json based on validation results."""
    if not os.path.exists(research_path):
        return
    with open(research_path) as f:
        research = json.load(f)

    status_map = {}
    for r in results:
        code = r["coupon_code"]
        if r["valid"] == "true":
            status_map[code] = "valid"
        elif r["valid"] == "false":
            status_map.setdefault(code, "invalid")
        else:
            status_map.setdefault(code, "error")

    for entry in research:
        if entry["code"] in status_map:
            entry["validation_status"] = status_map[entry["code"]]

    tmp_path = research_path + ".tmp"
    os.makedirs(os.path.dirname(research_path) or ".", exist_ok=True)
    with open(tmp_path, "w") as f:
        json.dump(research, f, indent=2, default=str)
    os.replace(tmp_path, research_path)
