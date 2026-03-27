"""Scraper for HotDeals iHerb page.

Splits page by "Get Code"/"Get Deal" buttons to isolate offer cards,
then extracts the code and its discount description from each card.
"""

import re
from sources.base import BaseScraper, logger
from sources.couponfollow import _strip_html

CODE_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')
FALSE_POSITIVES = frozenset({
    "HTTP", "HTML", "HEAD", "BODY", "META", "LINK", "NONE",
    "TRUE", "FALSE", "NULL", "HREF", "HTTPS", "NBSP", "CODE",
    "DOCTYPE", "FFFFFF", "SCRIPT",
})


class HotDealsScraper(BaseScraper):
    name = "hotdeals"
    url = "https://www.hotdeals.com/coupons/iherb/"

    async def scrape(self) -> list[dict]:
        html = await self._fetch(self.url)
        if not html:
            return []

        # Split by "Get Code" / "Get Deal" buttons — each split point
        # separates offer cards. The code appears right after the button,
        # the title/description appears in the preceding section.
        cards = re.split(r'Get (?:Code|Deal)', html)

        results = []
        seen = set()

        for i, card_after in enumerate(cards[1:], 1):
            card_before = cards[i - 1]

            # Code appears in the first ~200 chars after "Get Code"
            codes = CODE_PATTERN.findall(card_after[:200])
            codes = [c for c in codes if c not in FALSE_POSITIVES and len(c) >= 4]
            if not codes:
                continue
            code = codes[0]
            if code in seen:
                continue
            seen.add(code)

            # Title/description is in the preceding card section
            # Look for text with discount info (%, $, off, save)
            text_chunks = re.findall(r'>([^<]{10,})<', card_before[-2000:])
            title = ""
            for chunk in reversed(text_chunks):
                chunk = chunk.strip()
                # Skip stats lines like "237 used • Avg. Saved $27.03"
                if re.search(r'used\s*[•·]', chunk):
                    continue
                if re.search(r'\d+%|\$\d+', chunk) and re.search(r'(?i)off|save|discount', chunk):
                    title = _strip_html(chunk)
                    break

            results.append({
                "code": code,
                "source": self.name,
                "raw_description": title,
                "raw_context": f"hotdeals.com code {code}",
            })

        logger.info("[%s] Found %d potential codes", self.name, len(results))
        return results
