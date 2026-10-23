"""Keep regression runs independent of user credentials and paid provider calls."""

import pytest


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch):
    from industrial_rca.tools.deepseek_client import reconfigure_all_deepseek_clients

    monkeypatch.setenv("DEEPSEEK_API_KEY", "mock")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    reconfigure_all_deepseek_clients(api_key="mock")
