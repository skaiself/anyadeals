"""Unit tests for the Stage-2 Playwright region validator.

The parse_cart_html function is pure — it takes an HTML string and the code
under test, and returns (eligible: bool, reason: str, discount: str | None).
We test it against fixtures, with no browser involved.
"""
from pathlib import Path

from iherb_region_validator import parse_cart_html, REGION_SCCODES, _build_iher_pref

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_autopromo_banner_does_not_contaminate_eligibility():
    """REGRESSION: the auto-promo banner must NOT be read as the code's result."""
    html = _load("cart_with_autopromo_banner.html")
    # Code being tested is TESTCODE123, not GOLD60 (banner mentions GOLD60).
    eligible, reason, discount = parse_cart_html(html, "TESTCODE123")
    assert eligible is True
    assert "GOLD60" not in reason


def test_autopromo_banner_extracts_discount():
    """When a code is applied, the discount percentage should be extracted."""
    html = _load("cart_with_autopromo_banner.html")
    eligible, reason, discount = parse_cart_html(html, "TESTCODE123")
    assert eligible is True
    assert discount == "10% off"


def test_ineligible_region_html_is_detected():
    html = _load("cart_ineligible_region.html")
    eligible, reason, discount = parse_cart_html(html, "EU15N")
    assert eligible is False
    assert "not eligible" in reason.lower()
    assert discount is None


def test_parse_cart_html_returns_false_when_no_confirmation():
    html = "<html><body><div>cart is empty</div></body></html>"
    eligible, reason, discount = parse_cart_html(html, "GOLD60")
    assert eligible is False
    assert "no apply confirmation" in reason.lower()
    assert discount is None


def test_parse_cart_html_empty_html():
    eligible, reason, discount = parse_cart_html("", "GOLD60")
    assert eligible is False
    assert "empty html" in reason.lower()
    assert discount is None


def test_region_sccodes_covers_all_23_regions():
    expected = {"us", "kr", "jp", "de", "gb", "au", "sa", "ca", "cn", "rs", "hr",
                "es", "pl",
                "it", "fr", "at", "nl", "se", "ch", "ie", "tw", "in", "hk"}
    assert expected.issubset(set(REGION_SCCODES.keys()))


def test_region_sccodes_values_are_uppercase_two_letter():
    for r, sc in REGION_SCCODES.items():
        assert len(sc) == 2 and sc.isupper(), f"{r} -> {sc}"


def test_rejected_not_applied_via_qa_element():
    """A warning-msg-promo with 'not applied' text must be classified as rejected."""
    html = '''
    <html><body>
      <div data-qa-element="warning-msg-promo">
        <span>GOLD60</span>
        <span>Promo code not applied to your cart.</span>
      </div>
    </body></html>
    '''
    eligible, reason, discount = parse_cart_html(html, "GOLD60")
    assert eligible is False
    assert "not applied" in reason.lower()


def test_script_tags_stripped_before_classification():
    """i18n bundle inside <script> tags must not trigger false rejection."""
    html = '''
    <html><body>
      <script>var i18n = {"msg": "Discount not applied to your region"};</script>
      <div data-qa-element="applied-promo">
        <span>GOLD60 applied</span>
      </div>
    </body></html>
    '''
    eligible, reason, discount = parse_cart_html(html, "GOLD60")
    assert eligible is True


def test_build_iher_pref_format():
    """The cookie value must be URL-encoded with %3D and %26 separators."""
    pref = _build_iher_pref("US")
    assert "sccode%3DUS" in pref
    assert "%26" in pref
    assert "=" not in pref
    assert "&" not in pref
