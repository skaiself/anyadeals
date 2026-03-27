import pytest
from sources.reddit import RedditScraper, CODE_PATTERN, FALSE_POSITIVES


def test_code_pattern_matches_valid_codes():
    text = "Use code JFF855 at checkout for SAVE20 discount"
    codes = CODE_PATTERN.findall(text)
    assert "JFF855" in codes
    assert "SAVE20" in codes


def test_code_pattern_rejects_short_codes():
    text = "Use AB at checkout"
    codes = CODE_PATTERN.findall(text)
    assert "AB" not in codes


def test_code_pattern_rejects_lowercase():
    text = "use code save20 at checkout"
    codes = CODE_PATTERN.findall(text)
    assert len(codes) == 0


def test_false_positives_filtered():
    assert "HTTP" in FALSE_POSITIVES
    assert "IHERB" in FALSE_POSITIVES
    assert "PROMO" in FALSE_POSITIVES
    assert "REDDIT" in FALSE_POSITIVES


def test_extract_codes_filters_non_iherb_posts():
    scraper = RedditScraper()
    posts = [{"data": {"title": "Great vitamin sale SAVE20", "selftext": "use code SAVE20"}}]
    results = []
    scraper._extract_codes(posts, "test", set(), results)
    assert len(results) == 0  # No "iherb" in text


def test_extract_codes_finds_codes_in_iherb_posts():
    scraper = RedditScraper()
    posts = [{"data": {"title": "iHerb promo code SAVE20", "selftext": "Use SAVE20 at checkout"}}]
    results = []
    scraper._extract_codes(posts, "reddit/r/iherb", set(), results)
    assert len(results) == 1
    assert results[0]["code"] == "SAVE20"
    assert results[0]["source"] == "reddit/r/iherb"


def test_extract_codes_deduplicates():
    scraper = RedditScraper()
    posts = [
        {"data": {"title": "iHerb code SAVE20", "selftext": ""}},
        {"data": {"title": "iHerb also SAVE20", "selftext": ""}},
    ]
    results = []
    seen = set()
    scraper._extract_codes(posts, "test", seen, results)
    assert len(results) == 1


def test_extract_codes_skips_false_positives():
    scraper = RedditScraper()
    posts = [{"data": {"title": "iHerb HTTP POST JSON", "selftext": ""}}]
    results = []
    scraper._extract_codes(posts, "test", set(), results)
    assert len(results) == 0


def test_extract_codes_preserves_context():
    scraper = RedditScraper()
    title = "Amazing iHerb discount with NEWCODE25"
    body = "Apply NEWCODE25 at checkout for 25% off your first order"
    posts = [{"data": {"title": title, "selftext": body}}]
    results = []
    scraper._extract_codes(posts, "reddit/r/iherb", set(), results)
    assert results[0]["raw_description"] == title
    assert body[:300] in results[0]["raw_context"]
