"""Generic scraper for additional coupon sites — configurable URL list."""

import re
from sources.base import BaseScraper, logger
from parsers.code_filter import filter_results, is_false_positive


class GenericScraper(BaseScraper):
    name = "generic"
    url = ""

    URLS = [
        "https://www.rakuten.com/shop/iherb",
        "https://www.savings.com/coupons/iherb.com",
        "https://www.groupon.com/coupons/iherb",
        "https://www.marieclaire.com/coupons/iherb.com",
        # Blocked/broken — kept for reference:
        # "https://www.worthepenny.com/coupons/iherb",     # 403
        # "https://www.coupons.com/coupon-codes/iherb.com" # 404
        # "https://www.couponcabin.com/coupons/iherb/"     # 403
        # German sites moved to GutscheinScraper (need Playwright to reveal codes)
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
                    if code in seen or is_false_positive(code):
                        continue
                    seen.add(code)
                    context = block[:200].strip()
                    results.append({
                        "code": code,
                        "source": url,
                        "raw_description": "",
                        "raw_context": context,
                    })

        results = filter_results(results)
        logger.info("[%s] Found %d potential codes from %d sites", self.name, len(results), len(self.URLS))
        return results
