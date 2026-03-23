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
