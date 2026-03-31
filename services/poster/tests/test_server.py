import json
import os
import pytest
from httpx import AsyncClient, ASGITransport
from server import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
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
async def test_get_best_coupon_returns_most_recently_validated(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [
        {"code": "OLD1", "status": "valid", "last_validated": "2026-03-28T00:00:00Z",
         "discount": "10% off"},
        {"code": "GOLD60", "status": "valid", "last_validated": "2026-03-31T00:00:00Z",
         "discount": "20% off $60+"},
        {"code": "EXPIRED1", "status": "expired", "last_validated": "2026-03-31T12:00:00Z",
         "discount": "5% off"},
    ]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/best-coupon")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "GOLD60"


@pytest.mark.asyncio
async def test_get_best_coupon_returns_404_when_no_valid(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [{"code": "EXP1", "status": "expired", "last_validated": "2026-03-01T00:00:00Z"}]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/best-coupon")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_copy_stores_and_returns_success(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [
        {"code": "GOLD60", "status": "valid", "last_validated": "2026-03-31T00:00:00Z",
         "discount": "20% off $60+"},
    ]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))
    (tmp_path / "posts.json").write_text("[]")

    from server import state
    state["running"] = False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/copy", json={
            "coupon_code": "GOLD60",
            "copy_text": "Save 20% at iHerb with GOLD60! Stack with OFR0296. #iHerb #deals",
            "platform": "twitter",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["coupon_code"] == "GOLD60"


@pytest.mark.asyncio
async def test_post_copy_rejects_unknown_coupon(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [{"code": "GOLD60", "status": "valid", "last_validated": "2026-03-31T00:00:00Z"}]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/copy", json={
            "coupon_code": "NONEXISTENT",
            "copy_text": "Some copy",
            "platform": "twitter",
        })
    assert resp.status_code == 404
