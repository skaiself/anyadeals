import json
import os
import pytest
from json_writer import load_research_json, merge_research, write_research_json


def test_load_research_json_missing_file(tmp_path):
    path = str(tmp_path / "research.json")
    result = load_research_json(path)
    assert result == []


def test_load_research_json_existing(tmp_path):
    path = str(tmp_path / "research.json")
    data = [{"code": "TEST10", "source": "test"}]
    with open(path, "w") as f:
        json.dump(data, f)
    result = load_research_json(path)
    assert len(result) == 1
    assert result[0]["code"] == "TEST10"


def test_merge_research_new_code():
    existing = []
    new_codes = [
        {
            "code": "NEW25",
            "source": "hotdeals.com",
            "discovered_at": "2026-03-23T06:00:00Z",
            "raw_description": "25% off",
            "raw_context": "Found on homepage",
            "discount_type": "percentage",
            "discount_value": 25,
            "regions": ["us"],
            "expiry_date": None,
            "confidence": "high",
            "validation_status": "pending",
        }
    ]
    result = merge_research(existing, new_codes)
    assert len(result) == 1
    assert result[0]["code"] == "NEW25"


def test_merge_research_dedup():
    existing = [{"code": "OLD10", "source": "site-a.com", "discovered_at": "2026-03-20T00:00:00Z"}]
    new_codes = [{"code": "OLD10", "source": "site-b.com", "discovered_at": "2026-03-23T00:00:00Z"}]
    result = merge_research(existing, new_codes)
    assert len(result) == 1
    # Keeps existing entry, doesn't duplicate
    assert result[0]["source"] == "site-a.com"


def test_write_research_json_atomic(tmp_path):
    path = str(tmp_path / "research.json")
    data = [{"code": "X", "source": "test"}]
    write_research_json(data, path)
    assert os.path.exists(path)
    with open(path) as f:
        loaded = json.load(f)
    assert loaded == data
