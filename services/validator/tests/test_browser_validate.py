"""Tests for browser_validate.merge_browser_results — especially fail_count threshold."""

from browser_validate import merge_browser_results


def _coupon(code, status="valid", regions=None, fail_count=0):
    return {
        "code": code,
        "type": "promo",
        "discount": "10% off",
        "regions": regions or ["us"],
        "min_cart_value": 0,
        "status": status,
        "first_seen": "2026-03-01",
        "last_validated": "2026-03-28T00:00:00Z",
        "last_failed": None,
        "fail_count": fail_count,
        "source": "test",
        "stackable_with_referral": False,
        "notes": "",
    }


def _result(code, valid_regions=None, invalid_regions=None):
    results = {}
    for r in (valid_regions or []):
        results[r] = {"valid": True, "discount": "10% off"}
    for r in (invalid_regions or []):
        results[r] = {"valid": False, "error": "not applicable"}
    return {"code": code, "results": results}


def test_single_failure_does_not_invalidate():
    """A valid coupon that fails once should NOT become invalid."""
    existing = [_coupon("GOLD60", status="valid", regions=["us", "de"])]
    browser = [_result("GOLD60", invalid_regions=["us"])]

    updated, _ = merge_browser_results(existing, browser)
    gold = next(c for c in updated if c["code"] == "GOLD60")

    assert gold["status"] == "valid"
    assert gold["fail_count"] == 1
    assert gold["regions"] == ["us", "de"]  # preserved from before


def test_two_failures_does_not_invalidate():
    """A coupon with 2 consecutive failures should still not be invalid."""
    existing = [_coupon("GOLD60", status="valid", regions=["us"], fail_count=1)]
    browser = [_result("GOLD60", invalid_regions=["us"])]

    updated, _ = merge_browser_results(existing, browser)
    gold = next(c for c in updated if c["code"] == "GOLD60")

    assert gold["status"] == "valid"
    assert gold["fail_count"] == 2


def test_three_failures_invalidates():
    """A coupon with 3 consecutive failures should become invalid."""
    existing = [_coupon("GOLD60", status="valid", regions=["us"], fail_count=2)]
    browser = [_result("GOLD60", invalid_regions=["us"])]

    updated, _ = merge_browser_results(existing, browser)
    gold = next(c for c in updated if c["code"] == "GOLD60")

    assert gold["status"] == "invalid"
    assert gold["fail_count"] == 3
    assert gold["regions"] == []


def test_valid_result_resets_fail_count():
    """A successful validation should reset fail_count to 0."""
    existing = [_coupon("GOLD60", status="valid", regions=["us"], fail_count=2)]
    browser = [_result("GOLD60", valid_regions=["us", "de"])]

    updated, _ = merge_browser_results(existing, browser)
    gold = next(c for c in updated if c["code"] == "GOLD60")

    assert gold["status"] == "valid"
    assert gold["fail_count"] == 0
    assert gold["regions"] == ["de", "us"]


def test_partial_regions_sets_region_limited():
    """Coupon valid in some regions but not all = region_limited."""
    existing = [_coupon("TEST1")]
    browser = [_result("TEST1", valid_regions=["us"], invalid_regions=["de", "gb"])]

    updated, _ = merge_browser_results(existing, browser)
    t = next(c for c in updated if c["code"] == "TEST1")

    assert t["status"] == "region_limited"
    assert t["fail_count"] == 0
    assert t["regions"] == ["us"]


def test_new_coupon_with_no_valid_regions():
    """A brand new coupon that fails all regions should start with fail_count=1, not invalid."""
    existing = []
    browser = [_result("NEW1", invalid_regions=["us"])]

    updated, _ = merge_browser_results(existing, browser)
    n = next(c for c in updated if c["code"] == "NEW1")

    assert n["status"] == "invalid"  # new codes get immediate status
    assert n["fail_count"] == 1
