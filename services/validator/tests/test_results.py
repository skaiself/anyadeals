import csv
import os
import tempfile
import pytest
from src.results import ResultsWriter, CouponResult


def test_csv_created_with_headers():
    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "test.csv")
        writer = ResultsWriter(csv_path, os.path.join(d, "screenshots"))
        writer.close()
        with open(csv_path) as f:
            reader = csv.reader(f)
            headers = next(reader)
        assert headers == [
            "coupon_code",
            "region",
            "valid",
            "discount_amount",
            "discount_type",
            "error_message",
            "timestamp",
        ]


def test_write_result_appends_row():
    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "test.csv")
        writer = ResultsWriter(csv_path, os.path.join(d, "screenshots"))
        result = CouponResult(
            coupon_code="SAVE10",
            region="us",
            valid="true",
            discount_amount="10.00",
            discount_type="percentage",
            error_message="",
        )
        writer.write_result(result)
        writer.close()
        with open(csv_path) as f:
            reader = csv.reader(f)
            next(reader)  # skip headers
            row = next(reader)
        assert row[0] == "SAVE10"
        assert row[1] == "us"
        assert row[2] == "true"


def test_save_screenshot():
    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "test.csv")
        ss_dir = os.path.join(d, "screenshots")
        writer = ResultsWriter(csv_path, ss_dir)
        # Simulate screenshot bytes
        path = writer.save_screenshot(b"\x89PNG", "SAVE10", "us")
        assert os.path.exists(path)
        assert "SAVE10" in path
        assert "us" in path
        writer.close()


def test_summary_counts():
    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "test.csv")
        writer = ResultsWriter(csv_path, os.path.join(d, "screenshots"))
        writer.write_result(CouponResult("A", "us", "true", "10", "fixed", ""))
        writer.write_result(CouponResult("B", "us", "false", "", "", "Invalid"))
        writer.write_result(CouponResult("C", "us", "error", "", "", "Timeout"))
        summary = writer.get_summary()
        assert summary == {"valid": 1, "invalid": 1, "errors": 1}
        writer.close()
