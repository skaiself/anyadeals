"""Tests for the rescue_backfill one-shot script."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import rescue_backfill


def _write_coupons(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "coupons.json"
    p.write_text(json.dumps(rows))
    return p


@pytest.mark.asyncio
async def test_rescue_rescues_newly_valid_codes(tmp_path, monkeypatch):
    coupons_path = _write_coupons(tmp_path, [
        {"code": "RESCUED1", "status": "invalid", "regions": [], "fail_count": 5,
         "notes": "", "source": "browser_validation", "discount": ""},
        {"code": "STILLBAD", "status": "invalid", "regions": [], "fail_count": 5,
         "notes": "", "source": "browser_validation", "discount": ""},
        {"code": "GOLD60", "status": "valid", "regions": ["us"], "fail_count": 0,
         "notes": "Min. order $60.", "source": "browser_validation", "discount": "10% off"},
    ])
    monkeypatch.setattr(rescue_backfill, "DATA_DIR", str(tmp_path))

    async def fake_validate_codes(codes, brand_notes_map=None, regions=None):
        assert set(codes) == {"RESCUED1", "STILLBAD"}
        return [
            {"code": "RESCUED1",
             "results": {"us": {"valid": True, "discount": "10% off", "min_cart": ""}}},
            {"code": "STILLBAD",
             "results": {"us": {"valid": False, "message": "Invalid code"}}},
        ]

    with patch.object(rescue_backfill, "validate_codes", side_effect=fake_validate_codes):
        summary = await rescue_backfill.run()

    rows = json.loads(coupons_path.read_text())
    by_code = {r["code"]: r for r in rows}

    assert by_code["RESCUED1"]["status"] in ("valid", "region_limited")
    assert by_code["RESCUED1"]["fail_count"] == 0
    assert by_code["RESCUED1"]["rescued_at"]
    assert by_code["STILLBAD"]["status"] == "invalid"
    assert by_code["GOLD60"]["status"] == "valid"  # untouched
    assert summary["rescued"] == 1
    assert summary["still_invalid"] == 1


@pytest.mark.asyncio
async def test_rescue_dry_run_does_not_mutate(tmp_path, monkeypatch):
    coupons_path = _write_coupons(tmp_path, [
        {"code": "RESCUED1", "status": "invalid", "regions": [], "fail_count": 5,
         "notes": "", "source": "browser_validation", "discount": ""},
    ])
    monkeypatch.setattr(rescue_backfill, "DATA_DIR", str(tmp_path))

    async def fake(*a, **kw):
        return [{"code": "RESCUED1",
                 "results": {"us": {"valid": True, "discount": "10% off", "min_cart": ""}}}]

    with patch.object(rescue_backfill, "validate_codes", side_effect=fake):
        summary = await rescue_backfill.run(dry_run=True)

    rows = json.loads(coupons_path.read_text())
    assert rows[0]["status"] == "invalid"  # unchanged
    preview = tmp_path / "coupons.rescue_preview.json"
    assert preview.exists()
    assert summary["dry_run"] is True
