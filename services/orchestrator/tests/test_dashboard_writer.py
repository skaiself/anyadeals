import json
import os
import pytest
from dashboard_writer import update_dashboard, load_dashboard, write_dashboard


def test_load_dashboard_missing(tmp_path):
    path = str(tmp_path / "dashboard.json")
    result = load_dashboard(path)
    assert "jobs" in result
    assert "stats" in result


def test_load_dashboard_existing(tmp_path):
    path = str(tmp_path / "dashboard.json")
    data = {"affiliate_code": "OFR0296", "jobs": {}, "stats": {}}
    with open(path, "w") as f:
        json.dump(data, f)
    result = load_dashboard(path)
    assert result["affiliate_code"] == "OFR0296"


def test_write_dashboard_atomic(tmp_path):
    path = str(tmp_path / "dashboard.json")
    data = {"jobs": {"test": {"status": "success"}}, "stats": {}}
    write_dashboard(data, path)
    with open(path) as f:
        loaded = json.load(f)
    assert loaded["jobs"]["test"]["status"] == "success"


@pytest.mark.asyncio
async def test_update_dashboard_records_success(tmp_path, monkeypatch):
    import dashboard_writer
    path = str(tmp_path / "dashboard.json")
    monkeypatch.setattr(dashboard_writer, "DATA_DIR", str(tmp_path))
    write_dashboard({"affiliate_code": "OFR0296", "jobs": {}, "stats": {}}, path)

    await update_dashboard("researcher", {"status": "success", "summary": {"codes_found": 5}})

    with open(path) as f:
        data = json.load(f)
    assert data["jobs"]["researcher"]["status"] == "success"
