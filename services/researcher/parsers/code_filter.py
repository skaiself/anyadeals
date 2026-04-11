"""Centralised false-positive and referral-phrase filter for scraped codes.

All scrapers in services/researcher/sources/ should call filter_results()
before returning, so junk tokens and personal referral codes never enter
the pipeline.
"""

FALSE_POSITIVES: frozenset[str] = frozenset({
    "HTTP", "HTML", "HEAD", "BODY", "META", "LINK", "NONE",
    "TRUE", "FALSE", "NULL", "JSON", "SELF", "POST", "NSFW",
    "REDDIT", "SUBREDDIT", "COMMENT", "HTTPS", "HREF", "TITLE",
    "IHERB", "HERB", "VITAMIN", "PROMO", "CODE", "COUPON",
    "EDIT", "UPDATE", "DELETED", "REMOVED", "TLDR", "NBSP",
    "IMGUR", "JPEG", "WEBP", "IFRAME", "CDATA",
})

REFERRAL_PHRASES: tuple[str, ...] = (
    "my code",
    "use my",
    "my referral",
    "my link",
    "my iherb",
    "new customer discount with",
    "first order with code",
    "first purchase with code",
)

MIN_CODE_LENGTH = 4


def is_false_positive(code: str) -> bool:
    """Return True if `code` is too short or belongs to the junk set."""
    if not code or len(code) < MIN_CODE_LENGTH:
        return True
    return code.upper() in FALSE_POSITIVES


def looks_like_referral(context: str) -> bool:
    """Return True if context text suggests a personal referral / affiliate code."""
    if not context:
        return False
    lowered = context.lower()
    return any(phrase in lowered for phrase in REFERRAL_PHRASES)


def filter_results(results: list[dict]) -> list[dict]:
    """Drop entries whose code is a false positive or whose context text
    triggers a referral phrase. The context text is `raw_context` if set,
    otherwise `raw_description` (scrapers use one or the other). Preserves
    all other fields and input ordering.
    """
    kept: list[dict] = []
    for r in results:
        code = r.get("code", "")
        if is_false_positive(code):
            continue
        context = r.get("raw_context", "") or r.get("raw_description", "")
        if looks_like_referral(context):
            continue
        kept.append(r)
    return kept
