"""One-shot backfill: fill empty `discount` on active coupons in coupons.json.

Strategy, per coupon with status in {valid, region_limited} and empty discount:
  1. Try deterministic parsers (parse_discount_from_text on code/notes,
     parse_discount_from_code on the code name).
  2. If still empty, ask Claude CLI (haiku) to infer from code + source + notes.
  3. Write the result back, leaving everything else untouched.

Run:
  python3 services/validator/backfill_discounts.py \
    --coupons site/data/coupons.json \
    --research site/data/research.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from json_writer import parse_discount_from_code, parse_discount_from_text


AI_PROMPT = """You infer the iHerb promo code discount from its name, source, and any scraped notes.

Code: {code}
Source: {source}
Notes: {notes}

Common iHerb patterns:
- NEW-user codes (WELCOME7, WELCOME10, NEWCUSTOMER20): trailing/leading number is the percent
- GOLD60 / GOLD120: iHerb's loyalty tiers — 10% off $60+ / $120+ orders (always "10% off")
- MYAPP / MOBILE / APPNEW: mobile-app exclusive, usually "5% off" unless a number says otherwise
- Brand codes (STBEANSUK = St Francis Herb Farm etc.): typically "20% off brand"
- Anything with OFF/SAVE/PCT suffix: the number is the percent
- CAUTION: APR26, MAR26, CHI22, CANADA26 etc. may encode a DATE (year/month), NOT a discount — return "" if you cannot confirm the number is a discount

Reply with ONLY a JSON object, no prose:
  {{"discount": "10% off"}}   or
  {{"discount": "$5 off"}}    or
  {{"discount": ""}}          if you truly cannot tell.

Keep it short (max 25 chars). Do not invent specifics you cannot support."""


_MONTHS = re.compile(
    r'(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\d{2}', re.IGNORECASE
)
_YEAR_SUFFIX = re.compile(r'\D(\d{2})$')  # e.g. CHI22, GOCANADA26 — trailing 2-digit after letters


def _looks_like_date_code(code: str) -> bool:
    """Return True if any number in the code is likely a year/date, not a discount."""
    if _MONTHS.search(code):
        return True
    m = _YEAR_SUFFIX.search(code)
    if m:
        yr = int(m.group(1))
        if yr >= 20:  # 2020–2099 range — be conservative
            return True
    return False


def deterministic(code: str, notes: str) -> str:
    for text in (notes, code):
        amt, typ = parse_discount_from_text(text or "")
        if amt:
            return f"{amt}% off" if typ == "percentage" else f"${amt} off"
    if _looks_like_date_code(code):
        return ""
    amt, typ = parse_discount_from_code(code, "percentage")
    if amt:
        return f"{amt}% off"
    return ""


def ai_infer(code: str, source: str, notes: str) -> str:
    prompt = AI_PROMPT.format(code=code, source=source or "unknown", notes=notes or "(none)")
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--dangerously-skip-permissions",
             "--model", "haiku", "--output-format", "json"],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  [ai] {code}: {e}", file=sys.stderr)
        return ""
    if result.returncode != 0:
        print(f"  [ai] {code}: exit {result.returncode} stderr={result.stderr[:200]}", file=sys.stderr)
        return ""
    try:
        envelope = json.loads(result.stdout)
        body = envelope.get("result", "") if isinstance(envelope, dict) else ""
        # Body is the model's text; strip code fences if any.
        body = body.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        # Extract first {...} block, ignore any trailing prose
        m = re.search(r'\{[^}]*\}', body, re.DOTALL)
        body = m.group(0) if m else body
        parsed = json.loads(body)
        discount = parsed.get("discount", "") if isinstance(parsed, dict) else ""
        return discount[:30] if isinstance(discount, str) else ""
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [ai] {code}: parse failed ({e}) body={result.stdout[:200]}", file=sys.stderr)
        return ""


def load_research_sources(research_path: str) -> dict[str, str]:
    if not os.path.exists(research_path):
        return {}
    with open(research_path) as f:
        data = json.load(f)
    out: dict[str, str] = {}
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, dict) and "code" in entry:
            out[entry["code"]] = entry.get("source", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coupons", default="site/data/coupons.json")
    ap.add_argument("--research", default="site/data/research.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-ai", action="store_true", help="Skip Claude CLI step")
    args = ap.parse_args()

    with open(args.coupons) as f:
        doc: Any = json.load(f)
    coupons = doc["coupons"] if isinstance(doc, dict) and "coupons" in doc else doc

    sources = load_research_sources(args.research)

    targets = [
        c for c in coupons
        if c.get("status") in ("valid", "region_limited") and not c.get("discount")
    ]
    print(f"Active codes missing discount: {len(targets)}")

    filled = 0
    for c in targets:
        code = c["code"]
        notes = c.get("notes", "")
        source = sources.get(code, c.get("source", ""))

        guess = deterministic(code, notes)
        origin = "deterministic"
        if not guess and not args.no_ai:
            guess = ai_infer(code, source, notes)
            origin = "ai"
        if guess:
            print(f"  {code}: '{guess}'  ({origin}, source={source})")
            c["discount"] = guess
            filled += 1
        else:
            print(f"  {code}: UNRESOLVED  (source={source}, notes={notes!r})")

    print(f"\nFilled {filled}/{len(targets)} discounts.")

    if args.dry_run:
        print("--dry-run: not writing file.")
        return 0
    if filled:
        tmp = args.coupons + ".tmp"
        with open(tmp, "w") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, args.coupons)
        print(f"Wrote {args.coupons}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
