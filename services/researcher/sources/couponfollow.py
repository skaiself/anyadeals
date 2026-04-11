"""Scraper for CouponFollow iHerb page.

Extracts coupon codes from href anchors (#CODE pattern) and maps each
to its nearest offer title/description for discount text.
"""

import re
from sources.base import BaseScraper, logger
from parsers.code_filter import filter_results, is_false_positive

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

        # Strategy 1: Extract codes from href anchors (most reliable)
        # CouponFollow embeds full codes in URLs like /site/iherb.com#CODE
        href_codes = re.findall(
            r'couponfollow\.com/site/iherb\.com#([A-Z0-9]{4,20})', html
        )

        # Strategy 2: Extract offer titles — "Save 20% Off Your Order"
        titles = re.findall(
            r'class="[^"]*(?:offer|coupon)[^"]*title[^"]*"[^>]*>([^<]+)<',
            html, re.IGNORECASE,
        )

        # Build code → title mapping by position in HTML
        code_positions = [
            (m.start(), m.group(1))
            for m in re.finditer(
                r'couponfollow\.com/site/iherb\.com#([A-Z0-9]{4,20})', html
            )
        ]
        title_positions = [
            (m.start(), _strip_html(m.group(1)).strip())
            for m in re.finditer(
                r'class="[^"]*(?:offer|coupon)[^"]*title[^"]*"[^>]*>([^<]+)<',
                html, re.IGNORECASE,
            )
        ]

        results = []
        seen = set()

        for code_pos, code in code_positions:
            if code in seen or is_false_positive(code):
                continue
            seen.add(code)

            # Find the nearest title that appears before this code
            title = ""
            for title_pos, title_text in reversed(title_positions):
                if title_pos < code_pos:
                    title = title_text
                    break

            results.append({
                "code": code,
                "source": self.name,
                "raw_description": title,
                "raw_context": f"couponfollow.com/site/iherb.com#{code}",
            })

        # Fallback: regex scan for any codes missed by href extraction
        code_pattern = re.compile(r'\b([A-Z][A-Z0-9]{3,19})\b')
        blocks = re.split(r'(?i)(?=coupon|promo|code|discount|%\s*off|\$\s*off)', html)
        for block in blocks:
            codes = code_pattern.findall(block[:500])
            for code in codes:
                if code in seen or is_false_positive(code):
                    continue
                seen.add(code)
                description = _strip_html(block[:500])[:200]
                results.append({
                    "code": code,
                    "source": self.name,
                    "raw_description": description,
                    "raw_context": block[:200].strip(),
                })

        results = filter_results(results)
        logger.info("[%s] Found %d potential codes (%d from hrefs, %d from fallback)",
                    self.name, len(results), len(code_positions), len(results) - len(code_positions))
        return results
