import json
import os
import tempfile
import pytest
from src.config import load_config, ConfigError


def _write_config(data: dict) -> str:
    """Write config dict to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


VALID_CONFIG = {
    "regions": {
        "us": {
            "proxy": "http://p:p@host:1",
            "currency": "USD",
            "iherb_url": "https://www.iherb.com",
            "locale_path": "",
        }
    },
    "coupons": [{"code": "TEST", "regions": ["us"], "min_cart_value": None}],
    "defaults": {
        "min_cart_value": 50,
        "timeout_seconds": 60,
        "product_categories": ["vitamins"],
        "retry_delay_seconds": 5,
    },
}


def test_load_valid_config():
    path = _write_config(VALID_CONFIG)
    cfg = load_config(path)
    assert len(cfg["coupons"]) == 1
    assert cfg["regions"]["us"]["currency"] == "USD"
    os.unlink(path)


def test_missing_regions_raises():
    data = {**VALID_CONFIG}
    del data["regions"]
    path = _write_config(data)
    with pytest.raises(ConfigError, match="regions"):
        load_config(path)
    os.unlink(path)


def test_unknown_region_in_coupon_raises():
    data = json.loads(json.dumps(VALID_CONFIG))
    data["coupons"] = [{"code": "X", "regions": ["jp"], "min_cart_value": None}]
    path = _write_config(data)
    with pytest.raises(ConfigError, match="jp"):
        load_config(path)
    os.unlink(path)


def test_wildcard_region_accepted():
    data = json.loads(json.dumps(VALID_CONFIG))
    data["coupons"] = [{"code": "X", "regions": ["*"], "min_cart_value": None}]
    path = _write_config(data)
    cfg = load_config(path)
    assert cfg["coupons"][0]["regions"] == ["*"]
    os.unlink(path)


def test_missing_file_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/config.json")


def test_coupon_min_cart_value_defaults():
    data = json.loads(json.dumps(VALID_CONFIG))
    data["coupons"] = [{"code": "X", "regions": ["us"], "min_cart_value": None}]
    path = _write_config(data)
    cfg = load_config(path)
    assert cfg["coupons"][0]["min_cart_value"] is None
    assert cfg["defaults"]["min_cart_value"] == 50
    os.unlink(path)
