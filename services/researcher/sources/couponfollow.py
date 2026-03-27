"""Scraper for CouponFollow iHerb page."""

import re
from sources.base import BaseScraper, logger

# Strip HTML tags to get readable text
TAG_RE = re.compile(r'<[^>]+>')
WHITESPACE_RE = re.compile(r'\s+')


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    return WHITESPACE_RE.sub(' ', TAG_RE.sub(' ', text)).strip()


class CouponFollowScraper(BaseScraper):
    name = "couponfollow"
    url = "https://couponfollow.com/site/iherb.com"

    async def scrape(self) -> list[dict]:
        html = await self._fetch(self.url)
        if not html:
            return []

        results = []
        code_pattern = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')
        blocks = re.split(r'(?i)(?=coupon|promo|code|discount|%\s*off|\$\s*off)', html)

        seen = set()
        for block in blocks:
            codes = code_pattern.findall(block[:500])
            for code in codes:
                if code in seen or len(code) < 4:
                    continue
                if code in ("HTTP", "HTML", "HEAD", "BODY", "META", "LINK", "NONE", "TRUE", "FALSE", "NULL"):
                    continue
                seen.add(code)
                context = block[:500].strip()
                description = _strip_html(context)[:200]
                results.append({
                    "code": code,
                    "source": self.name,
                    "raw_description": description,
                    "raw_context": context[:200],
                })

        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results
