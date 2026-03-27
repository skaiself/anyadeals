"""Scraper for Reddit iHerb-related subreddits (read-only, no auth needed).

Uses Reddit's public JSON API: append .json to any subreddit URL.
Requires a custom User-Agent or Reddit returns 429/403.
"""

import re
import httpx
import logging

from sources.base import BaseScraper

logger = logging.getLogger("researcher")

# Codes must be 4-20 uppercase alphanumeric, starting with a letter
CODE_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')

# Common false positives from Reddit JSON/HTML
FALSE_POSITIVES = frozenset({
    "HTTP", "HTML", "HEAD", "BODY", "META", "LINK", "NONE",
    "TRUE", "FALSE", "NULL", "JSON", "SELF", "POST", "NSFW",
    "REDDIT", "SUBREDDIT", "COMMENT", "HTTPS", "HREF", "TITLE",
    "IHERB", "HERB", "VITAMIN", "PROMO", "CODE", "COUPON",
    "EDIT", "UPDATE", "DELETED", "REMOVED", "TLDR", "NBSP",
    "IMGUR", "JPEG", "WEBP",
})


class RedditScraper(BaseScraper):
    name = "reddit"
    url = "https://www.reddit.com"

    SUBREDDITS = ["iherb", "Supplements", "herbalism", "SkincareAddiction"]
    SORTS = ["new", "hot"]
    SEARCH_QUERIES = ["iherb promo code", "iherb coupon", "iherb discount code"]

    async def scrape(self) -> list[dict]:
        results = []
        seen = set()

        async with httpx.AsyncClient(
            headers={"User-Agent": "anyadeals-researcher/1.0"},
            timeout=30,
            follow_redirects=True,
        ) as client:
            # Browse subreddit listings
            for sub in self.SUBREDDITS:
                for sort in self.SORTS:
                    posts = await self._fetch_posts(client, f"/r/{sub}/{sort}.json?limit=25")
                    self._extract_codes(posts, f"reddit/r/{sub}", seen, results)

            # Search for iHerb codes across all subreddits
            for query in self.SEARCH_QUERIES:
                posts = await self._fetch_posts(
                    client,
                    f"/search.json?q={query}&sort=new&t=week&limit=25",
                )
                self._extract_codes(posts, "reddit/search", seen, results)

        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results

    async def _fetch_posts(self, client: httpx.AsyncClient, path: str) -> list[dict]:
        """Fetch posts from a Reddit JSON endpoint."""
        url = f"https://www.reddit.com{path}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("children", [])
        except Exception as e:
            logger.warning("[%s] Failed to fetch %s: %s", self.name, path, e)
            return []

    def _extract_codes(
        self,
        posts: list[dict],
        source: str,
        seen: set,
        results: list[dict],
    ) -> None:
        """Extract coupon codes from Reddit post data."""
        for post in posts:
            d = post.get("data", {})
            title = d.get("title", "")
            body = d.get("selftext", "")
            text = f"{title} {body}"

            # Only process posts that mention iHerb
            if "iherb" not in text.lower():
                continue

            codes = CODE_PATTERN.findall(text)
            for code in codes:
                if code in seen or code in FALSE_POSITIVES:
                    continue
                seen.add(code)
                results.append({
                    "code": code,
                    "source": source,
                    "raw_description": title[:200],
                    "raw_context": body[:300] if body else title[:300],
                })
