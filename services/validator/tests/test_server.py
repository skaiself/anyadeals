import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_status_endpoint():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["healthy"] is True
    assert data["last_run"] is None
    assert data["last_error"] is None
    assert data["running"] is False

def test_status_returns_all_fields():
    response = client.get("/status")
    data = response.json()
    required_fields = {"healthy", "last_run", "last_error", "running"}
    assert required_fields.issubset(data.keys())
