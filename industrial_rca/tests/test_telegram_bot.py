"""
Comprehensive Unit and Integration Tests for Telegram Bot Service.
Tests:
- In-memory Matplotlib industrial waveform generation
- Telegram API client request packaging
- Two-way Human-in-the-Loop (HITL) approval callbacks
- Conversational AI Copilot memory and queries
- Outbound proactive trip alerts and 5-Whys RCA completion reports
- FastAPI Bot management endpoints
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
from fastapi.testclient import TestClient

from industrial_rca.bot.chart_generator import (
    generate_trip_waveform,
    generate_live_trend_plot,
    generate_spectrum_plot,
)
from industrial_rca.bot.telegram_client import TelegramClient
from industrial_rca.bot.telegram_bot import TelegramBotService
from industrial_rca.api import api_app, telegram_bot_service


# Helper runner for async coroutines without requiring pytest-asyncio plugin
def async_test(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def isolate_subscribers_file(tmp_path, monkeypatch):
    """Prevents tests from mutating live production telegram_subscribers.json or .env."""
    test_sub_file = tmp_path / "telegram_subscribers.json"
    monkeypatch.setattr("industrial_rca.bot.telegram_bot.SUBSCRIBERS_FILE", test_sub_file)
    monkeypatch.setattr("industrial_rca.utils.env_manager.save_telegram_credentials", lambda *args, **kwargs: None)


# ── 1. Chart Generator Tests ──────────────────────────────────────────

def test_generate_trip_waveform_empty():
    """Verifies that trip waveform generates valid PNG bytes even from empty data."""
    png_bytes = generate_trip_waveform(pd.DataFrame(), fault_code=6)
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 1000
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_generate_trip_waveform_with_data():
    """Verifies waveform generation with real time-series points."""
    df = pd.DataFrame({
        "f_out": [40.0, 39.0, 20.0, 0.0],
        "v_dc": [182.0, 185.0, 198.0, 204.0],
        "current": [1.2, 1.3, 1.5, 3.2],
        "rpm": [1200.0, 1150.0, 600.0, 0.0],
        "fault_code": [0, 0, 0, 6],
    })
    png_bytes = generate_trip_waveform(df, fault_code=6, asset_id="VFD_VM_01")
    assert isinstance(png_bytes, bytes)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_generate_live_trend_plot():
    """Verifies live trend generation from TSDB records."""
    records = [
        {"f_out": 40.0, "v_dc": 182.0, "current": 1.2, "rpm": 1200.0}
        for _ in range(10)
    ]
    png_bytes = generate_live_trend_plot(records, asset_id="VFD_VM_01")
    assert isinstance(png_bytes, bytes)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_generate_spectrum_plot():
    """Verifies 20 kHz vibration FFT spectrum rendering."""
    normal = {"signal": [0.05 * (i % 10) for i in range(1024)]}
    fault = {"signal": [0.25 * (i % 5) for i in range(1024)]}
    png_bytes = generate_spectrum_plot(normal_waveform=normal, fault_waveform=fault)
    assert isinstance(png_bytes, bytes)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


# ── 2. Telegram Client Tests ──────────────────────────────────────────

def test_build_inline_keyboard():
    """Tests InlineKeyboardMarkup structure generation."""
    rows = [
        [{"text": "✅ Approve", "callback_data": "app_1"}, {"text": "❌ Reject", "callback_data": "rej_1"}],
        [{"text": "🔗 Web App", "url": "http://localhost:5173"}],
    ]
    kb = TelegramClient.build_inline_keyboard(rows)
    assert "inline_keyboard" in kb
    assert len(kb["inline_keyboard"]) == 2
    assert kb["inline_keyboard"][0][0]["text"] == "✅ Approve"


def test_telegram_client_send_message_mocked():
    """Tests send_message packaging with mocked HTTP response."""
    async def _run():
        client = TelegramClient(token="mock_token_123")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"ok": True, "result": {"message_id": 42}})

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.send_message(chat_id=999, text="Hello Industrial RCA")
            assert result["message_id"] == 42
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["chat_id"] == 999
            assert call_kwargs["json"]["text"] == "Hello Industrial RCA"
    async_test(_run())


def test_telegram_client_send_photo_mocked():
    """Tests send_photo packaging with mocked HTTP response."""
    async def _run():
        client = TelegramClient(token="mock_token_123")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"ok": True, "result": {"message_id": 43}})

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.send_photo(chat_id=999, photo_bytes=b"fake_png", caption="Trip Waveform")
            assert result["message_id"] == 43
            mock_post.assert_called_once()
            assert "photo" in mock_post.call_args[1]["files"]
    async_test(_run())


# ── 3. Telegram Bot Service & Command Tests ───────────────────────────

def test_bot_service_subscribers_management():
    """Verifies that add/remove subscriber operations maintain unique subscribers."""
    service = TelegramBotService(token="mock_token_123", default_chat_id="111")
    service.add_subscriber(222)
    service.add_subscriber("333")
    assert "111" in service.subscribers
    assert "222" in service.subscribers
    assert "333" in service.subscribers

    service.remove_subscriber(222)
    assert "222" not in service.subscribers
    assert "333" in service.subscribers


def test_bot_handle_start_auto_registers_subscriber():
    """Verifies /start registers the operator's chat ID and sends welcome message."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 1})

        await service.handle_start(chat_id=12345, user_first_name="Engineer Alex")
        assert "12345" in service.subscribers
        service.client.send_message.assert_called_once()
        msg_call = service.client.send_message.call_args
        assert "Engineer Alex" in msg_call[0][1]
    async_test(_run())


