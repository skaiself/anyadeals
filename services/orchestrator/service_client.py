"""HTTP client for calling other pipeline services."""

import logging

import httpx

logger = logging.getLogger("orchestrator")


class ServiceClient:
    """Calls a pipeline service's /run and /status endpoints."""

    def __init__(self, base_url: str, timeout: float = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def trigger_run(self) -> dict:
        """POST /run and return result. Raises on HTTP error."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/run")
            resp.raise_for_status()
            return resp.json()

    async def get_status(self) -> dict:
        """GET /status and return result."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.base_url}/status")
            resp.raise_for_status()
            return resp.json()

    async def is_healthy(self) -> bool:
        """Check if service is healthy and not currently running."""
        try:
            status = await self.get_status()
            return status.get("healthy", False) and not status.get("running", False)
        except Exception:
            return False
