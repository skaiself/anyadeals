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
