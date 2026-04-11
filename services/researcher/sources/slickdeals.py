"""Scraper for SlickDeals iHerb promo codes page."""

import re
from sources.base import BaseScraper, logger
from sources.couponfollow import _strip_html
from parsers.code_filter import filter_results, is_false_positive

CODE_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')


class SlickDealsScraper(BaseScraper):
    name = "slickdeals"
    url = "https://slickdeals.net/promo-codes/iherb"

    async def scrape(self) -> list[dict]:
        html = await self._fetch(self.url)
        if not html:
            return []

        results = []
        seen = set()

        # SlickDeals shows codes in card/offer sections
        cards = re.split(r'(?i)(?=coupon|promo.*code|get.*code|show.*code)', html)
        for card in cards:
            codes = CODE_PATTERN.findall(card[:500])
            for code in codes:
                if code in seen or is_false_positive(code):
                    continue
                seen.add(code)

                text_chunks = re.findall(r'>([^<]{10,})<', card[:2000])
                desc = ""
                for chunk in text_chunks:
                    chunk = chunk.strip()
                    if re.search(r'\d+%|\$\d+', chunk) and re.search(r'(?i)off|save|discount', chunk):
                        desc = _strip_html(chunk)[:200]
                        break

                results.append({
                    "code": code,
                    "source": self.name,
                    "raw_description": desc,
                    "raw_context": f"slickdeals.net code {code}",
                })

        results = filter_results(results)
        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results
