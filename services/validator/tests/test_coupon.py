import pytest
from src.coupon import parse_discount_type, parse_discount_amount


def test_parse_percentage_discount():
    assert parse_discount_type("-10%") == "percentage"
    assert parse_discount_type("Save 10%") == "percentage"


def test_parse_fixed_discount():
    assert parse_discount_type("-$10.00") == "fixed"
    assert parse_discount_type("-€5.00") == "fixed"


def test_parse_free_shipping():
    assert parse_discount_type("Free Shipping") == "free_shipping"
    assert parse_discount_type("free shipping applied") == "free_shipping"


def test_parse_unknown_discount():
    assert parse_discount_type("") == ""
    assert parse_discount_type("something weird") == ""


def test_parse_discount_amount():
    assert parse_discount_amount("-$10.00") == "10.00"
    assert parse_discount_amount("-10%") == "10"
    assert parse_discount_amount("Save 25.50%") == "25.50"
    assert parse_discount_amount("-€5.99") == "5.99"
    assert parse_discount_amount("") == ""
