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


def test_bot_copilot_prompt_caching_prefix_invariance():
    """Verifies that the Telegram Copilot system prompt has a static prefix invariant to sensor values."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 20})

        captured_prompts = []
        mock_ds = MagicMock()
        def mock_cc(messages, model=None):
            for m in messages:
                if m.get("role") == "system":
                    captured_prompts.append(m.get("content"))
            return {"content": "Telemetry nominal."}

        mock_ds.chat_completion.side_effect = mock_cc

        # State 1: Telemetry reading A
        mock_api_a = MagicMock()
        mock_api_a.deepseek_client = mock_ds
        mock_tsdb_a = MagicMock()
        mock_tsdb_a.get_latest.return_value = {"f_out": 40.0, "v_dc": 182.0, "current": 1.2, "rpm": 1200, "fault_code": 0}
        mock_api_a.GLOBAL_TSDB = mock_tsdb_a
        mock_api_a.LATEST_HIL_INCIDENT = {}
        service.set_api_context(mock_api_a)
        await service.handle_conversational_query(chat_id=111, user_query="Status?")

        # State 2: Telemetry reading B with different values
        mock_api_b = MagicMock()
        mock_api_b.deepseek_client = mock_ds
        mock_tsdb_b = MagicMock()
        mock_tsdb_b.get_latest.return_value = {"f_out": 15.0, "v_dc": 210.0, "current": 2.4, "rpm": 450, "fault_code": 6}
        mock_api_b.GLOBAL_TSDB = mock_tsdb_b
        mock_api_b.LATEST_HIL_INCIDENT = {}
        service.set_api_context(mock_api_b)
        await service.handle_conversational_query(chat_id=222, user_query="Status?")

        assert len(captured_prompts) == 2
        prompt_1, prompt_2 = captured_prompts[0], captured_prompts[1]

        dynamic_boundary = "=== CURRENT ASSET TELEMETRY & INCIDENT STATE (DYNAMIC) ==="
        assert dynamic_boundary in prompt_1, "Missing dynamic boundary in Telegram prompt 1"
        assert dynamic_boundary in prompt_2, "Missing dynamic boundary in Telegram prompt 2"

        prefix_1 = prompt_1.split(dynamic_boundary)[0]
        prefix_2 = prompt_2.split(dynamic_boundary)[0]

        assert prefix_1 == prefix_2, "Cache violation: Telegram copilot static prefix differs across sensor readings"
        assert "Err13" in prefix_1, "Missing Err13 phase loss in Telegram domain reference"
        assert "Err06" in prefix_1, "Missing Err06 overvoltage in Telegram domain reference"

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


def test_telegram_copilot_dynamic_envelope_physical_vs_sim():
    """Verifies that Telegram Copilot adapts DC bus nominal & trip limit dynamically (380V physical vs 220V sim)."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 101})

        # 1. Test Physical Rig (v_dc = 290.0 V)
        mock_api = MagicMock()
        mock_ds = MagicMock()
        mock_ds.chat_completion.return_value = {"content": "System running normally at 290V."}
        mock_tsdb = MagicMock()
        mock_tsdb.get_latest.return_value = {
            "f_out": 40.0,
            "v_dc": 290.0,
            "current": 1.15,
            "rpm": 1200.0,
            "fault_code": 0,
        }
        mock_api.deepseek_client = mock_ds
        mock_api.GLOBAL_TSDB = mock_tsdb
        mock_api.LATEST_HIL_INCIDENT = {}
        service.set_api_context(mock_api)

        await service.handle_conversational_query(chat_id=12345, user_query="is the machine running okay?")
        call_messages = mock_ds.chat_completion.call_args[0][0]
        sys_prompt = call_messages[0]["content"]
        assert "DC Bus Voltage: 290.0 V (Nominal 270.0-290.0V, Trip Limit: 380V)" in sys_prompt

        # 2. Test Simulation Rig (v_dc = 182.0 V)
        mock_tsdb.get_latest.return_value["v_dc"] = 182.0
        await service.handle_conversational_query(chat_id=12345, user_query="is the machine running okay?")
        call_messages_sim = mock_ds.chat_completion.call_args[0][0]
        sys_prompt_sim = call_messages_sim[0]["content"]
        assert "DC Bus Voltage: 182.0 V (Nominal 200.0-214.0V, Trip Limit: 220V)" in sys_prompt_sim

    async_test(_run())


def test_chart_generator_physical_rig_dynamic_scaling():
    """Verifies that waveform generation scales dynamically to 380V trip threshold for physical rig (v_dc > 240V)."""
    import pandas as pd
    from industrial_rca.bot.chart_generator import generate_trip_waveform

    # Physical rig data (290V DC bus)
    df_phys = pd.DataFrame({
        "timestamp": range(10),
        "f_out": [40.0] * 10,
        "v_dc": [290.0] * 10,
        "current": [1.15] * 10,
        "rpm": [1200.0] * 10,
    })
    img_bytes = generate_trip_waveform(df_phys, fault_code=0)
    assert len(img_bytes) > 1000
    assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    # Simulation data (182V DC bus)
    df_sim = pd.DataFrame({
        "timestamp": range(10),
        "f_out": [40.0] * 10,
        "v_dc": [182.0] * 10,
        "current": [1.15] * 10,
        "rpm": [1200.0] * 10,
    })
    img_bytes_sim = generate_trip_waveform(df_sim, fault_code=0)
    assert len(img_bytes_sim) > 1000


