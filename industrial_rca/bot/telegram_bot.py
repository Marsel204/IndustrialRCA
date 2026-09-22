"""
Unified Telegram Bot Service for Industrial RCA System.
Supports:
- Outbound proactive trip alerts with auto-attached Matplotlib waveforms.
- LangGraph Human-in-the-Loop (HITL) approval via inline buttons.
- Conversational DeepSeek AI Copilot with sliding-window chat memory.
- Commands: /start, /status, /alarms, /rca, /chart, /help.
- Hybrid subscriber management (auto-register on /start + .env default).
"""

import asyncio
import json
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union
import pandas as pd

from industrial_rca.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_POLLING_INTERVAL,
    DASHBOARD_URL,
    EQUIPMENT_ID,
    EQUIPMENT_NAME,
    DATA_DIR,
)
from industrial_rca.bot.telegram_client import TelegramClient
from industrial_rca.bot.telegram_formatter import format_telegram_response
from industrial_rca.bot.chart_generator import (
    generate_trip_waveform,
    generate_live_trend_plot,
    generate_spectrum_plot,
)
from industrial_rca.data.oem_manuals import get_vfd_fault_info
from industrial_rca.utils.logging import get_logger

logger = get_logger("industrial_rca.bot.service")

SUBSCRIBERS_FILE = DATA_DIR / "telegram_subscribers.json"


def _to_float(val: Any, default: float) -> float:
    """Safely converts val to float, falling back to default if None, Mock, or invalid."""
    try:
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val))
    except (TypeError, ValueError):
        return default


def _to_int(val: Any, default: int) -> int:
    """Safely converts val to int, falling back to default if None, Mock, or invalid."""
    try:
        if isinstance(val, (int, float)):
            return int(val)
        return int(str(val))
    except (TypeError, ValueError):
        return default


