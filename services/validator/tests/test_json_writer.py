import json
import os
import tempfile
import pytest
from json_writer import merge_results, write_coupons_json, load_coupons_json

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
