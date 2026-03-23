import pytest
from sources.base import BaseScraper


class MockScraper(BaseScraper):
    name = "mock"
    url = "https://example.com"

    async def scrape(self) -> list[dict]:
        return [{"code": "MOCK10", "source": self.name, "raw_description": "10% off", "raw_context": "test"}]


@pytest.mark.asyncio
async def test_base_scraper_interface():
    s = MockScraper()
    results = await s.scrape()
    assert len(results) == 1
    assert results[0]["code"] == "MOCK10"
    assert results[0]["source"] == "mock"


def test_base_scraper_requires_name():
    with pytest.raises(TypeError):
        BaseScraper()
