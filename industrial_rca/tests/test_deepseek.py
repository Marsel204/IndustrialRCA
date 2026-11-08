"""Provider behavior is verified offline; absent credentials cannot imply success."""

from types import SimpleNamespace
from industrial_rca.tools.deepseek_client import DeepSeekClient


def test_deepseek_connection():
    client = DeepSeekClient(api_key="mock")
    info = client.test_connection()
    assert info["status"] == "UNAVAILABLE"
    assert info["is_live"] is False
    assert info["error"]


def test_deepseek_chat_completion():
    message = SimpleNamespace(content="A grounded answer", reasoning_content="", tool_calls=[])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)
    client = DeepSeekClient(api_key="mock")
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
    client.is_live = True
    result = client.chat_completion([{"role": "user", "content": "Ping"}])
    assert result["success"] is True
    assert result["content"] == "A grounded answer"
    client.client = None


def test_deepseek_no_mock_fallback():
    client = DeepSeekClient(api_key="mock")
    result = client.chat_completion([{"role": "user", "content": "Evaluate 5-whys hypothesis"}])
    assert result["success"] is False
    assert result["is_mock"] is False
    assert result["content"] == ""
