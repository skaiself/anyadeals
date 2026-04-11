"""Tests for the centralised code_filter module."""
from parsers.code_filter import (
    FALSE_POSITIVES,
    REFERRAL_PHRASES,
    is_false_positive,
    looks_like_referral,
    filter_results,
)


def test_false_positive_set_contains_known_junk():
    for junk in ("HTTP", "HTML", "NONE", "IHERB", "VITAMIN", "PROMO", "COUPON", "NBSP"):
        assert junk in FALSE_POSITIVES


def test_is_false_positive_case_insensitive():
    assert is_false_positive("http") is True
    assert is_false_positive("HTTP") is True
    assert is_false_positive("GOLD60") is False


def test_is_false_positive_rejects_short_codes():
    assert is_false_positive("AB") is True  # too short
    assert is_false_positive("ABC") is True  # still too short
    assert is_false_positive("ABCD") is False  # 4 is the minimum


def test_looks_like_referral_catches_my_code_phrase():
    assert looks_like_referral("Use my code ARWAOM for 5% off your first order") is True
    assert looks_like_referral("my referral link gives you a bonus") is True


def test_looks_like_referral_does_not_fire_on_plain_promos():
    assert looks_like_referral("Save 15% off your order with code GOLD60") is False
    assert looks_like_referral("Today's iHerb promo: 10% off sitewide") is False


def test_filter_results_drops_false_positive_codes():
    results = [
        {"code": "GOLD60", "raw_context": "Save 10% off"},
        {"code": "HTTP", "raw_context": "Save 10% off"},
        {"code": "ARWAOM", "raw_context": "use my code ARWAOM"},
        {"code": "CHI22", "raw_context": "iHerb promo codes April 2026"},
    ]
    kept = filter_results(results)
    kept_codes = {r["code"] for r in kept}
    assert kept_codes == {"GOLD60", "CHI22"}


def test_filter_results_tolerates_missing_raw_context():
    results = [{"code": "GOLD60"}]
    kept = filter_results(results)
    assert len(kept) == 1


def test_filter_results_preserves_original_fields():
    results = [{"code": "GOLD60", "source": "reddit", "raw_description": "10% off"}]
    kept = filter_results(results)
    assert kept[0] == results[0]
