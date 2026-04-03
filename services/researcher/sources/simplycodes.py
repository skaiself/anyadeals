"""Scraper for SimplyCodes iHerb page.

SimplyCodes shows verified coupon codes with discount descriptions.
Codes are typically in data attributes or visible text elements.
"""

import re
from sources.base import BaseScraper, logger
from sources.couponfollow import _strip_html, FALSE_POSITIVES

CODE_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')


class SimpleCodesScraper(BaseScraper):
    name = "simplycodes"
    url = "https://simplycodes.com/store/iherb.com"

    async def scrape(self) -> list[dict]:
        html = await self._fetch(self.url)
        if not html:
            return []

        results = []
        seen = set()

        # Split by coupon/offer card patterns
        cards = re.split(r'(?i)(?=coupon-code|promo-code|offer-card|data-code)', html)
        for card in cards:
            codes = CODE_PATTERN.findall(card[:500])
            for code in codes:
                if code in seen or code in FALSE_POSITIVES or len(code) < 4:
                    continue
                seen.add(code)

                # Extract description from nearby text
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
                    "raw_context": f"simplycodes.com code {code}",
                })

        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results