def test_get_dc_bus_chart_envelope():
    """Verifies that DC bus chart envelope scales to 380V for physical rig (>240V) and 220V for sim."""
    from industrial_rca.bot.chart_generator import get_dc_bus_chart_envelope

    # Physical rig: max_v = 290.0V
    v_trip, v_max_disp, ticks, labels = get_dc_bus_chart_envelope(290.0)
    assert v_trip == 380.0
    assert v_max_disp >= 380.0
    assert 380 in ticks
    assert "380 V" in labels

    # Simulation rig: max_v = 182.0V
    v_trip_sim, v_max_disp_sim, ticks_sim, labels_sim = get_dc_bus_chart_envelope(182.0)
    assert v_trip_sim == 220.0
    assert 220 in ticks_sim
    assert "220 V" in labels_sim


def test_bot_handle_status_six_channels():
    """Verifies that handle_status displays all 6 SCADA telemetry channels matching the web dashboard."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 102})

        mock_api = MagicMock()
        mock_tsdb = MagicMock()
        mock_tsdb.get_latest.return_value = {
            "f_out": 20.0,
            "f_target": 20.0,
            "v_dc": 286.1,
            "v_out": 95.0,
            "current": 0.0,
            "rpm": 597.0,
            "torque": 1.9,
            "power": 0.0,
            "fault_code": 0,
        }
        mock_api.GLOBAL_TSDB = mock_tsdb
        mock_api.LATEST_HIL_INCIDENT = {}
        service.set_api_context(mock_api)

        await service.handle_status(chat_id=12345)
        service.client.send_message.assert_called_once()
        text = service.client.send_message.call_args[0][1]

        # Verify all 6 telemetry parameters are explicitly present in status message
        assert "20.00 Hz" in text
        assert "286.1 V" in text
        assert "95.0 V AC" in text
        assert "0.00 A" in text
        assert "597 RPM" in text
        assert "1.9%" in text
        assert "0.00 kW" in text

    async_test(_run())


def test_bot_copilot_prompt_six_channels():
    """Verifies that Telegram Copilot system prompt dynamically incorporates all 6 telemetry channels."""
    async def _run():
        service = TelegramBotService(token="mock_token_123")
        service.client.send_message = AsyncMock(return_value={"message_id": 103})

        mock_api = MagicMock()
        mock_ds = MagicMock()
        mock_ds.chat_completion.return_value = {"content": "Machine is running steady at 20 Hz."}
        mock_tsdb = MagicMock()
        mock_tsdb.get_latest.return_value = {
            "f_out": 20.0,
            "f_target": 20.0,
            "v_dc": 286.1,
            "v_out": 95.0,
            "current": 0.0,
            "rpm": 597.0,
            "torque": 1.9,
            "power": 0.0,
            "fault_code": 0,
        }
        mock_api.deepseek_client = mock_ds
        mock_api.GLOBAL_TSDB = mock_tsdb
        mock_api.LATEST_HIL_INCIDENT = {}
        service.set_api_context(mock_api)

        await service.handle_conversational_query(chat_id=12345, user_query="what is the power and torque right now?")
        call_messages = mock_ds.chat_completion.call_args[0][0]
        sys_prompt = call_messages[0]["content"]

        # Check that dynamic suffix includes all 6 channels
        assert "Output Frequency: 20.00 Hz" in sys_prompt or "Output Frequency: 20.0 Hz" in sys_prompt
        assert "DC Bus Voltage: 286.1 V" in sys_prompt
        assert "AC Output Voltage: 95.0 V AC" in sys_prompt
        assert "Motor Line Current: 0.00 A" in sys_prompt
        assert "Motor Speed: 597 RPM" in sys_prompt
        assert "1.9%" in sys_prompt
        assert "0.00 kW" in sys_prompt

    async_test(_run())


def test_chart_generator_six_channels():
    """Verifies that waveform generation renders a full 6-channel dashboard including v_out, torque & power."""
    import pandas as pd
    from industrial_rca.bot.chart_generator import generate_trip_waveform, _extract_dataframe

    # Partial dataframe missing some channels
    raw_df = pd.DataFrame({
        "timestamp": range(20),
        "f_out": [20.0] * 20,
        "v_dc": [286.1] * 20,
        "current": [0.0] * 20,
        "rpm": [597.0] * 20,
    })
    filled_df = _extract_dataframe(raw_df)
    assert "v_out" in filled_df.columns
    assert "torque" in filled_df.columns
    assert "power" in filled_df.columns

    # Render full 6-channel waveform graphic
    img_bytes = generate_trip_waveform(filled_df, fault_code=0)
    assert len(img_bytes) > 5000
    assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"





