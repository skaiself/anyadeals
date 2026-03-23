"""Integration test — requires Docker Compose stack running."""

import httpx
import pytest
import time


BASE_URL = "http://localhost:80"


@pytest.fixture(scope="module")
def stack_running():
    """Check if Docker Compose stack is running."""
    try:
        resp = httpx.get(f"{BASE_URL}/status", timeout=5)
        return resp.status_code == 200
    except Exception:
        pytest.skip("Docker Compose stack not running")


def test_orchestrator_status(stack_running):
    resp = httpx.get(f"{BASE_URL}/status")
    assert resp.status_code == 200
    assert resp.json()["healthy"] is True


def test_orchestrator_dashboard(stack_running):
    resp = httpx.get(f"{BASE_URL}/dashboard")
    assert resp.status_code == 200
    assert "anyadeals" in resp.text.lower()


def test_orchestrator_jobs(stack_running):
    resp = httpx.get(f"{BASE_URL}/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) >= 4


def test_trigger_research(stack_running):
    resp = httpx.post(f"{BASE_URL}/trigger/research")
    assert resp.status_code == 200
    assert resp.json()["status"] == "triggered"


def test_trigger_validate(stack_running):
    resp = httpx.post(f"{BASE_URL}/trigger/validate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "triggered"
