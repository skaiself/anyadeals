"""Coordinates all source scrapers. Resilient — one failure doesn't stop others."""

import logging
from sources import ALL_SCRAPERS

logger = logging.getLogger("researcher")


async def run_all_scrapers() -> list[dict]:
    """Run all registered scrapers, aggregate results. Failures are logged and skipped."""
    all_results = []
    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        try:
            results = await scraper.scrape()
            all_results.extend(results)
            logger.info("[%s] returned %d entries", scraper.name, len(results))
        except Exception as e:
            logger.error("[%s] failed: %s", scraper.name, e)
    logger.info("Total raw entries from all sources: %d", len(all_results))
    return all_results
