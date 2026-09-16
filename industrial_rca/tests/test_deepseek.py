"""
Unit tests for DeepSeek API integration.
Verifies connection, chat completions, reasoning extraction, and deterministic mock mode.
"""

import pytest
from industrial_rca.tools.deepseek_client import DeepSeekClient


def test_deepseek_connection():
    client = DeepSeekClient()
    info = client.test_connection()
    assert info["status"] == "ONLINE"
    assert info["base_url"] is not None
    assert info["model"] is not None


def test_deepseek_chat_completion():
    client = DeepSeekClient()
    res = client.chat_completion([
        {"role": "user", "content": "Ping"}
    ], model="deepseek-chat", max_tokens=20)
    assert res["success"] is True
    assert len(res["content"]) > 0


def test_deepseek_mock_fallback():
    # Test client with dummy key to force simulation mode
    mock_client = DeepSeekClient(api_key="mock", default_model="deepseek-chat")
    assert mock_client.is_live is False
    res = mock_client.chat_completion([
        {"role": "user", "content": "Evaluate 5-whys hypothesis"}
    ])
    assert res["success"] is True
    assert res["is_mock"] is True
    assert "five_whys" in res["content"] or "STR-301A" in res["content"] or len(res["reasoning_content"]) > 0
