"""Scraper for iHerb's official Sales and Offers page.

This is the primary source — iHerb's own promotions page lists active
deals and sometimes includes promo codes directly.
"""

import re
from sources.base import BaseScraper, logger
from sources.couponfollow import _strip_html
from parsers.code_filter import is_false_positive

CODE_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')


class IHerbOfficialScraper(BaseScraper):
    name = "iherb_official"
    url = "https://www.iherb.com/info/sales-and-offers"

    async def scrape(self) -> list[dict]:
        html = await self._fetch(self.url)
        if not html:
            return []

        results = []
        seen = set()

        # Look for promo code patterns — iHerb often shows codes in
        # banners, headings, or "Use code X" text
        code_mentions = re.finditer(
            r'(?i)(?:code|promo|coupon)\s*:?\s*([A-Z][A-Z0-9]{3,19})', html
        )
        for m in code_mentions:
            code = m.group(1).upper()
            if code in seen or is_false_positive(code):
                continue
            seen.add(code)
            # Get surrounding context
            start = max(0, m.start() - 200)
            end = min(len(html), m.end() + 200)
            context = _strip_html(html[start:end])
            results.append({
                "code": code,
                "source": self.name,
                "raw_description": context[:200],
                "raw_context": f"iherb.com official: {code}",
            })

        # Also scan for standalone codes near discount text
        blocks = re.split(r'(?i)(?=\d+%\s*off|\$\d+\s*off|save\s+\d)', html)
        for block in blocks:
            codes = CODE_PATTERN.findall(block[:500])
            for code in codes:
                if code in seen or is_false_positive(code):
                    continue
                seen.add(code)
                desc = _strip_html(block[:300])[:200]
                results.append({
                    "code": code,
                    "source": self.name,
                    "raw_description": desc,
                    "raw_context": f"iherb.com official: {code}",
                })

        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results
