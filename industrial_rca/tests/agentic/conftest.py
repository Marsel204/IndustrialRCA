"""Keep the refactor proposal independent of credentials and external services."""

import pytest


@pytest.fixture(autouse=True)
def offline_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "mock")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")


@pytest.fixture
def ingestion(monkeypatch):
    from industrial_rca import api

    monkeypatch.setattr(api, "LATEST_HIL_INCIDENT", {
        "has_incident": False, "pipeline_status": "READY", "version": 0,
    })
    monkeypatch.setattr(api, "SCENARIOS_REGISTRY", {})
    monkeypatch.setattr(api, "_notify_hil_subscribers", lambda event: None)
    monkeypatch.setattr(api, "_broadcast_live_metric", lambda event: None)
    return api
