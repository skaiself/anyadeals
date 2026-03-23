"""Scraper for Reddit iHerb-related subreddits (read-only, no auth needed)."""

import re
from sources.base import BaseScraper, logger


class RedditScraper(BaseScraper):
    name = "reddit"
    url = "https://www.reddit.com"

    SUBREDDITS = ["iherb", "supplements"]
    SEARCH_TERMS = ["iherb promo code", "iherb coupon", "iherb discount"]

    async def scrape(self) -> list[dict]:
        results = []
        seen = set()

        for sub in self.SUBREDDITS:
            for term in self.SEARCH_TERMS:
                url = f"https://www.reddit.com/r/{sub}/search.json?q={term}&sort=new&t=week&restrict_sr=1&limit=10"
                html = await self._fetch(url, headers={"Accept": "application/json"})
                if not html:
                    continue

                code_pattern = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')
                codes = code_pattern.findall(html)
                for code in codes:
                    if code in seen or len(code) < 4:
                        continue
                    if code in ("HTTP", "HTML", "HEAD", "BODY", "META", "LINK", "NONE",
                                "TRUE", "FALSE", "NULL", "JSON", "SELF", "POST",
                                "REDDIT", "SUBREDDIT", "COMMENT"):
                        continue
                    seen.add(code)
                    results.append({
                        "code": code,
                        "source": f"reddit/r/{sub}",
                        "raw_description": "",
                        "raw_context": f"Found in r/{sub} search for '{term}'",
                    })

        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results
