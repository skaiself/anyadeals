import json
import os
from typing import Any


class ConfigError(Exception):
    pass


REQUIRED_TOP_KEYS = ["regions", "coupons", "defaults"]
REQUIRED_REGION_KEYS = ["proxy", "currency", "iherb_url", "locale_path"]
REQUIRED_DEFAULT_KEYS = [
    "min_cart_value",
    "timeout_seconds",
    "product_categories",
    "retry_delay_seconds",
]
REQUIRED_COUPON_KEYS = ["code", "regions", "min_cart_value"]


def load_config(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")

    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config: {e}")

    _validate(data)

    # Override proxy URLs from environment variables
    # Per-region: PROXY_URL_US, PROXY_URL_DE, etc. Fall back to PROXY_URL.
    default_proxy = os.environ.get("PROXY_URL")
    for region_key, region_data in data["regions"].items():
        region_proxy = os.environ.get(f"PROXY_URL_{region_key.upper()}")
        if region_proxy:
            region_data["proxy"] = region_proxy
        elif default_proxy:
            region_data["proxy"] = default_proxy

    return data


def _validate(data: dict) -> None:
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            raise ConfigError(f"Missing required top-level key: {key}")

    regions = data["regions"]
    if not regions:
        raise ConfigError("At least one region must be defined")

    for region_name, region_data in regions.items():
        for key in REQUIRED_REGION_KEYS:
            if key not in region_data:
                raise ConfigError(
                    f"Missing required key '{key}' in region '{region_name}'"
                )

    defaults = data["defaults"]
    for key in REQUIRED_DEFAULT_KEYS:
        if key not in defaults:
            raise ConfigError(f"Missing required defaults key: {key}")

    defined_regions = set(regions.keys())
    for i, coupon in enumerate(data["coupons"]):
        for key in REQUIRED_COUPON_KEYS:
            if key not in coupon:
                raise ConfigError(
                    f"Missing required key '{key}' in coupon index {i}"
                )
        for r in coupon["regions"]:
            if r != "*" and r not in defined_regions:
                raise ConfigError(
                    f"Coupon '{coupon['code']}' references unknown region: {r}"
                )
