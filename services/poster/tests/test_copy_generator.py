import pytest
from unittest.mock import AsyncMock, patch
from copy_generator import generate_copy, _fallback_copy


def test_fallback_copy_includes_code():
    coupon = {"code": "SAVE25", "discount": "25% off"}
    text = _fallback_copy(coupon)
    assert "SAVE25" in text
    assert "OFR0296" in text


@pytest.mark.asyncio
async def test_generate_copy_uses_fallback_on_cli_failure():
    coupon = {"code": "TEST10", "discount": "10% off"}
    with patch("copy_generator._run_claude_cli", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("CLI not found")
        result = await generate_copy(coupon)
    assert "TEST10" in result
