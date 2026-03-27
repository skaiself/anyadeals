import json
import os
import tempfile
import pytest
from json_writer import merge_results, write_coupons_json, load_coupons_json, load_research_codes, update_research_status, parse_discount_from_text

def test_new_valid_coupon_added():
    existing = []
    results = [{"coupon_code": "TEST1", "region": "us", "valid": "true", "discount_amount": "20", "discount_type": "percentage"}]
    merged = merge_results(existing, results)
    assert len(merged) == 1
    assert merged[0]["code"] == "TEST1"
    assert merged[0]["status"] == "valid"

def test_existing_coupon_updated():
    existing = [{"code": "TEST1", "status": "valid", "regions": ["us"], "fail_count": 0, "last_validated": "2026-03-20T00:00:00Z"}]
    results = [{"coupon_code": "TEST1", "region": "us", "valid": "true", "discount_amount": "20", "discount_type": "percentage"}]
    merged = merge_results(existing, results)
    assert len(merged) == 1
    assert merged[0]["last_validated"] > "2026-03-20"

def test_failed_coupon_increments_fail_count():
    existing = [{"code": "TEST1", "status": "valid", "regions": ["us"], "fail_count": 0, "last_validated": "2026-03-20T00:00:00Z"}]
    results = [{"coupon_code": "TEST1", "region": "us", "valid": "false", "discount_amount": "", "discount_type": ""}]
    merged = merge_results(existing, results)
    assert merged[0]["fail_count"] == 1
    assert merged[0]["status"] == "valid"

def test_coupon_expires_after_3_failures():
    existing = [{"code": "TEST1", "status": "valid", "regions": ["us"], "fail_count": 2, "last_validated": "2026-03-20T00:00:00Z"}]
    results = [{"coupon_code": "TEST1", "region": "us", "valid": "false", "discount_amount": "", "discount_type": ""}]
    merged = merge_results(existing, results)
    assert merged[0]["fail_count"] == 3
    assert merged[0]["status"] == "expired"

def test_new_region_added_to_existing_coupon():
    existing = [{"code": "TEST1", "status": "valid", "regions": ["us"], "fail_count": 0, "last_validated": "2026-03-20T00:00:00Z"}]
    results = [{"coupon_code": "TEST1", "region": "de", "valid": "true", "discount_amount": "20", "discount_type": "percentage"}]
    merged = merge_results(existing, results)
    assert "de" in merged[0]["regions"]
    assert "us" in merged[0]["regions"]

def test_write_and_load_coupons_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "coupons.json")
        data = [{"code": "TEST1", "status": "valid"}]
        write_coupons_json(data, path)
        loaded = load_coupons_json(path)
        assert loaded == data

def test_load_missing_file_returns_empty():
    result = load_coupons_json("/nonexistent/path/coupons.json")
    assert result == []


# --- load_research_codes tests ---

def test_load_research_codes_returns_pending_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "research.json")
        research = [
            {"code": "AAA", "source": "site1", "regions": ["us"], "validation_status": "pending"},
            {"code": "BBB", "source": "site2", "regions": ["de"], "validation_status": "valid"},
            {"code": "CCC", "source": "site3", "regions": ["us", "de"], "validation_status": "pending"},
        ]
        with open(path, "w") as f:
            json.dump(research, f)
        codes = load_research_codes(path)
        assert len(codes) == 2
        assert codes[0]["code"] == "AAA"
        assert codes[1]["code"] == "CCC"

def test_load_research_codes_format():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "research.json")
        research = [
            {"code": "TEST1", "source": "couponfollow", "regions": ["us"], "validation_status": "pending",
             "discount_type": "unknown", "confidence": "low"},
        ]
        with open(path, "w") as f:
            json.dump(research, f)
        codes = load_research_codes(path)
        assert len(codes) == 1
        assert codes[0] == {"code": "TEST1", "regions": ["us"], "min_cart_value": None, "source": "couponfollow"}

def test_load_research_codes_missing_file():
    result = load_research_codes("/nonexistent/research.json")
    assert result == []

