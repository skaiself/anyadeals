"""Unit tests for the Stage-2 Playwright region validator.

The parse_cart_html function is pure — it takes an HTML string and the code
under test, and returns (eligible: bool, reason: str). We test it against
fixtures, with no browser involved.
"""
from pathlib import Path

from iherb_region_validator import parse_cart_html, REGION_SCCODES

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_autopromo_banner_does_not_contaminate_eligibility():
    """REGRESSION: the auto-promo banner must NOT be read as the code's result."""
    html = _load("cart_with_autopromo_banner.html")
    # Code being tested is TESTCODE123, not GOLD60 (banner mentions GOLD60).
    eligible, reason = parse_cart_html(html, "TESTCODE123")
    assert eligible is True
    assert "GOLD60" not in reason


def test_ineligible_region_html_is_detected():
    html = _load("cart_ineligible_region.html")
    eligible, reason = parse_cart_html(html, "EU15N")
    assert eligible is False
    assert "not eligible" in reason.lower() or "ineligible" in reason.lower()


def test_parse_cart_html_returns_false_when_applied_row_missing():
    html = "<html><body><div>cart is empty</div></body></html>"
    eligible, reason = parse_cart_html(html, "GOLD60")
    assert eligible is False
    assert "no applied" in reason.lower() or "not found" in reason.lower()


def test_region_sccodes_covers_all_21_regions():
    expected = {"us", "kr", "jp", "de", "gb", "au", "sa", "ca", "cn", "rs", "hr",
                "it", "fr", "at", "nl", "se", "ch", "ie", "tw", "in", "hk"}
    assert expected.issubset(set(REGION_SCCODES.keys()))


def test_region_sccodes_values_are_uppercase_two_letter():
    for r, sc in REGION_SCCODES.items():
        assert len(sc) == 2 and sc.isupper(), f"{r} → {sc}"


def test_parse_cart_html_rejects_novel_not_applied_reason():
    """REGRESSION: a 'Not applied: <novel reason>' message must NOT leak as eligible
    via the substring 'applied' fall-through. This locks in the prefix-check fix.
    """
    html = '''
    <section data-testid="applied-coupons">
      <div data-testid="applied-coupon-row" data-code="GOLD60">
        <span class="applied-coupon-status">Not applied: not available for loyalty members</span>
      </div>
    </section>
    '''
    eligible, reason = parse_cart_html(html, "GOLD60")
    assert eligible is False, f"novel 'Not applied' reason leaked as eligible: {reason}"
