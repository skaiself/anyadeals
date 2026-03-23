"""Generic scraper for additional coupon sites — configurable URL list."""

import re
from sources.base import BaseScraper, logger


class GenericScraper(BaseScraper):
    name = "generic"
    url = ""

    URLS = [
        "https://www.worthepenny.com/coupons/iherb",
        "https://www.coupons.com/coupon-codes/iherb.com",
    ]

    async def scrape(self) -> list[dict]:
        results = []
        seen = set()
        code_pattern = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')

        for url in self.URLS:
            html = await self._fetch(url)
            if not html:
                continue

            blocks = re.split(r'(?i)(?=coupon|promo|code|discount|%\s*off|\$\s*off)', html)
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
                        "source": url,
                        "raw_description": "",
                        "raw_context": context,
                    })

        logger.info("[%s] Found %d potential codes from %d sites", self.name, len(results), len(self.URLS))
        return results
