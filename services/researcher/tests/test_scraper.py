import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scraper import run_all_scrapers


@pytest.mark.asyncio
async def test_run_all_scrapers_aggregates_results():
    mock_results = [
        {"code": "A1", "source": "mock1", "raw_description": "", "raw_context": ""},
        {"code": "A2", "source": "mock2", "raw_description": "", "raw_context": ""},
    ]

    with patch("scraper.ALL_SCRAPERS") as mock_scrapers:
        scraper1 = MagicMock()
        scraper1.return_value.scrape = AsyncMock(return_value=[mock_results[0]])
        scraper1.return_value.name = "mock1"
        scraper2 = MagicMock()
        scraper2.return_value.scrape = AsyncMock(return_value=[mock_results[1]])
        scraper2.return_value.name = "mock2"
        mock_scrapers.__iter__ = lambda self: iter([scraper1, scraper2])

        results = await run_all_scrapers()
        assert len(results) == 2


@pytest.mark.asyncio
async def test_run_all_scrapers_handles_failure():
    """If one scraper throws, others still run."""
    with patch("scraper.ALL_SCRAPERS") as mock_scrapers:
        scraper1 = MagicMock()
        scraper1.return_value.scrape = AsyncMock(side_effect=Exception("boom"))
        scraper1.return_value.name = "failing"
        scraper2 = MagicMock()
        scraper2.return_value.scrape = AsyncMock(return_value=[{"code": "OK", "source": "s"}])
        scraper2.return_value.name = "working"
        mock_scrapers.__iter__ = lambda self: iter([scraper1, scraper2])

        results = await run_all_scrapers()
        assert len(results) == 1
        assert results[0]["code"] == "OK"
