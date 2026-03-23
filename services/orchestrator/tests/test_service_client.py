import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from service_client import ServiceClient


@pytest.mark.asyncio
async def test_call_service_run():
    client = ServiceClient(base_url="http://researcher:8001")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "summary": {"codes_found": 3}}
    mock_response.raise_for_status = MagicMock()

    with patch("service_client.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.post = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_instance

        result = await client.trigger_run()
        assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_service_status():
    client = ServiceClient(base_url="http://validator:8002")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"healthy": True, "running": False}
    mock_response.raise_for_status = MagicMock()

    with patch("service_client.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_instance

        result = await client.get_status()
        assert result["healthy"] is True
