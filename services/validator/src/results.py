import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class CouponResult:
    coupon_code: str
    region: str
    valid: str  # "true" | "false" | "error"
    discount_amount: str
    discount_type: str  # "percentage" | "fixed" | "free_shipping" | ""
    error_message: str


HEADERS = [
    "coupon_code",
    "region",
    "valid",
    "discount_amount",
    "discount_type",
    "error_message",
    "timestamp",
]


class ResultsWriter:
    def __init__(self, csv_path: str, screenshots_dir: str):
        self._csv_path = csv_path
        self._screenshots_dir = screenshots_dir
        self._counts = {"valid": 0, "invalid": 0, "errors": 0}

        os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
        os.makedirs(screenshots_dir, exist_ok=True)

        self._file = open(csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(HEADERS)
        self._file.flush()

    def write_result(self, result: CouponResult) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        self._writer.writerow([
            result.coupon_code,
            result.region,
            result.valid,
            result.discount_amount,
            result.discount_type,
            result.error_message,
            timestamp,
        ])
        self._file.flush()

        if result.valid == "true":
            self._counts["valid"] += 1
        elif result.valid == "false":
            self._counts["invalid"] += 1
        else:
            self._counts["errors"] += 1

    def save_screenshot(self, png_bytes: bytes, coupon_code: str, region: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{coupon_code}_{region}_{timestamp}.png"
        path = os.path.join(self._screenshots_dir, filename)
        with open(path, "wb") as f:
            f.write(png_bytes)
        return path

    def get_summary(self) -> dict[str, int]:
        return dict(self._counts)

    def close(self) -> None:
        self._file.close()
