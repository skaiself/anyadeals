import json
import os
import pytest
from httpx import AsyncClient, ASGITransport
from server import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data
    assert "running" in data
    assert data["healthy"] is True


@pytest.mark.asyncio
async def test_run_returns_409_when_already_running():
    from server import state
    state["running"] = True
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/run")
        assert resp.status_code == 409
    finally:
        state["running"] = False


@pytest.mark.asyncio
async def test_get_raw_codes_returns_latest_entries(data_dir):
    raw = [
        {"code": "GOLD60", "source": "retailmenot", "raw_description": "20% off $60+"},
        {"code": "WELLNESS2026", "source": "couponbirds", "raw_description": "15% off wellness"},
    ]
    (data_dir / "raw_codes.json").write_text(json.dumps(raw))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raw-codes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["code"] == "GOLD60"


@pytest.mark.asyncio
async def test_get_raw_codes_returns_empty_when_no_file(data_dir):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raw-codes")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_raw_codes_limits_to_50(data_dir):
    raw = [{"code": f"CODE{i}", "source": "test", "raw_description": ""} for i in range(80)]
    (data_dir / "raw_codes.json").write_text(json.dumps(raw))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raw-codes")
    assert resp.status_code == 200
    assert len(resp.json()) == 50