def test_bot_handle_status():
    """Verifies /status outputs formatted VFD metrics."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 2})

        await service.handle_status(chat_id=12345)
        service.client.send_message.assert_called_once()
        text = service.client.send_message.call_args[0][1]
        assert "TELEMETRY STATUS: VFD_VM_01" in text
        assert "DC Bus Voltage" in text
    async_test(_run())


def test_bot_two_way_hitl_approval_callback():
    """Verifies that clicking [Approve Remediation] calls HITL logic and edits message."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.answer_callback_query = AsyncMock(return_value=True)
        service.client.edit_message_text = AsyncMock(return_value={"message_id": 5})

        # Mock API context
        mock_api = MagicMock()
        mock_graph = MagicMock()
        mock_graph.stream.return_value = [None]
        mock_api.GLOBAL_RCA_GRAPH = mock_graph
        mock_api.LATEST_HIL_INCIDENT = {"pipeline_status": "TRIGGERED"}
        mock_api._notify_hil_subscribers = MagicMock()
        service.set_api_context(mock_api)

        callback_query = {
            "id": "cb_query_1",
            "data": "approve_remediation:rca-thread-test-01",
            "from": {"username": "chief_engineer", "first_name": "Chief"},
            "message": {
                "message_id": 101,
                "chat": {"id": 12345},
                "text": "RCA Diagnosis: Rapid Deceleration Overvoltage.",
            },
        }

        await service.handle_callback_query(callback_query)

        service.client.answer_callback_query.assert_called_once()
        service.client.edit_message_text.assert_called_once()
        edited_text = service.client.edit_message_text.call_args[0][2]
        assert "REMEDIATION APPROVED" in edited_text
        assert "@chief_engineer" in edited_text
    async_test(_run())


def test_bot_outbound_trip_alert_broadcast():
    """Verifies notify_trip_alert delivers photo alert to all subscribers."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.subscribers = {"777", "888"}
        service.client.send_photo = AsyncMock(return_value={"message_id": 10})

        incident_data = {
            "fault_code": 6,
            "fault_description": "Deceleration Overvoltage",
            "asset_id": "VFD_VM_01",
            "incident_id": "INC-TEST-06",
            "thread_id": "rca-thread-06",
        }

        await service.notify_trip_alert(incident_data)
        assert service.client.send_photo.call_count == 2
        caption = service.client.send_photo.call_args[1]["caption"]
        assert "CRITICAL MACHINE TRIP DETECTED" in caption
        assert "Err06" in caption
    async_test(_run())


def test_bot_conversational_copilot_query():
    """Verifies freeform natural language query interacts with AI Copilot."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 20})

        mock_api = MagicMock()
        mock_ds = MagicMock()
        mock_ds.chat.return_value = "The DC bus voltage rose to 204V due to regenerative braking."
        mock_ds.chat_completion.return_value = {"content": "The DC bus voltage rose to 204V due to regenerative braking."}
        mock_api.deepseek_client = mock_ds
        mock_api.GLOBAL_TSDB = None
        mock_api.LATEST_HIL_INCIDENT = {}
        service.set_api_context(mock_api)

        await service.handle_conversational_query(chat_id=12345, user_query="Why did the DC bus voltage spike?")
        service.client.send_message.assert_called_once()
        reply = service.client.send_message.call_args[0][1]
        assert "regenerative braking" in reply
        assert len(service.chat_memory["12345"]) == 2
    async_test(_run())


