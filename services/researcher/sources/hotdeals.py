"""Scraper for HotDeals iHerb page."""

import re
from sources.base import BaseScraper, logger


class HotDealsScraper(BaseScraper):
    name = "hotdeals"
    url = "https://www.hotdeals.com/coupons/iherb/"

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
                context = block[:200].strip()
                results.append({
                    "code": code,
                    "source": self.name,
                    "raw_description": "",
                    "raw_context": context,
                })

        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results
