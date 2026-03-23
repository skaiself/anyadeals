import json
import pytest
from unittest.mock import AsyncMock, patch
from claude_parser import parse_and_deduplicate, _fallback_parse


def test_fallback_parse_extracts_fields():
    raw = [
        {"code": "SAVE25", "source": "hotdeals", "raw_description": "25% off first order", "raw_context": "Valid for new customers"},
        {"code": "GOLD60", "source": "couponfollow", "raw_description": "20% off over $60", "raw_context": ""},
    ]
    result = _fallback_parse(raw)
    assert len(result) == 2
    assert result[0]["code"] == "SAVE25"
    assert result[0]["validation_status"] == "pending"
    assert result[0]["source"] == "hotdeals"


def test_fallback_parse_deduplicates():
    raw = [
        {"code": "SAME10", "source": "site-a", "raw_description": "", "raw_context": ""},
        {"code": "SAME10", "source": "site-b", "raw_description": "", "raw_context": ""},
    ]
    result = _fallback_parse(raw)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_parse_and_deduplicate_uses_fallback_on_cli_failure():
    raw = [{"code": "TEST5", "source": "test", "raw_description": "5% off", "raw_context": ""}]
    with patch("claude_parser._run_claude_cli", new_callable=AsyncMock) as mock_cli:
        mock_cli.side_effect = Exception("CLI not found")
        result = await parse_and_deduplicate(raw)
    assert len(result) == 1
    assert result[0]["code"] == "TEST5"


@pytest.mark.asyncio
async def test_parse_and_deduplicate_uses_claude_output():
    raw = [{"code": "RAW1", "source": "test", "raw_description": "", "raw_context": ""}]
    claude_output = [
        {
            "code": "RAW1",
            "source": "test",
            "discovered_at": "2026-03-23T06:00:00Z",
            "raw_description": "Cleaned description",
            "raw_context": "",
            "discount_type": "percentage",
            "discount_value": 10,
            "regions": ["us"],
            "expiry_date": None,
            "confidence": "medium",
            "validation_status": "pending",
        }
    ]
    with patch("claude_parser._run_claude_cli", new_callable=AsyncMock) as mock_cli:
        mock_cli.return_value = claude_output
        result = await parse_and_deduplicate(raw)
    assert len(result) == 1
    assert result[0]["discount_type"] == "percentage"