def test_load_research_codes_defaults_regions_to_wildcard():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "research.json")
        research = [{"code": "X", "validation_status": "pending"}]
        with open(path, "w") as f:
            json.dump(research, f)
        codes = load_research_codes(path)
        assert codes[0]["regions"] == ["*"]


# --- update_research_status tests ---

def test_update_research_status_marks_valid():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "research.json")
        research = [
            {"code": "A", "validation_status": "pending"},
            {"code": "B", "validation_status": "pending"},
        ]
        with open(path, "w") as f:
            json.dump(research, f)
        results = [
            {"coupon_code": "A", "valid": "true"},
            {"coupon_code": "B", "valid": "false"},
        ]
        update_research_status(path, results)
        with open(path) as f:
            updated = json.load(f)
        assert updated[0]["validation_status"] == "valid"
        assert updated[1]["validation_status"] == "invalid"

def test_update_research_status_valid_wins_over_error():
    """If a code is valid in one region and error in another, valid wins."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "research.json")
        research = [{"code": "A", "validation_status": "pending"}]
        with open(path, "w") as f:
            json.dump(research, f)
        results = [
            {"coupon_code": "A", "valid": "error"},
            {"coupon_code": "A", "valid": "true"},
        ]
        update_research_status(path, results)
        with open(path) as f:
            updated = json.load(f)
        assert updated[0]["validation_status"] == "valid"

def test_update_research_status_missing_file_noop():
    update_research_status("/nonexistent/research.json", [{"coupon_code": "A", "valid": "true"}])


# --- parse_discount_from_text tests ---

def test_parse_percentage_discount():
    assert parse_discount_from_text("25% off your order") == ("25", "percentage")

def test_parse_percentage_no_off():
    assert parse_discount_from_text("Save 10%") == ("10", "percentage")

def test_parse_fixed_discount():
    assert parse_discount_from_text("$15 off orders over $50") == ("15", "fixed")

def test_parse_decimal_percentage():
    assert parse_discount_from_text("22.5% discount") == ("22.5", "percentage")

def test_parse_no_discount():
    assert parse_discount_from_text("Free shipping on all orders") == ("", "")

def test_parse_empty_string():
    assert parse_discount_from_text("") == ("", "")

def test_parse_none():
    assert parse_discount_from_text(None) == ("", "")

def test_parse_percentage_preferred_over_fixed():
    """When both patterns present, percentage match (earlier in text) wins."""
    assert parse_discount_from_text("20% off, save $10") == ("20", "percentage")


# --- merge_results with research fallback tests ---

def test_merge_uses_api_discount_when_available():
    results = [{"coupon_code": "X", "region": "us", "valid": "true", "discount_amount": "15", "discount_type": "percentage"}]
    merged = merge_results([], results)
    assert merged[0]["discount"] == "15% off"

def test_merge_falls_back_to_research_text():
    with tempfile.TemporaryDirectory() as tmpdir:
        rpath = os.path.join(tmpdir, "research.json")
        with open(rpath, "w") as f:
            json.dump([{"code": "SAVE20", "raw_description": "20% off sitewide", "raw_context": ""}], f)
        results = [{"coupon_code": "SAVE20", "region": "us", "valid": "true", "discount_amount": "", "discount_type": ""}]
        merged = merge_results([], results, research_path=rpath)
        assert merged[0]["discount"] == "20% off"

def test_merge_no_research_no_crash():
    results = [{"coupon_code": "X", "region": "us", "valid": "true", "discount_amount": "", "discount_type": ""}]
    merged = merge_results([], results, research_path=None)
    assert merged[0]["discount"] == ""

def test_merge_research_fills_source():
    with tempfile.TemporaryDirectory() as tmpdir:
        rpath = os.path.join(tmpdir, "research.json")
        with open(rpath, "w") as f:
            json.dump([{"code": "X", "source": "reddit/r/iherb", "raw_description": "", "raw_context": ""}], f)
        results = [{"coupon_code": "X", "region": "us", "valid": "true", "discount_amount": "10", "discount_type": "fixed"}]
        merged = merge_results([], results, research_path=rpath)
        assert merged[0]["source"] == "reddit/r/iherb"
