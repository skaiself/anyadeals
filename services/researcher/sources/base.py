"""Base class for all coupon source scrapers."""

import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger("researcher")


class BaseScraper(ABC):
    """All scrapers must define name, url, and implement scrape()."""

    name: str = ""
    url: str = ""

    def __init__(self):
        if not self.name:
            raise TypeError("Scraper must define 'name'")

    @abstractmethod
    async def scrape(self) -> list[dict]:
        """Return list of raw code entries: {code, source, raw_description, raw_context}."""
        ...

    async def _fetch(self, url: str, headers: dict | None = None) -> str:
        """Fetch a URL with httpx, return body text. Returns '' on error."""
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        }
        if headers:
            default_headers.update(headers)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers=default_headers)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            logger.warning("[%s] Failed to fetch %s: %s", self.name, url, e)
            return ""
