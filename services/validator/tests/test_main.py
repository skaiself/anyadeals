# tests/test_main.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from main import expand_coupons, TransientError, ProxyError


VALID_CONFIG = {
    "regions": {
        "us": {
            "proxy": "http://p:p@host:1",
            "currency": "USD",
            "iherb_url": "https://www.iherb.com",
            "locale_path": "",
        },
        "de": {
            "proxy": "http://p:p@host:2",
            "currency": "EUR",
            "iherb_url": "https://www.iherb.com",
            "locale_path": "/?lc=de&rc=DE",
        },
    },
    "coupons": [
        {"code": "GLOBAL", "regions": ["*"], "min_cart_value": None},
        {"code": "USONLY", "regions": ["us"], "min_cart_value": 40},
    ],
    "defaults": {
        "min_cart_value": 50,
        "timeout_seconds": 60,
        "product_categories": ["vitamins"],
        "retry_delay_seconds": 5,
    },
}


def test_expand_coupons_wildcard():
    combos = expand_coupons(VALID_CONFIG)
    codes_regions = [(c["code"], r) for c, r in combos]
    assert ("GLOBAL", "us") in codes_regions
    assert ("GLOBAL", "de") in codes_regions
    assert ("USONLY", "us") in codes_regions
    assert ("USONLY", "de") not in codes_regions
    assert len(combos) == 3


def test_expand_coupons_specific_regions():
    config = {
        "regions": {"us": {}, "de": {}, "jp": {}},
        "coupons": [{"code": "A", "regions": ["us", "jp"], "min_cart_value": None}],
    }
    combos = expand_coupons(config)
    codes_regions = [(c["code"], r) for c, r in combos]
    assert ("A", "us") in codes_regions
    assert ("A", "jp") in codes_regions
    assert ("A", "de") not in codes_regions
