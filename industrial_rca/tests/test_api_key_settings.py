"""
Unit and integration tests for API key settings endpoints and .env management.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from industrial_rca.api import api_app
from industrial_rca.utils import env_manager
from industrial_rca.tools.deepseek_client import DeepSeekClient


@pytest.fixture
def temp_env_file(tmp_path, monkeypatch):
    """Provides an isolated .env file and clean os.environ for testing."""
    test_env = tmp_path / ".env"
    monkeypatch.setattr(env_manager, "get_env_path", lambda: test_env)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    return test_env


def test_get_api_key_settings_unconfigured(temp_env_file):
    client = TestClient(api_app)
    response = client.get("/api/v1/settings/api-key")
    assert response.status_code == 200
    data = response.json()
    assert data["has_key"] is False
    assert data["masked_key"] == ""
    assert data["provider"] == "DeepSeek"
    assert data["status"] == "SIMULATION"


def test_save_and_get_api_key_settings(temp_env_file):
    client = TestClient(api_app)
    
    # Save a test API key
    payload = {
        "api_key": "sk-1234567890abcdef12345678",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-flash",
    }
    response = client.post("/api/v1/settings/api-key", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["has_key"] is True
    assert data["masked_key"] == "sk-12***5678"
    assert data["is_live"] is True
    assert data["status"] == "ONLINE"

    # Verify .env file was written
    assert temp_env_file.exists()
    env_content = temp_env_file.read_text()
    assert "DEEPSEEK_API_KEY=sk-1234567890abcdef12345678" in env_content

    # GET endpoint should now report active key
    get_res = client.get("/api/v1/settings/api-key")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["has_key"] is True
    assert get_data["masked_key"] == "sk-12***5678"
    assert get_data["is_live"] is True


def test_save_empty_api_key_fails(temp_env_file):
    client = TestClient(api_app)
    response = client.post("/api/v1/settings/api-key", json={"api_key": "   "})
    assert response.status_code == 400


def test_delete_api_key_settings(temp_env_file):
    client = TestClient(api_app)

    # First save key
    client.post("/api/v1/settings/api-key", json={"api_key": "sk-test-key-to-delete-123"})
    assert temp_env_file.exists()
    assert "DEEPSEEK_API_KEY" in temp_env_file.read_text()

    # Now delete key
    del_res = client.delete("/api/v1/settings/api-key")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["success"] is True
    assert del_data["has_key"] is False
    assert del_data["status"] == "SIMULATION"

    # Verify key was removed from file and os.environ
    assert "DEEPSEEK_API_KEY" not in os.environ


def test_test_api_key_endpoint_mock_response(temp_env_file):
    client = TestClient(api_app)

    with patch.object(DeepSeekClient, "test_connection") as mock_test:
        mock_test.return_value = {
            "status": "ONLINE",
            "is_live": True,
            "model": "deepseek-flash",
            "response": "DEEPSEEK_ONLINE",
        }
        res = client.post(
            "/api/v1/settings/api-key/test",
            json={"api_key": "sk-dummy-valid-key-12345"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "ONLINE"
        assert data["is_live"] is True