# ── 4. FastAPI Bot Endpoints ──────────────────────────────────────────

def test_fastapi_bot_status_endpoint():
    """Verifies GET /api/v1/bot/status endpoint returns valid health payload."""
    client = TestClient(api_app)
    resp = client.get("/api/v1/bot/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "is_configured" in data
    assert "subscribers_count" in data
    assert "dashboard_url" in data


def test_fastapi_bot_settings_endpoint():
    """Verifies POST /api/v1/bot/settings updates configuration dynamically."""
    client = TestClient(api_app)
    resp = client.post("/api/v1/bot/settings", json={
        "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "default_chat_id": "999888777",
        "dashboard_url": "http://localhost:5173",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_configured"] is True
    assert data["default_chat_id"] == "999888777"
    assert "999888777" in data["subscribers"]


def test_bot_callback_refresh_telemetry_on_media_message():
    """Verifies that clicking refresh_telemetry on a photo message sends a new message without editing photo text."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.answer_callback_query = AsyncMock(return_value=True)
        service.client.send_message = AsyncMock(return_value={"message_id": 50})
        service.client.edit_message_text = AsyncMock()

        callback_query = {
            "id": "cb_query_media",
            "data": "refresh_telemetry",
            "from": {"username": "operator1", "first_name": "Operator"},
            "message": {
                "message_id": 42,
                "chat": {"id": 12345},
                "photo": [{"file_id": "photo_123"}],
                "caption": "Telemetry Dashboard Snapshot",
            },
        }

        await service.handle_callback_query(callback_query)

        service.client.answer_callback_query.assert_called_once()
        service.client.send_message.assert_called_once()
        service.client.edit_message_text.assert_not_called()
    async_test(_run())


def test_bot_callback_refresh_chart():
    """Verifies that clicking refresh_chart invokes handle_chart."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.answer_callback_query = AsyncMock(return_value=True)
        service.handle_chart = AsyncMock()

        callback_query = {
            "id": "cb_query_chart",
            "data": "refresh_chart",
            "from": {"username": "operator1", "first_name": "Operator"},
            "message": {
                "message_id": 43,
                "chat": {"id": 12345},
            },
        }

        await service.handle_callback_query(callback_query)

        service.client.answer_callback_query.assert_called_once()
        service.handle_chart.assert_called_once_with(12345)
    async_test(_run())


def test_bot_handle_status_edit_fallback():
    """Verifies that if edit_message_text fails, handle_status falls back to send_message."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.edit_message_text = AsyncMock(side_effect=Exception("400 Bad Request"))
        service.client.send_message = AsyncMock(return_value={"message_id": 99})

        await service.handle_status(chat_id=12345, message_id=88)

        service.client.edit_message_text.assert_called_once()
        service.client.send_message.assert_called_once()
    async_test(_run())


def test_bot_conversational_formats_markdown():
    """Verifies that markdown in LLM response is converted to Telegram HTML."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 21})

        mock_api = MagicMock()
        mock_ds = MagicMock()
        mock_ds.chat_completion.return_value = {
            "content": "**System Status: OK**\n- Motor Speed: `1200 RPM`\n- DC Bus: 182.0 V (Limit < 195V)"
        }
        mock_api.deepseek_client = mock_ds
        mock_api.GLOBAL_TSDB = None
        mock_api.LATEST_HIL_INCIDENT = {}
        service.set_api_context(mock_api)

        await service.handle_conversational_query(chat_id=12345, user_query="is the system okay ?")
        service.client.send_message.assert_called_once()
        reply = service.client.send_message.call_args[0][1]
        assert "<b>System Status: OK</b>" in reply
        assert "• Motor Speed: <code>1200 RPM</code>" in reply
        assert "&lt; 195V" in reply
        assert "**" not in reply
    async_test(_run())


def test_bot_handle_clear():
    """Verifies /clear resets conversation memory and returns confirmation."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.chat_memory["12345"] = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        service.client.send_message = AsyncMock(return_value={"message_id": 99})

        await service.handle_clear(chat_id=12345)

        assert service.chat_memory["12345"] == []
        service.client.send_message.assert_called_once()
        text = service.client.send_message.call_args[0][1]
        assert "Conversation Memory Cleared" in text
    async_test(_run())


