import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_status_endpoint():
    # Import here to avoid scheduler startup issues in tests
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATA_DIR", "/tmp")
        from server import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "healthy" in data


@pytest.mark.asyncio
async def test_api_raw_codes_proxies_to_researcher(monkeypatch):
    import httpx

    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json=[{"code": "GOLD60"}])

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATA_DIR", "/tmp")
        from server import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/raw-codes")
        assert resp.status_code == 200
        assert resp.json() == [{"code": "GOLD60"}]


@pytest.mark.asyncio
async def test_api_best_coupon_proxies_to_poster(monkeypatch):
    import httpx

    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"code": "GOLD60", "discount": "20% off"})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATA_DIR", "/tmp")
        from server import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/best-coupon")
        assert resp.status_code == 200
        assert resp.json()["code"] == "GOLD60"