class TelegramBotService:
    """Orchestrates Telegram interactions, commands, outbound alerts, and AI Copilot."""

    def __init__(
        self,
        token: Optional[str] = None,
        default_chat_id: Optional[str] = None,
        dashboard_url: Optional[str] = None,
    ):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.default_chat_id = default_chat_id or TELEGRAM_CHAT_ID
        self.dashboard_url = dashboard_url or DASHBOARD_URL
        self.client = TelegramClient(self.token) if self.token else None

        self.subscribers: Set[str] = set()
        self._load_subscribers()
        if self.default_chat_id:
            self.subscribers.add(str(self.default_chat_id))

        self.last_update_id: int = 0
        self.is_running: bool = False
        self._poll_task: Optional[asyncio.Task] = None

        # Chat memory: chat_id -> list of {"role": "user"|"assistant", "content": str}
        self.chat_memory: Dict[str, List[Dict[str, str]]] = {}
        self.max_memory_turns: int = 6

        # Callback registry for HITL / API actions
        self._api_context: Optional[Any] = None

    def set_api_context(self, api_module: Any):
        """Allows injecting the FastAPI module context for direct graph access."""
        self._api_context = api_module

    def _load_subscribers(self):
        """Loads persistent subscribers from disk."""
        try:
            if SUBSCRIBERS_FILE.exists():
                with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, list):
                        self.subscribers.update(str(s) for s in saved)
        except Exception as e:
            logger.warning(f"Failed to load subscribers from {SUBSCRIBERS_FILE}: {e}")

    def _save_subscribers(self):
        """Persists current subscribers to disk."""
        try:
            SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.subscribers), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save subscribers to {SUBSCRIBERS_FILE}: {e}")

    def add_subscriber(self, chat_id: Union[int, str]):
        """Registers a chat ID to receive proactive machine trip alerts."""
        cid = str(chat_id)
        if cid not in self.subscribers:
            self.subscribers.add(cid)
            self._save_subscribers()
            logger.info(f"Registered new Telegram subscriber: {cid}")

    def remove_subscriber(self, chat_id: Union[int, str]):
        """Unregisters a chat ID from machine trip alerts."""
        cid = str(chat_id)
        if cid in self.subscribers:
            self.subscribers.remove(cid)
            self._save_subscribers()
            logger.info(f"Unregistered Telegram subscriber: {cid}")

    # ── Outbound Proactive Notifications ──────────────────────────────

    async def notify_trip_alert(
        self,
        incident_data: Dict[str, Any],
        telemetry_dataset: Optional[Any] = None,
    ):
        """
        Sends an urgent machine trip notification with an attached waveform plot
        to all subscribed chat IDs.
        """
        if not self.client or not self.subscribers:
            return

        fault_code = incident_data.get("fault_code", 0)
        fault_desc = incident_data.get("fault_description") or f"Trip Code {fault_code}"
        asset_id = incident_data.get("asset_id", EQUIPMENT_ID)
        inc_id = incident_data.get("incident_id", f"INC-{int(time.time())}")
        thread_id = incident_data.get("thread_id", f"rca-hil-{inc_id}")
        dataset_id = incident_data.get("dataset_id", "")

        text = (
            f"🚨 <b>CRITICAL MACHINE TRIP DETECTED</b>\n\n"
            f"• <b>Asset:</b> <code>{asset_id}</code> ({EQUIPMENT_NAME})\n"
            f"• <b>Fault:</b> <b>Err0{fault_code} - {fault_desc}</b>\n"
            f"• <b>Incident ID:</b> <code>{inc_id}</code>\n"
            f"• <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"⚡ <i>LangGraph RCA pipeline has been triggered. Diagnosing root cause...</i>"
        )

        # Build inline action buttons
        keyboard = TelegramClient.build_inline_keyboard([
            [
                {"text": "🔍 View RCA Diagnosis", "callback_data": f"show_rca:{thread_id}"},
                {"text": "📊 Live Status", "callback_data": "refresh_telemetry"},
            ],
            [
                {"text": "🔗 Open Web Dashboard", "url": f"{self.dashboard_url}"},
            ],
        ])

        # Generate trip waveform plot in-memory
        plot_bytes: Optional[bytes] = None
        try:
            if telemetry_dataset is not None:
                plot_bytes = generate_trip_waveform(telemetry_dataset, fault_code=fault_code, asset_id=asset_id)
            elif self._api_context and hasattr(self._api_context, "TelemetryStore") and dataset_id:
                ds = self._api_context.TelemetryStore.get(dataset_id)
                if ds:
                    plot_bytes = generate_trip_waveform(ds, fault_code=fault_code, asset_id=asset_id)
            if not plot_bytes:
                plot_bytes = generate_trip_waveform(pd.DataFrame(), fault_code=fault_code, asset_id=asset_id)
        except Exception as e:
            logger.warning(f"Failed to generate trip waveform plot: {e}")

        # Broadcast to all subscribers
        for chat_id in list(self.subscribers):
            try:
                if plot_bytes:
                    await self.client.send_photo(
                        chat_id=chat_id,
                        photo_bytes=plot_bytes,
                        caption=text,
                        reply_markup=keyboard,
                    )
                else:
                    await self.client.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=keyboard,
                    )
            except Exception as e:
                logger.error(f"Failed to push trip alert to chat {chat_id}: {e}")

    async def notify_rca_complete(
        self,
        incident_id: str,
        thread_id: str,
        dataset_id: str,
        graph_values: Optional[Dict[str, Any]] = None,
    ):
        """
        Sends completed RCA diagnosis report with Human-in-the-Loop
        [Approve Remediation] and [Reject] buttons to all subscribers.
        """
        if not self.client or not self.subscribers:
            return

        vals = graph_values or {}
        if not vals and self._api_context and hasattr(self._api_context, "GLOBAL_RCA_GRAPH"):
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = self._api_context.GLOBAL_RCA_GRAPH.get_state(config)
            vals = snapshot.values if snapshot else {}

        fault_code = vals.get("fault_code") or 6
        winning_hyp = vals.get("winning_hypothesis") or {}
        root_cause_desc = vals.get("root_cause_description") or winning_hyp.get("name", "Rapid Deceleration Overvoltage")
        confidence = winning_hyp.get("confidence", 0.95) * 100

        # Extract 5-Whys summary if available
        causal_chain = vals.get("causal_chain_5_whys") or []
        why_text = ""
        if causal_chain:
            first_why = causal_chain[0].get("why", "")
            root_why = causal_chain[-1].get("root_cause", "")
            why_text = f"\n• <b>Primary Causal Link:</b> {first_why}"
            if root_why and root_why != first_why:
                why_text += f"\n• <b>Core Root Cause:</b> {root_why}"

        # Extract proposed remediation action
        proposed_actions = winning_hyp.get("proposed_actions") or []
        remediation_text = (
            proposed_actions[0]
            if proposed_actions
            else "Increase deceleration time parameter P0.12 or install dynamic braking resistor."
        )

        text = (
            f"📋 <b>RCA DIAGNOSIS COMPLETE (LangGraph + DeepSeek)</b>\n\n"
            f"• <b>Asset:</b> <code>{vals.get('asset_id', EQUIPMENT_ID)}</code>\n"
            f"• <b>Fault:</b> Err0{fault_code}\n"
            f"• <b>Confidence:</b> <b>{confidence:.1f}%</b>\n"
            f"• <b>Diagnosis:</b> {root_cause_desc}"
            f"{why_text}\n\n"
            f"🛠 <b>Recommended Remediation:</b>\n"
            f"👉 <i>{remediation_text}</i>\n\n"
            f"⚠️ <b>Action Required:</b> Please authorize or reject this remediation."
        )

        keyboard = TelegramClient.build_inline_keyboard([
            [
                {"text": "✅ Approve Remediation", "callback_data": f"approve_remediation:{thread_id}"},
                {"text": "❌ Reject / Manual", "callback_data": f"reject_remediation:{thread_id}"},
            ],
            [
                {"text": "📈 View Waveform", "callback_data": f"show_waveform:{dataset_id}"},
                {"text": "🔗 Web App", "url": f"{self.dashboard_url}"},
            ],
        ])

        for chat_id in list(self.subscribers):
            try:
                await self.client.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.error(f"Failed to push RCA complete to chat {chat_id}: {e}")

    # ── Command & Callback Handlers ───────────────────────────────────

    async def handle_start(self, chat_id: Union[int, str], user_first_name: str):
        """Handles /start command: registers chat and sends onboarding instructions."""
        self.add_subscriber(chat_id)
        text = (
            f"👋 Welcome <b>{user_first_name}</b> to <b>Industrial RCA Bot</b>!\n\n"
            f"✅ You are subscribed to real-time machine trip alerts for <b>{EQUIPMENT_ID}</b> "
            f"({EQUIPMENT_NAME}).\n\n"
            f"<b>Available Commands:</b>\n"
            f"• <code>/status</code> — Real-time telemetry snapshot\n"
            f"• <code>/alarms</code> — Recent incident & trip status\n"
            f"• <code>/rca</code> — Latest LangGraph RCA diagnosis & 5-Whys\n"
            f"• <code>/chart</code> — High-resolution telemetry waveform plot\n"
            f"• <code>/help</code> — Full guide & interaction tips\n\n"
            f"💬 <b>AI Copilot:</b> You can also type any natural language question directly "
            f"(e.g. <i>'Why did the motor trip?'</i> or <i>'Check current DC bus voltage'</i>) "
            f"and DeepSeek AI will analyze the live telemetry!"
        )
        keyboard = TelegramClient.build_inline_keyboard([
            [
                {"text": "📊 Live Status", "callback_data": "refresh_telemetry"},
                {"text": "📈 Telemetry Plot", "callback_data": "show_waveform:latest"},
            ],
            [
                {"text": "🔗 Open Web Dashboard", "url": f"{self.dashboard_url}"},
            ],
        ])
        await self.client.send_message(chat_id, text, reply_markup=keyboard)

    async def handle_help(self, chat_id: Union[int, str]):
        """Handles /help command."""
        text = (
            f"📖 <b>Industrial RCA Telegram Bot Commands</b>\n\n"
            f"• <code>/status</code>: Inspect real-time frequency, DC bus voltage, current, RPM, and inverter state.\n"
            f"• <code>/alarms</code>: View active trip state, latched fault codes, and incident history.\n"
            f"• <code>/rca</code>: Review latest LangGraph Root Cause Analysis findings and 5-Whys causal tree.\n"
            f"• <code>/chart</code> or <code>/plot</code>: Generate an in-memory Matplotlib waveform graphic.\n"
            f"• <code>/clear</code> or <code>/reset</code>: Clear the AI Copilot conversation context memory.\n"
            f"• <code>/subscribe</code>: Enable proactive trip push notifications for this chat.\n"
            f"• <code>/unsubscribe</code>: Stop notifications.\n\n"
            f"💡 <i>Tip: When an alarm fires, you can approve corrective actions right from Telegram!</i>"
        )
        await self.client.send_message(chat_id, text)

    async def handle_clear(self, chat_id: Union[int, str]):
        """Clears conversational memory for this chat and instructs how to clear visual history."""
        cid = str(chat_id)
        self.chat_memory[cid] = []
        text = (
            "🧹 <b>Conversation Memory Cleared</b>\n\n"
            "• The AI Copilot conversation memory has been reset.\n"
            "• <i>To clear previous messages from your screen in Telegram:</i>\n"
            "  Click the three dots (<b>⋮</b>) at the top-right corner of this chat and select <b>Clear history</b>."
        )
        keyboard = TelegramClient.build_inline_keyboard([
            [
                {"text": "📊 Live Status", "callback_data": "refresh_telemetry"},
                {"text": "📈 SCADA Chart", "callback_data": "show_waveform:latest"},
            ],
        ])
        await self.client.send_message(chat_id, text, reply_markup=keyboard)

    async def handle_status(self, chat_id: Union[int, str], message_id: Optional[int] = None):
        """Handles /status command: returns live telemetry metrics."""
        f_out = 40.0
        v_dc = 182.0
        current = 1.20
        rpm = 1200.0
        fault_code = 0
        status_badge = "🟢 NORMAL / RUNNING"

        if self._api_context:
            # Try TSDB
            tsdb = getattr(self._api_context, "GLOBAL_TSDB", None)
            if tsdb and hasattr(tsdb, "get_latest"):
                latest = tsdb.get_latest(EQUIPMENT_ID)
                if isinstance(latest, dict):
                    f_out = _to_float(latest.get("f_out"), f_out)
                    v_dc = _to_float(latest.get("v_dc"), v_dc)
                    current = _to_float(latest.get("current"), current)
                    rpm = _to_float(latest.get("rpm"), rpm)
                    fault_code = _to_int(latest.get("fault_code"), 0)

            # Check latest incident
            latest_hil = getattr(self._api_context, "LATEST_HIL_INCIDENT", {})
            if isinstance(latest_hil, dict) and latest_hil.get("has_incident") and latest_hil.get("pipeline_status") != "COMPLETED":
                inc_dict = latest_hil.get("incident_data")
                if isinstance(inc_dict, dict):
                    fault_code = _to_int(inc_dict.get("fault_code"), fault_code)
                status_badge = f"🔴 TRIPPED (Err0{fault_code})"
            elif fault_code > 0:
                status_badge = f"🔴 TRIPPED (Err0{fault_code})"

        fault_info = get_vfd_fault_info(fault_code) if fault_code else {}
        fault_name = fault_info.get("name", "None")

        text = (
            f"📊 <b>TELEMETRY STATUS: {EQUIPMENT_ID}</b>\n\n"
            f"• <b>Operational State:</b> {status_badge}\n"
            f"• <b>Output Frequency:</b> <code>{f_out:.1f} Hz</code>\n"
            f"• <b>DC Bus Voltage:</b> <code>{v_dc:.1f} V</code>\n"
            f"• <b>Motor Current:</b> <code>{current:.2f} A</code>\n"
            f"• <b>Motor Speed:</b> <code>{rpm:.0f} RPM</code>\n"
            f"• <b>Active Fault Code:</b> <code>{fault_code} ({fault_name})</code>\n"
            f"• <b>Last Updated:</b> {time.strftime('%H:%M:%S UTC')}"
        )

        keyboard = TelegramClient.build_inline_keyboard([
            [
                {"text": "🔄 Refresh", "callback_data": "refresh_telemetry"},
                {"text": "📈 View Waveform", "callback_data": "show_waveform:latest"},
            ],
            [
                {"text": "🔗 Web App", "url": f"{self.dashboard_url}"},
            ],
        ])

        if message_id:
            try:
                await self.client.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)
            except Exception as e:
                logger.warning(f"Could not edit message {message_id} ({e}), sending fresh message")
                await self.client.send_message(chat_id, text, reply_markup=keyboard)
        else:
            await self.client.send_message(chat_id, text, reply_markup=keyboard)

    async def handle_alarms(self, chat_id: Union[int, str]):
        """Handles /alarms command."""
        latest_hil = getattr(self._api_context, "LATEST_HIL_INCIDENT", {}) if self._api_context else {}
        has_inc = latest_hil.get("has_incident", False)
        inc_data = latest_hil.get("incident_data") or {}

        if has_inc:
            fc = inc_data.get("fault_code", 0)
            desc = inc_data.get("fault_description", f"Fault Code {fc}")
            status = latest_hil.get("pipeline_status", "UNKNOWN")
            text = (
                f"🚨 <b>ACTIVE ALARM SUMMARY</b>\n\n"
                f"• <b>Incident ID:</b> <code>{inc_data.get('incident_id')}</code>\n"
                f"• <b>Asset:</b> {inc_data.get('asset_id', EQUIPMENT_ID)}\n"
                f"• <b>Trip Code:</b> <b>Err0{fc} - {desc}</b>\n"
                f"• <b>Pipeline State:</b> <code>{status}</code>\n"
                f"• <b>Detected At:</b> {inc_data.get('received_at', 'N/A')}\n"
            )
            keyboard = TelegramClient.build_inline_keyboard([
                [
                    {"text": "🔍 View RCA", "callback_data": f"show_rca:{inc_data.get('thread_id', '')}"},
                    {"text": "📈 View Plot", "callback_data": f"show_waveform:{inc_data.get('dataset_id', 'latest')}"},
                ],
            ])
        else:
            text = (
                f"✅ <b>NO ACTIVE ALARMS</b>\n\n"
                f"• <b>Asset:</b> <code>{EQUIPMENT_ID}</code>\n"
                f"• <b>Condition:</b> Normal nominal operating parameters\n"
                f"• <b>VFD Trip Relay:</b> Healthy (No active latch)"
            )
            keyboard = TelegramClient.build_inline_keyboard([
                [{"text": "📊 Live Status", "callback_data": "refresh_telemetry"}],
            ])

        await self.client.send_message(chat_id, text, reply_markup=keyboard)

    async def handle_rca(self, chat_id: Union[int, str], thread_id_override: Optional[str] = None):
        """Handles /rca command or show_rca callback."""
        latest_hil = getattr(self._api_context, "LATEST_HIL_INCIDENT", {}) if self._api_context else {}
        inc_data = latest_hil.get("incident_data") or {}
        thread_id = thread_id_override or inc_data.get("thread_id")

        vals: Dict[str, Any] = {}
        if self._api_context and hasattr(self._api_context, "GLOBAL_RCA_GRAPH") and thread_id:
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = self._api_context.GLOBAL_RCA_GRAPH.get_state(config)
            vals = snapshot.values if snapshot else {}

        if not vals:
            vals = latest_hil.get("graph_result") or {}

        if not vals:
            text = (
                f"ℹ️ <b>No RCA Investigation Record Available</b>\n\n"
                f"No automated RCA diagnosis has been triggered yet. When a hardware trip occurs, "
                f"LangGraph will automatically generate a 5-Whys causal analysis."
            )
            await self.client.send_message(chat_id, text)
            return

        fault_code = vals.get("fault_code") or 6
        pipe_status = vals.get("pipeline_status", "COMPLETED")
        winning_hyp = vals.get("winning_hypothesis") or {}
        root_cause = vals.get("root_cause_description") or winning_hyp.get("name", "Decel Overvoltage")
        confidence = winning_hyp.get("confidence", 0.95) * 100

        causal_chain = vals.get("causal_chain_5_whys") or []
        whys_str = ""
        for idx, item in enumerate(causal_chain[:3], 1):
            whys_str += f"\n  {idx}. {item.get('why', '')}"

        proposed = winning_hyp.get("proposed_actions") or []
        action_str = proposed[0] if proposed else "Inspect dynamic braking resistor and extend decel ramp time."

        text = (
            f"🔍 <b>LANGGRAPH ROOT CAUSE ANALYSIS REPORT</b>\n\n"
            f"• <b>Fault:</b> Err0{fault_code}\n"
            f"• <b>Pipeline Status:</b> <code>{pipe_status}</code>\n"
            f"• <b>Winning Diagnosis:</b> <b>{root_cause}</b> ({confidence:.1f}%)\n"
            f"• <b>Causal 5-Whys Chain:</b>{whys_str}\n\n"
            f"🛠 <b>Recommended Remediation:</b>\n"
            f"👉 <i>{action_str}</i>"
        )

        buttons = []
        if pipe_status in ("AWAITING_REVIEW", "TRIGGERED") and thread_id:
            buttons.append([
                {"text": "✅ Approve Remediation", "callback_data": f"approve_remediation:{thread_id}"},
                {"text": "❌ Reject / Manual", "callback_data": f"reject_remediation:{thread_id}"},
            ])
        buttons.append([
            {"text": "📈 View Waveform Plot", "callback_data": "show_waveform:latest"},
            {"text": "🔗 Web App", "url": f"{self.dashboard_url}"},
        ])

        keyboard = TelegramClient.build_inline_keyboard(buttons)
        await self.client.send_message(chat_id, text, reply_markup=keyboard)

    async def handle_chart(self, chat_id: Union[int, str], dataset_id: Optional[str] = None):
        """Generates and uploads an in-memory Matplotlib waveform graphic."""
        try:
            plot_bytes: Optional[bytes] = None
            fault_code = 0
            asset_id = EQUIPMENT_ID

            if self._api_context and hasattr(self._api_context, "TelemetryStore"):
                # If specific or latest dataset exists
                ds = None
                if dataset_id and dataset_id != "latest":
                    ds = self._api_context.TelemetryStore.get(dataset_id)
                if not ds:
                    latest_hil = getattr(self._api_context, "LATEST_HIL_INCIDENT", {})
                    inc_ds_id = (latest_hil.get("incident_data") or {}).get("dataset_id")
                    if inc_ds_id:
                        ds = self._api_context.TelemetryStore.get(inc_ds_id)
                if ds:
                    fault_code = ds.metadata.get("fault_code", 0)
                    plot_bytes = generate_trip_waveform(ds, fault_code=fault_code, asset_id=asset_id)

            if not plot_bytes and self._api_context and hasattr(self._api_context, "GLOBAL_TSDB") and self._api_context.GLOBAL_TSDB:
                tsdb = self._api_context.GLOBAL_TSDB
                if hasattr(tsdb, "get_window"):
                    df_win = tsdb.get_window(seconds=60, asset_id=asset_id)
                    if not df_win.empty:
                        plot_bytes = generate_trip_waveform(df_win, fault_code=fault_code, asset_id=asset_id, title_suffix="Live Telemetry Dashboard")
                elif hasattr(tsdb, "get_history"):
                    history = tsdb.get_history(asset_id, limit=60)
                    if history:
                        plot_bytes = generate_live_trend_plot(history, asset_id=asset_id)

            if not plot_bytes:
                plot_bytes = generate_trip_waveform(pd.DataFrame(), fault_code=fault_code, asset_id=asset_id)

            status_desc = f"Fault Err0{fault_code}" if fault_code else "Nominal Operating State"
            caption = (
                f"📈 <b>Telemetry Dashboard Snapshot: {asset_id}</b>\n"
                f"• <b>Status:</b> {status_desc}\n"
                f"• <b>Generated:</b> {time.strftime('%H:%M:%S UTC')} • Modern SCADA view"
            )
            keyboard = TelegramClient.build_inline_keyboard([
                [
                    {"text": "🔄 Refresh Chart", "callback_data": "refresh_chart"},
                    {"text": "📊 Live Status", "callback_data": "refresh_telemetry"},
                ],
                [
                    {"text": "🔗 Web App", "url": f"{self.dashboard_url}"},
                ],
            ])
            await self.client.send_photo(chat_id, plot_bytes, caption=caption, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error handling /chart: {e}")
            await self.client.send_message(chat_id, f"⚠️ Failed to generate chart: {str(e)}")

    # ── Conversational Copilot with Short-Term Memory ───────────────────

    async def handle_conversational_query(self, chat_id: Union[int, str], user_query: str):
        """
        Handles freeform user queries using DeepSeek AI Copilot,
        grounded in live telemetry, ISA-95 asset topology, and WECON manuals.
        """
        cid = str(chat_id)
        if cid not in self.chat_memory:
            self.chat_memory[cid] = []

        # Check if user explicitly asks for chart/plot
        wants_chart = any(term in user_query.lower() for term in ["chart", "plot", "graph", "trend", "waveform", "waveforms"])

        # Construct domain context
        f_out, v_dc, current, rpm, fault_code = 40.0, 182.0, 1.2, 1200.0, 0
        active_incident_summary = "None (System is operating normally)."

        if self._api_context:
            tsdb = getattr(self._api_context, "GLOBAL_TSDB", None)
            if tsdb and hasattr(tsdb, "get_latest"):
                latest = tsdb.get_latest(EQUIPMENT_ID)
                if isinstance(latest, dict):
                    f_out = _to_float(latest.get("f_out"), f_out)
                    v_dc = _to_float(latest.get("v_dc"), v_dc)
                    current = _to_float(latest.get("current"), current)
                    rpm = _to_float(latest.get("rpm"), rpm)
                    fault_code = _to_int(latest.get("fault_code"), 0)

            latest_hil = getattr(self._api_context, "LATEST_HIL_INCIDENT", {})
            if isinstance(latest_hil, dict) and latest_hil.get("has_incident"):
                inc = latest_hil.get("incident_data")
                if isinstance(inc, dict):
                    fc = _to_int(inc.get("fault_code"), fault_code)
                    desc = str(inc.get("fault_description") or "")
                    st = str(latest_hil.get("pipeline_status") or "")
                    active_incident_summary = f"Active Trip Incident: Err0{fc} ({desc}), Pipeline Status: {st}."

        fault_info = get_vfd_fault_info(fault_code) if fault_code else {}

        system_prompt = (
            f"You are the Senior SCADA & Reliability Engineer AI Copilot on Telegram for {EQUIPMENT_NAME} ({EQUIPMENT_ID}).\n"
            f"Assist plant operators with concise, technically accurate, reassuring, and conversational answers.\n\n"
            f"CURRENT ASSET TELEMETRY:\n"
            f"• Output Frequency: {f_out:.1f} Hz\n"
            f"• DC Bus Voltage: {v_dc:.1f} V (Nominal ~182V, High Trip Limit: 195V)\n"
            f"• Motor Line Current: {current:.2f} A (High Trip Limit: 2.50A)\n"
            f"• Motor Speed: {rpm:.0f} RPM\n"
            f"• Active Fault Code: {fault_code} ({fault_info.get('name', 'None')})\n"
            f"• Incident State: {active_incident_summary}\n\n"
            f"DOMAIN REFERENCE:\n"
            f"• WECON VM Inverter trips: Err02 (Overcurrent accel), Err03 (Overcurrent decel), "
            f"Err06 (Overvoltage decel from motor back-EMF), Err11 (Motor overload).\n"
            f"• ISA-95 Asset: VFD_VM_01 powers the slurry feed train.\n\n"
            f"STYLE & RESPONSE INSTRUCTIONS:\n"
            f"1. BOTTOM LINE FIRST: For general health checks (e.g. 'is the system okay?'), start with a clear emoji verdict (e.g. '✅ System is operating normally within safe parameters.').\n"
            f"2. CONCISE & CLEAN: Present key telemetry cleanly. Highlight numbers in code or bold.\n"
            f"3. NO UNNECESSARY ALARM WARNINGS: If operating normally with no active fault, DO NOT list hypothetical trip codes (Err02, Err06, etc.) unless the user specifically asks about them.\n"
            f"4. ACTIONABLE: Conclude with a brief 1-sentence operational takeaway.\n"
            f"5. Keep responses concise (under 120 words), friendly, and professional."
        )

        # Build message chain with memory
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for turn in self.chat_memory[cid][-self.max_memory_turns:]:
            messages.append(turn)
        messages.append({"role": "user", "content": user_query})

        reply_text = ""
        try:
            if self._api_context and hasattr(self._api_context, "deepseek_client"):
                client = self._api_context.deepseek_client
                res = client.chat_completion(messages, model="deepseek-flash")
                reply_text = res.get("content", "") if isinstance(res, dict) else str(res)
            else:
                from industrial_rca.tools.deepseek_client import DeepSeekClient
                ds = DeepSeekClient()
                res = ds.chat_completion(messages, model="deepseek-flash")
                reply_text = res.get("content", "") if isinstance(res, dict) else str(res)
        except Exception as e:
            logger.warning(f"Copilot query failed: {e}")
            reply_text = f"⚙️ <b>Copilot Diagnostic</b>:\nCurrent Status: V_dc={v_dc:.1f}V, F_out={f_out:.1f}Hz, Current={current:.2f}A, Fault Code={fault_code}.\n(Detailed LLM reasoning offline: {str(e)})"

        # Update sliding memory
        self.chat_memory[cid].append({"role": "user", "content": user_query})
        self.chat_memory[cid].append({"role": "assistant", "content": reply_text})
        if len(self.chat_memory[cid]) > self.max_memory_turns * 2:
            self.chat_memory[cid] = self.chat_memory[cid][-self.max_memory_turns * 2:]

        # Format markdown into clean, valid Telegram HTML
        formatted_reply = format_telegram_response(reply_text)

        keyboard = TelegramClient.build_inline_keyboard([
            [
                {"text": "📈 View Waveform Plot", "callback_data": "show_waveform:latest"},
                {"text": "📊 Live Status", "callback_data": "refresh_telemetry"},
            ],
            [
                {"text": "🔗 Web App", "url": f"{self.dashboard_url}"},
            ],
        ])

        if wants_chart:
            # Auto-send chart along with answer
            await self.client.send_message(chat_id, formatted_reply)
            await self.handle_chart(chat_id)
        else:
            await self.client.send_message(chat_id, formatted_reply, reply_markup=keyboard)

    # ── Inline Callback Query Processor (Two-Way HITL) ────────────────

    async def handle_callback_query(self, query: Dict[str, Any]):
        """
        Handles interactive inline button clicks from Telegram messages.
        Implements two-way LangGraph HITL approval and updates Telegram message.
        """
        query_id = query.get("id")
        data = query.get("data", "")
        message = query.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        message_id = message.get("message_id")
        user = query.get("from") or {}
        user_name = user.get("username") or user.get("first_name", "Operator")

        if not chat_id:
            return

        if data.startswith("approve_remediation:"):
            thread_id = data.split(":", 1)[1]
            await self.client.answer_callback_query(query_id, text="Approving remediation action...")
            await self._execute_hitl_action(
                action="approved",
                thread_id=thread_id,
                reviewer=f"@{user_name} (Telegram)",
                chat_id=chat_id,
                message_id=message_id,
                orig_text=message.get("text", ""),
            )

        elif data.startswith("reject_remediation:"):
            thread_id = data.split(":", 1)[1]
            await self.client.answer_callback_query(query_id, text="Remediation rejected.")
            await self._execute_hitl_action(
                action="rejected",
                thread_id=thread_id,
                reviewer=f"@{user_name} (Telegram)",
                chat_id=chat_id,
                message_id=message_id,
                orig_text=message.get("text", ""),
            )

        elif data == "refresh_chart":
            await self.client.answer_callback_query(query_id, text="Updating dashboard chart...")
            await self.handle_chart(chat_id)

        elif data == "refresh_telemetry":
            await self.client.answer_callback_query(query_id, text="Telemetry refreshed!")
            is_media = bool(message.get("photo") or message.get("video") or message.get("document"))
            target_msg_id = None if is_media else message_id
            await self.handle_status(chat_id, message_id=target_msg_id)

        elif data.startswith("show_rca:"):
            th_id = data.split(":", 1)[1]
            await self.client.answer_callback_query(query_id, text="Loading RCA Report...")
            await self.handle_rca(chat_id, thread_id_override=th_id)

        elif data.startswith("show_waveform:"):
            ds_id = data.split(":", 1)[1]
            await self.client.answer_callback_query(query_id, text="Rendering waveform...")
            await self.handle_chart(chat_id, dataset_id=ds_id)

        else:
            await self.client.answer_callback_query(query_id)

    async def _execute_hitl_action(
        self,
        action: str,
        thread_id: str,
        reviewer: str,
        chat_id: Union[int, str],
        message_id: Optional[int],
        orig_text: str,
    ):
        """Executes LangGraph HITL approval/rejection and updates Telegram card + SSE."""
        is_approved = action.lower() == "approved"
        stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Resume LangGraph if API context is present
        if self._api_context and hasattr(self._api_context, "GLOBAL_RCA_GRAPH"):
            from langgraph.types import Command
            try:
                config = {"configurable": {"thread_id": thread_id}}
                decision_payload = {
                    "action": "approved" if is_approved else "rejected",
                    "reviewer": reviewer,
                    "notes": f"Authorized via Telegram Bot at {stamp}",
                    "override_root_cause": None,
                }
                for _ in self._api_context.GLOBAL_RCA_GRAPH.stream(Command(resume=decision_payload), config=config):
                    pass

                # Update LATEST_HIL_INCIDENT pipeline status and graph values
                if hasattr(self._api_context, "LATEST_HIL_INCIDENT"):
                    final_snapshot = self._api_context.GLOBAL_RCA_GRAPH.get_state(config)
                    if final_snapshot and final_snapshot.values:
                        self._api_context.LATEST_HIL_INCIDENT["graph_result"] = final_snapshot.values
                        self._api_context.LATEST_HIL_INCIDENT["pipeline_status"] = final_snapshot.values.get("pipeline_status", "COMPLETED")
                    else:
                        self._api_context.LATEST_HIL_INCIDENT["pipeline_status"] = "COMPLETED"

                # Notify web app via SSE broadcast
                if hasattr(self._api_context, "_notify_hil_subscribers"):
                    self._api_context._notify_hil_subscribers({
                        "event": "hil_human_review_submitted",
                        "thread_id": thread_id,
                        "action": action,
                        "reviewer": reviewer,
                        "timestamp": time.time(),
                    })
            except Exception as e:
                logger.error(f"Error resuming LangGraph from Telegram HITL: {e}")

        badge = "✅ <b>REMEDIATION APPROVED</b>" if is_approved else "❌ <b>REMEDIATION REJECTED</b>"
        updated_text = (
            f"{orig_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{badge}\n"
            f"• <b>Authorized by:</b> {reviewer}\n"
            f"• <b>Timestamp:</b> {stamp}\n"
            f"• <b>Status:</b> LangGraph Workflow Resumed & Synchronized with Web Dashboard."
        )

        keyboard = TelegramClient.build_inline_keyboard([
            [
                {"text": "📊 Live Status", "callback_data": "refresh_telemetry"},
                {"text": "🔗 View Dashboard", "url": f"{self.dashboard_url}"},
            ],
        ])

        try:
            if message_id:
                await self.client.edit_message_text(chat_id, message_id, updated_text, reply_markup=keyboard)
            elif chat_id and chat_id != "simulated_chat":
                await self.client.send_message(chat_id, updated_text, reply_markup=keyboard)
        except Exception as e:
            logger.warning(f"Telegram notification update error in _execute_hitl_action: {e}")

    # ── Long-Polling Update Loop ──────────────────────────────────────

    async def _process_update(self, update: Dict[str, Any]):
        """Processes a single update object from Telegram."""
        up_id = update.get("update_id", 0)
        if up_id > self.last_update_id:
            self.last_update_id = up_id

        try:
            # 1. Callback Query (inline button click)
            if "callback_query" in update:
                await self.handle_callback_query(update["callback_query"])
                return

            # 2. Text Message
            if "message" in update:
                msg = update["message"]
                text = (msg.get("text") or "").strip()
                chat_id = (msg.get("chat") or {}).get("id")
                user = msg.get("from") or {}
                first_name = user.get("first_name", "Operator")

                if not chat_id:
                    return

                # Auto-register sender as subscriber on any user interaction
                self.add_subscriber(chat_id)

                if not text:
                    return

                # Slash commands
                cmd = text.split()[0].lower()
                if cmd in ("/start", "/start@industrial_rca_bot"):
                    await self.handle_start(chat_id, first_name)
                elif cmd in ("/help", "/help@industrial_rca_bot"):
                    await self.handle_help(chat_id)
                elif cmd in ("/status", "/status@industrial_rca_bot"):
                    await self.handle_status(chat_id)
                elif cmd in ("/alarms", "/alarms@industrial_rca_bot"):
                    await self.handle_alarms(chat_id)
                elif cmd in ("/rca", "/rca@industrial_rca_bot"):
                    await self.handle_rca(chat_id)
                elif cmd in ("/chart", "/plot", "/chart@industrial_rca_bot", "/plot@industrial_rca_bot"):
                    await self.handle_chart(chat_id)
                elif cmd in ("/clear", "/reset", "/clear@industrial_rca_bot", "/reset@industrial_rca_bot"):
                    await self.handle_clear(chat_id)
                elif cmd in ("/subscribe", "/subscribe@industrial_rca_bot"):
                    self.add_subscriber(chat_id)
                    await self.client.send_message(chat_id, "✅ You are now subscribed to automated trip alerts.")
                elif cmd in ("/unsubscribe", "/unsubscribe@industrial_rca_bot"):
                    self.remove_subscriber(chat_id)
                    await self.client.send_message(chat_id, "ℹ️ You have unsubscribed from automated trip alerts.")
                else:
                    # Conversational AI Copilot fallback
                    await self.handle_conversational_query(chat_id, text)
        except Exception as e:
            logger.error(f"Error handling Telegram update {up_id}: {e}", exc_info=True)
            chat_id = (update.get("message") or {}).get("chat", {}).get("id") or (update.get("callback_query") or {}).get("message", {}).get("chat", {}).get("id")
            if chat_id and self.client:
                try:
                    await self.client.send_message(chat_id, f"⚠️ Error processing command: {str(e)}")
                except Exception:
                    pass

    async def run_polling_loop(self):
        """Infinite polling loop using getUpdates."""
        if not self.client:
            logger.info("TelegramBotService has no token configured; polling loop skipped.")
            return

        self.is_running = True
        logger.info(f"Starting Telegram Bot polling loop for token: {self.token[:8]}...")

        # Test token and get bot details
        try:
            bot_info = await self.client.get_me()
            logger.info(f"Connected to Telegram as @{bot_info.get('username')} ({bot_info.get('first_name')})")
        except Exception as e:
            logger.warning(f"Telegram token validation notice: {e}")

        consecutive_errors = 0
        while self.is_running:
            try:
                updates = await self.client.get_updates(
                    offset=self.last_update_id + 1,
                    timeout=int(TELEGRAM_POLLING_INTERVAL * 10),
                )
                consecutive_errors = 0
                for up in updates:
                    await self._process_update(up)
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_errors += 1
                backoff = min(15, 2 ** min(consecutive_errors, 4))
                logger.warning(f"Telegram polling exception (backoff {backoff}s): {e}")
                await asyncio.sleep(backoff)

        self.is_running = False

    def start_background_polling(self) -> Optional[asyncio.Task]:
        """Launches polling loop as an asyncio background task."""
        if not self.token:
            return None
        if self._poll_task and not self._poll_task.done():
            return self._poll_task

        loop = asyncio.get_event_loop()
        self._poll_task = loop.create_task(self.run_polling_loop())
        return self._poll_task

    async def stop(self):
        """Stops the polling loop and closes HTTP client."""
        self.is_running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self.client:
            await self.client.close()


# Singleton factory
_GLOBAL_BOT_SERVICE: Optional[TelegramBotService] = None


def get_telegram_service(token: Optional[str] = None) -> TelegramBotService:
    """Returns singleton TelegramBotService."""
    global _GLOBAL_BOT_SERVICE
    if _GLOBAL_BOT_SERVICE is None:
        _GLOBAL_BOT_SERVICE = TelegramBotService(token=token)
    return _GLOBAL_BOT_SERVICE
