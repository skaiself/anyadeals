"""Unit tests for IHerbAPIValidator — all _curl calls are mocked."""
from unittest.mock import AsyncMock, patch

import pytest

from iherb_api_validator import (
    IHerbAPIValidator,
    CascadingFailure,
    ProxyQuotaExhausted,
)


@pytest.mark.asyncio
async def test_valid_code_type1_with_promo_echo():
    """200 + type=1 + promoCode echoes our code → valid, high confidence."""
    responses = [
        (200, {}),  # add_to_cart ok
        (200, {"appliedCouponCodeType": 1, "promoCode": "GOLD60",
               "couponDiscountPercent": 10}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("GOLD60")
    assert result["valid"] is True
    assert result["applied_type"] == 1
    assert result["discount_pct"] == 10
    assert result["confidence"] == "high"


@pytest.mark.asyncio
async def test_valid_code_type1_without_promo_echo_is_low_confidence():
    """200 + type=1 + missing promoCode → valid but low confidence."""
    responses = [
        (200, {}),
        (200, {"appliedCouponCodeType": 1, "promoCode": None}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("MYSTERY")
    assert result["valid"] is True
    assert result["confidence"] == "low"


@pytest.mark.asyncio
async def test_promo_echo_mismatch_is_rejected():
    """If iHerb echoes a *different* code than we sent, reject."""
    responses = [
        (200, {}),
        (200, {"appliedCouponCodeType": 1, "promoCode": "SOMETHING_ELSE"}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("GOLD60")
    assert result["valid"] is False
    assert "mismatch" in result["message"].lower()


@pytest.mark.asyncio
async def test_referral_type2_is_rejected():
    """200 + type=2 → referral code, rejected per OFR0296 policy."""
    responses = [
        (200, {}),
        (200, {"appliedCouponCodeType": 2, "promoCode": "RANDOM"}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("RANDOM")
    assert result["valid"] is False
    assert result["applied_type"] == 2
    assert "referral" in result["message"].lower()


@pytest.mark.asyncio
async def test_invalid_400_response():
    responses = [
        (200, {}),
        (400, {"message": "Invalid coupon code"}),
    ]
    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        result = await v.validate("FAKEINVALID999")
    assert result["valid"] is False
    assert result["http_code"] == 400


@pytest.mark.asyncio
async def test_transient_5xx_retries_then_succeeds():
    """First apply attempt 503, second attempt 200/valid."""
    call_count = {"n": 0}

    async def side_effect(*args, **kwargs):
        call_count["n"] += 1
        url = args[3] if len(args) >= 4 else kwargs.get("url", "")
        if "lineItems" in url:
            return (200, {})
        if call_count["n"] <= 2:  # first applyCoupon round
            return (503, {})
        return (200, {"appliedCouponCodeType": 1, "promoCode": "GOLD60"})

    v = IHerbAPIValidator()
    with patch.object(v, "_curl", AsyncMock(side_effect=side_effect)):
        result = await v.validate("GOLD60")
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_proxy_402_raises_quota_exhausted():
    responses = [(402, {})]
    v = IHerbAPIValidator(proxy_url="http://dummy")
    with patch.object(v, "_curl", AsyncMock(side_effect=responses)):
        with pytest.raises(ProxyQuotaExhausted):
            await v.validate("GOLD60")


@pytest.mark.asyncio
async def test_cascading_failure_after_ten_consecutive_transients():
    """10 consecutive transient failures in validate_many → CascadingFailure."""
    v = IHerbAPIValidator()

    async def always_transient(*a, **kw):
        return (503, {})

    with patch.object(v, "_curl", AsyncMock(side_effect=always_transient)):
        with pytest.raises(CascadingFailure):
            await v.validate_many([f"CODE{i}" for i in range(20)], {})
