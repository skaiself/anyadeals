import json
import os
import re
from datetime import datetime, timezone


def parse_discount_from_text(text: str) -> tuple[str, str]:
    """Extract discount amount and type from descriptive text.

    Returns (amount, type) where type is "percentage" or "fixed".
    Returns ("", "") if no discount found.
    """
    if not text:
        return "", ""
    # Match patterns like "25% off", "25 percent", "25%"
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:off|discount)?', text, re.IGNORECASE)
    if pct_match:
        return pct_match.group(1), "percentage"
    # Match patterns like "$10 off", "$10 discount", "10 dollars off"
    fixed_match = re.search(r'\$\s*(\d+(?:\.\d+)?)\s*(?:off|discount)?', text, re.IGNORECASE)
    if fixed_match:
        return fixed_match.group(1), "fixed"
    return "", ""


def parse_discount_from_code(code: str, discount_type: str) -> tuple[str, str]:
    """Infer discount amount from the coupon code itself.

    Many iHerb codes embed the discount value: IHERB22OFF → 22%, NEW20 → 20%.
    Only trusts numbers that look like intentional discount values.

    Heuristics:
    - percentage: 5-50 (iHerb never offers 60%+ or tiny 1-4% via promo)
    - fixed: skip entirely (too ambiguous — RMB299 is a threshold, not a discount)
    - Numbers must be adjacent to discount-suggestive letters (OFF, SAVE, etc.)
      or be the only number in the code

    Returns (amount, type) or ("", "").
    """
    if not code or discount_type != "percentage":
        return "", ""
    # Look for number followed by OFF/SAVE/PCT or preceded by similar patterns
    m = re.search(r'(\d{1,2})(?:OFF|PCT|SAVE|DISC)', code, re.IGNORECASE)
    if m and 5 <= int(m.group(1)) <= 50:
        return m.group(1), "percentage"
    # If code ends with a number (e.g., NEW20, EU15N where N is minor suffix),
    # or starts with a number, use it. Reject numbers sandwiched between
    # letters (e.g., MAR26ANTI — likely a date, not a discount).
    numbers = re.findall(r'(\d+)', code)
    if len(numbers) == 1:
        num = int(numbers[0])
        if 5 <= num <= 50:
            # Check the number is at the start or end of the code (with optional 1-char suffix)
            if re.search(r'(\d+).?$', code) or re.match(r'\d+', code):
                return numbers[0], "percentage"
    return "", ""


def merge_results(existing: list[dict], results: list[dict],
                  research_path: str | None = None) -> list[dict]:
    """Merge CSV-style validation results into existing coupons.json data.

    If research_path is provided and a coupon has no discount from the API,
    falls back to parsing discount from the research entry's description/context.
    """
    now = datetime.now(timezone.utc).isoformat()
    coupon_map = {c["code"]: dict(c) for c in existing}

    # Load research data for fallback discount parsing
    research_by_code = {}
    if research_path and os.path.exists(research_path):
        with open(research_path) as f:
            for entry in json.load(f):
                research_by_code[entry["code"]] = entry

    for r in results:
        code = r["coupon_code"]
        region = r["region"]
        is_valid = r["valid"] == "true"

        # Resolve discount: API → research text → code name
        amt = r.get("discount_amount", "")
        typ = r.get("discount_type", "")
        if not amt and code in research_by_code:
            re_entry = research_by_code[code]
            text = f"{re_entry.get('raw_description', '')} {re_entry.get('raw_context', '')}"
            amt, typ = parse_discount_from_text(text)
        if not amt:
            code_typ = typ or r.get("discount_type", "")
            amt, typ = parse_discount_from_code(code, code_typ)
        if not typ and r.get("discount_type"):
            typ = r["discount_type"]

        if code in coupon_map:
            entry = coupon_map[code]
            if is_valid:
                entry["last_validated"] = now
                entry["fail_count"] = 0
                entry["status"] = "valid"
                entry["last_failed"] = None
                if region not in entry.get("regions", []):
                    entry.setdefault("regions", []).append(region)
                if amt and typ:
                    new_discount = f"{amt}% off" if typ == "percentage" else f"${amt} off"
                    if not entry.get("discount") or entry["discount"] != new_discount:
                        entry["discount"] = new_discount
            else:
                entry["fail_count"] = entry.get("fail_count", 0) + 1
                entry["last_failed"] = now
                if entry["fail_count"] >= 3:
                    entry["status"] = "expired"
        else:
            discount = f"{amt}% off" if typ == "percentage" and amt else f"${amt} off" if amt else ""
            source = research_by_code.get(code, {}).get("source", "")
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
                "source": source,
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
            "regions": ["*"],  # Always test in all configured regions
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
