"""
Unified FastAPI REST and Server-Sent Events (SSE) Backend for Industrial Root Cause Analysis.
Provides endpoints for:
- Health and status
- Scenario telemetry and downsampled vector arrays
- High-frequency 20 kHz vibration FFT spectrum
- ISA-95 Asset Topology traversal and visual graph mapping
- Stateful LangGraph RCA execution, step tracking, and state retrieval
- Human-in-the-Loop (HITL) authorization and review
- DeepSeek AI Copilot real-time token streaming (SSE)
- Live Hardware-in-the-Loop (HIL) edge incident ingestion and reactive push (SSE)
"""

import os
import sys
import time
import json
import math
import random
import socket
import asyncio
import threading
from uuid import uuid4
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional, Generator
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from industrial_rca.config import (
    EQUIPMENT_ID,
    EQUIPMENT_NAME,
    OPERATIONAL_LIMITS,
    VFD_OPERATIONAL_LIMITS,
    RUNNING_FREQUENCY_1X_HZ,
    RUNNING_FREQUENCY_2X_HZ,
    CAVITATION_BROADBAND_BAND_HZ,
    HIGH_FREQ_SAMPLING_RATE_HZ,
    DEFAULT_THREAD_ID,
)
from industrial_rca.data.oem_manuals import (
    OEM_PUMP_SPEC,
    FMEA_KNOWLEDGE_BASE,
    ISO_14224_TAXONOMY,
    get_vfd_spec,
    get_vfd_fault_info,
)
from industrial_rca.data.telemetry_generator import (
    TelemetryDataset,
    TelemetryStore,
    generate_normal_scenario,
    generate_fault_scenario,
    generate_vfd_dataset,
    generate_high_frequency_vibration,
)
from industrial_rca.tools.telemetry_analytics import (
    TelemetryAnalyticsTool,
    GLOBAL_TELEMETRY_CACHE,
    SpectralAnalyzer,
)
from industrial_rca.tools.topology_tracer import AssetTopologyTracer
from industrial_rca.tools.cmms_connector import CMMSConnector
from industrial_rca.tools.deepseek_client import DeepSeekClient
from industrial_rca.tools.influx_tool import InfluxDBTelemetryTool
from industrial_rca.data.embedded_tsdb import GLOBAL_TSDB
from industrial_rca.graph.workflow import create_rca_graph
from industrial_rca.services.incidents import build_incident_dataset
from industrial_rca.utils.middleware import CorrelationIdMiddleware
from industrial_rca.utils.logging import get_logger
from industrial_rca.utils.env_manager import (
    get_api_key_status,
    save_api_key,
    delete_api_key,
    test_api_credentials,
)
from industrial_rca.bot import get_telegram_service, TelegramBotService

logger = get_logger("industrial_rca.api")

# Global instances
analytics_tool = TelemetryAnalyticsTool(GLOBAL_TELEMETRY_CACHE)
topology_tracer = AssetTopologyTracer()
cmms_tool = CMMSConnector()
deepseek_client = DeepSeekClient()
influx_tool = InfluxDBTelemetryTool()
telegram_bot_service = get_telegram_service()
telegram_bot_service.set_api_context(sys.modules[__name__])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts Telegram Bot polling loop if token is configured and syncs environment."""
    from dotenv import load_dotenv
    from industrial_rca.config import ENV_FILE
    from industrial_rca.tools.deepseek_client import reconfigure_all_deepseek_clients
    if ENV_FILE.exists():
        load_dotenv(dotenv_path=ENV_FILE, override=False)
        reconfigure_all_deepseek_clients()
        logger.info(f"Synchronized DeepSeek client credentials from {ENV_FILE}")

    telegram_bot_service.set_api_context(sys.modules[__name__])
    if telegram_bot_service.token:
        telegram_bot_service.start_background_polling()
        logger.info("Telegram Bot service background polling initialized.")

    yield

    await telegram_bot_service.stop()


api_app = FastAPI(
    title="Industrial RCA Unified REST & SSE API",
    description="High-performance backend serving telemetry, ISA-95 topology, LangGraph RCA, and DeepSeek streaming.",
    version="2.1.0",
    lifespan=lifespan,
)

# Correlation ID and error handling middleware
api_app.add_middleware(CorrelationIdMiddleware)

# Enable CORS for Vite frontend running on localhost:5173 / localhost:3000
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def _safe_async_run(coro):
    """Executes an async coroutine safely from synchronous or asynchronous contexts."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        def _runner():
            asyncio.run(coro)
        t = threading.Thread(target=_runner, daemon=True)
        t.start()
    except Exception as e:
        logger.warning(f"Async dispatch warning: {e}")


# Stateful shared checkpointer and graph
GLOBAL_CHECKPOINTER = MemorySaver()
GLOBAL_RCA_GRAPH = create_rca_graph(checkpointer=GLOBAL_CHECKPOINTER)

# Pre-seeded scenarios in TelemetryStore
SCENARIOS_REGISTRY: Dict[str, str] = {}


def _ensure_default_scenarios():
    """Initializes and registers real Wecon VFD hardware and experiment scenarios in TelemetryStore."""
    if "live_stream" not in SCENARIOS_REGISTRY:
        ds_live = generate_vfd_dataset(scenario="live_stream")
        ds_id_live = TelemetryStore.register(ds_live, "ds_live_stream")
        SCENARIOS_REGISTRY["live_stream"] = ds_id_live

    if "exp_err02" not in SCENARIOS_REGISTRY:
        ds_err02 = generate_vfd_dataset(scenario="exp_err02")
        ds_id_err02 = TelemetryStore.register(ds_err02, "ds_exp_err02")
        SCENARIOS_REGISTRY["exp_err02"] = ds_id_err02

    if "exp_err06" not in SCENARIOS_REGISTRY:
        ds_err06 = generate_vfd_dataset(scenario="exp_err06")
        ds_id_err06 = TelemetryStore.register(ds_err06, "ds_exp_err06")
        SCENARIOS_REGISTRY["exp_err06"] = ds_id_err06
        SCENARIOS_REGISTRY["fault"] = ds_id_err06

    if "exp_err13" not in SCENARIOS_REGISTRY:
        ds_err13 = generate_vfd_dataset(scenario="exp_err13")
        ds_id_err13 = TelemetryStore.register(ds_err13, "ds_exp_err13")
        SCENARIOS_REGISTRY["exp_err13"] = ds_id_err13

    if "exp_nominal" not in SCENARIOS_REGISTRY:
        ds_nom = generate_vfd_dataset(scenario="exp_nominal")
        ds_id_nom = TelemetryStore.register(ds_nom, "ds_exp_nominal")
        SCENARIOS_REGISTRY["exp_nominal"] = ds_id_nom
        SCENARIOS_REGISTRY["normal"] = ds_id_nom


_ensure_default_scenarios()

# Global HIL Incident State
LATEST_HIL_INCIDENT: Dict[str, Any] = {
    "has_incident": False,
    "incident_data": None,
    "received_at": None,
    "pipeline_status": "READY",
    "graph_result": None,
    "version": 0,
}
_HIL_EVENT_SUBSCRIBERS: List[asyncio.Queue] = []
_SUBSCRIBER_LOCK = threading.Lock()

_LIVE_STREAM_SUBSCRIBERS: List[asyncio.Queue] = []
_LIVE_STREAM_LOCK = threading.Lock()


def _safe_queue_put(q: asyncio.Queue, item: Any):
    """Safely enqueues items into an asyncio queue from sync or async threads."""
    try:
        loop = getattr(q, "_loop", None)
        if loop and loop.is_running():
            loop.call_soon_threadsafe(q.put_nowait, item)
        else:
            q.put_nowait(item)
    except Exception:
        pass


def _notify_hil_subscribers(event_data: Dict[str, Any]):
    with _SUBSCRIBER_LOCK:
        for q in _HIL_EVENT_SUBSCRIBERS:
            _safe_queue_put(q, event_data)

    # Forward alerts to Telegram Bot
    if telegram_bot_service and telegram_bot_service.subscribers:
        try:
            ev = event_data.get("event")
            if ev == "hil_incident_detected":
                inc_data = event_data.get("data") or {}
                ds_id = event_data.get("dataset_id")
                ds = TelemetryStore.get(ds_id) if ds_id else None
                _safe_async_run(telegram_bot_service.notify_trip_alert(inc_data, telemetry_dataset=ds))
            elif ev == "hil_pipeline_completed":
                inc_id = event_data.get("incident_id")
                th_id = event_data.get("thread_id")
                ds_id = event_data.get("dataset_id")
                _safe_async_run(telegram_bot_service.notify_rca_complete(
                    incident_id=inc_id,
                    thread_id=th_id,
                    dataset_id=ds_id,
                    graph_values=LATEST_HIL_INCIDENT.get("graph_result"),
                ))
            elif ev == "hil_incident_cleared":
                if hasattr(telegram_bot_service, "notify_recovery_alert"):
                    _safe_async_run(telegram_bot_service.notify_recovery_alert(
                        asset_id=event_data.get("asset_id", "VFD_VM_01"),
                        f_out=float(event_data.get("f_out", 40.0)),
                        rpm=float(event_data.get("rpm", 1200.0)),
                    ))
        except Exception as e:
            logger.warning(f"Telegram notification dispatch error: {e}")


def _broadcast_live_metric(metric_data: Dict[str, Any]):
    with _LIVE_STREAM_LOCK:
        for q in _LIVE_STREAM_SUBSCRIBERS:
            _safe_queue_put(q, metric_data)


# ── Request / Response Models ─────────────────────────────────────────

class IncidentPayload(BaseModel):
    asset_id: str = Field(default="VFD_VM_01", min_length=1, max_length=128, description="Identifier of the tripped asset")
    fault_code: int = Field(default=6, ge=0, le=65535, description="WECON VM trip code (e.g. 6 for Err06, 11 for Err11)")
    fault_description: Optional[str] = Field(default="", description="Human-readable trip description")
    incident_id: Optional[str] = Field(default=None, min_length=1, max_length=128, description="Unique incident ID")
    pre_fault_telemetry: List[Dict[str, Any]] = Field(default_factory=list, max_length=10000, description="Array of time-series points")
    model_config = ConfigDict(extra="allow")


class RCARunRequest(BaseModel):
    dataset_id: str = Field(default="exp_err06", description="Dataset identifier or preset (live_stream, exp_err02, exp_err06, exp_nominal)")
    asset_id: str = Field(default=EQUIPMENT_ID, description="Target asset ID")
    thread_id: Optional[str] = Field(default=None, description="Session thread ID for LangGraph checkpointer")
    use_deepseek: bool = Field(default=True, description="Enable DeepSeek AI evaluation")
    deepseek_model: Optional[str] = Field(default=None, description="Provider model override; defaults to DEEPSEEK_MODEL")


class HumanReviewRequest(BaseModel):
    thread_id: str = Field(description="Thread ID of paused RCA workflow")
    action: str = Field(pattern="^(approve|approved|reject|override)$", description="'approve', 'reject', or 'override'")
    reviewer: str = Field(min_length=1, max_length=200, pattern=r".*\S.*", description="Signing engineer name")
    notes: str = Field(default="", description="Engineering justification notes")
    override_root_cause: Optional[str] = Field(default=None, description="Optional overridden root cause description")


class CopilotChatRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(description="Chat history messages")
    thread_id: Optional[str] = Field(default=None, description="Associated RCA thread ID for contextual grounding")
    model: Optional[str] = Field(default="deepseek-flash", description="Model to use")


class ApiKeySaveRequest(BaseModel):
    api_key: str = Field(description="DeepSeek API Key (e.g. sk-...)")
    base_url: Optional[str] = Field(default=None, description="Optional custom base URL")
    model: Optional[str] = Field(default=None, description="Optional default model name")


class ApiKeyTestRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, description="Optional API key to test without saving")
    base_url: Optional[str] = Field(default=None, description="Optional base URL")
    model: Optional[str] = Field(default=None, description="Optional model name")


class SimulationToggleRequest(BaseModel):
    enabled: bool = Field(default=False, description="Enable or disable simulated telemetry fallback")
    scenario: str = Field(default="nominal", description="Scenario: H_VFD_ERR06, H_VFD_ERR02, H_VFD_ERR03, H_VFD_ERR11, or nominal")
    normal_duration_sec: float = Field(default=5.0, description="Duration in seconds of normal baseline before injecting fault")


class BotSettingsRequest(BaseModel):
    bot_token: Optional[str] = Field(default=None, description="Telegram Bot API Token")
    default_chat_id: Optional[str] = Field(default=None, description="Default Chat/Channel ID for alerts")
    dashboard_url: Optional[str] = Field(default=None, description="Base URL of Web Dashboard")


class BotTestAlertRequest(BaseModel):
    chat_id: Optional[str] = Field(default=None, description="Specific Chat ID (defaults to all subscribers)")
    message: Optional[str] = Field(default=None, description="Custom test alert text")


_SIMULATION_TASK: Optional[asyncio.Task] = None
_SIMULATION_STATE: Dict[str, Any] = {
    "enabled": False,
    "scenario": "nominal",
    "phase": "IDLE",
    "start_time": 0.0,
    "normal_duration": 5.0,
    "countdown": 0.0,
    "fault_injected": False,
}


def _dispatch_simulated_incident(incident: IncidentPayload):
    """Dispatch explicitly generated simulation observations through common ingestion."""
    tasks = BackgroundTasks()
    ingest_incident(incident, tasks, simulated=True)
    threading.Thread(target=lambda: asyncio.run(tasks()), daemon=True).start()


async def _run_telemetry_simulation(scenario: str, normal_duration_sec: float = 5.0):
    """
    Simulates real-time telemetry:
    1. For `normal_duration_sec` seconds: streams steady nominal baseline readings (f_out: 40 Hz, v_dc: 182 V, current: 1.15 A)
       into GLOBAL_TSDB, broadcasts to SSE clients with live countdown.
    2. At t >= normal_duration_sec: injects selected envelope breach / trip code (Err06, Err02, Err03, Err11),
       automatically triggering the LangGraph DeepSeek RCA Agent!
    """
    logger.info(f"Starting telemetry simulation task: scenario={scenario}, duration={normal_duration_sec}s")
    start_time = time.time()
    _SIMULATION_STATE["start_time"] = start_time
    _SIMULATION_STATE["scenario"] = scenario
    _SIMULATION_STATE["normal_duration"] = normal_duration_sec
    _SIMULATION_STATE["phase"] = "NORMAL"
    _SIMULATION_STATE["fault_injected"] = False

    fault_code_map = {
        "H_VFD_ERR06": 6, "ERR06": 6, "6": 6,
        "H_VFD_ERR02": 2, "ERR02": 2, "2": 2,
        "H_VFD_ERR03": 3, "ERR03": 3, "3": 3,
        "H_VFD_ERR11": 11, "ERR11": 11, "11": 11,
        "H_VFD_ERR13": 13, "ERR13": 13, "13": 13, "EXP_ERR13": 13,
    }
    target_fc = fault_code_map.get(scenario.upper(), 0) if scenario.lower() not in ("nominal", "normal") else 0

    try:
        while influx_tool.is_simulation_enabled():
            now = time.time()
            elapsed = now - start_time
            countdown = max(0.0, round(normal_duration_sec - elapsed, 1))
            _SIMULATION_STATE["countdown"] = countdown

            if elapsed < normal_duration_sec or target_fc == 0:
                _SIMULATION_STATE["phase"] = "NORMAL"
                f_out = round(40.0 + 0.25 * math.sin(now * 0.5) + random.uniform(-0.05, 0.05), 2)
                v_dc = round(182.0 + 1.2 * math.cos(now * 0.3) + random.uniform(-0.3, 0.3), 1)
                current = round(1.15 + 0.03 * math.sin(now * 0.7) + random.uniform(-0.02, 0.02), 2)
                rpm = round(f_out * 29.0 + random.uniform(-1.0, 1.0), 1)
                metric = {
                    "asset_id": "VFD_VM_01",
                    "f_out": f_out,
                    "f_target": 40.0,
                    "v_dc": v_dc,
                    "v_out": 220.0,
                    "current": current,
                    "rpm": rpm,
                    "fault_code": 0,
                    "status": "RUNNING",
                    "timestamp": now,
                    "source": "simulation",
                    "is_simulated": True,
                    "telemetry_connected": True,
                    "simulation_enabled": True,
                    "simulation_scenario": scenario,
                    "simulation_phase": "NORMAL",
                    "simulation_countdown": countdown,
                }
                GLOBAL_TSDB.insert(metric)
                influx_tool.update_latest(metric)
                _broadcast_live_metric(metric)
                await asyncio.sleep(1.0)
            else:
                if not _SIMULATION_STATE.get("fault_injected", False):
                    _SIMULATION_STATE["fault_injected"] = True
                    _SIMULATION_STATE["phase"] = "TRIPPED"
                    _SIMULATION_STATE["countdown"] = 0.0
                    logger.info(f"Injecting simulated fault {target_fc} ({scenario}) at t={elapsed:.2f}s!")

                    if target_fc == 6:
                        v_dc = 206.5
                        current = 1.32
                    elif target_fc == 2:
                        v_dc = 184.0
                        current = 2.95
                    elif target_fc == 3:
                        v_dc = 185.0
                        current = 2.75
                    elif target_fc == 11:
                        v_dc = 181.5
                        current = 2.45
                    elif target_fc == 13:
                        v_dc = 182.0
                        current = 0.00
                    else:
                        v_dc = 202.5
                        current = 1.20

                    trip_metric = {
                        "asset_id": "VFD_VM_01",
                        "f_out": 0.0,
                        "f_target": 0.0,
                        "v_dc": v_dc,
                        "v_out": 0.0,
                        "current": current,
                        "rpm": 0.0,
                        "fault_code": target_fc,
                        "status": "TRIPPED",
                        "timestamp": now,
                        "source": "simulation",
                        "is_simulated": True,
                        "telemetry_connected": True,
                        "simulation_enabled": True,
                        "simulation_scenario": scenario,
                        "simulation_phase": "TRIPPED",
                        "simulation_countdown": 0.0,
                    }
                    GLOBAL_TSDB.insert(trip_metric)
                    influx_tool.update_latest(trip_metric)
                    _broadcast_live_metric(trip_metric)

                    try:
                        df_pre = GLOBAL_TSDB.get_window(seconds=60, asset_id="VFD_VM_01")
                        pre_points = df_pre.to_dict("records")
                        fault_info = get_vfd_fault_info(target_fc)
                        inc_desc = fault_info.get("description", f"WECON VM VFD Trip Code {target_fc}")
                        inc = IncidentPayload(
                            asset_id="VFD_VM_01",
                            fault_code=target_fc,
                            fault_description=inc_desc,
                            incident_id=f"INC-SIM-{target_fc}-{int(now)}",
                            pre_fault_telemetry=pre_points,
                        )
                        _dispatch_simulated_incident(inc)
                    except Exception as ex:
                        logger.error(f"Auto-dispatch error in simulation loop: {ex}")

                    await asyncio.sleep(1.0)
                else:
                    hold_metric = {
                        "asset_id": "VFD_VM_01",
                        "f_out": 0.0,
                        "f_target": 0.0,
                        "v_dc": 182.0,
                        "v_out": 0.0,
                        "current": 0.0,
                        "rpm": 0.0,
                        "fault_code": target_fc,
                        "status": "TRIPPED",
                        "timestamp": now,
                        "source": "simulation",
                        "is_simulated": True,
                        "telemetry_connected": True,
                        "simulation_enabled": True,
                        "simulation_scenario": scenario,
                        "simulation_phase": "TRIPPED",
                        "simulation_countdown": 0.0,
                    }
                    influx_tool.update_latest(hold_metric)
                    _broadcast_live_metric(hold_metric)
                    await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        logger.info(f"Simulation task cancelled: scenario={scenario}")
    except Exception as e:
        logger.error(f"Exception in simulation task: {e}")


# ── Health & Diagnostics ──────────────────────────────────────────────

@api_app.get("/api/v1/health")
def get_health():
    _ensure_default_scenarios()
    cache_stats = GLOBAL_TELEMETRY_CACHE.get_stats()
    mqtt_online = influx_tool.is_mqtt_active()
    latest_tsdb = GLOBAL_TSDB.get_latest("VFD_VM_01")
    is_real = bool(latest_tsdb and (time.time() - latest_tsdb.get("timestamp", 0) < 30))
    sim_enabled = influx_tool.is_simulation_enabled()
    telemetry_connected = is_real or sim_enabled

    return {
        "status": "ONLINE",
        "service": "Industrial RCA Unified Backend API",
        "timestamp": time.time(),
        "time_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "active_scenarios": list(SCENARIOS_REGISTRY.keys()),
        "telemetry_cache": cache_stats,
        "latest_hil_incident": LATEST_HIL_INCIDENT.get("incident_data"),
        "hil_status": LATEST_HIL_INCIDENT.get("pipeline_status"),
        "mqtt_connected": mqtt_online,
        "telemetry_connected": telemetry_connected,
        "is_simulated": sim_enabled,
        "simulation_enabled": sim_enabled,
        "simulation_scenario": influx_tool.get_simulation_scenario() if sim_enabled else None,
        "simulation_phase": _SIMULATION_STATE.get("phase", "IDLE") if sim_enabled else None,
        "telemetry_source": "hardware" if is_real else ("simulation" if sim_enabled else "disconnected"),
    }


@api_app.get("/api/v1/telemetry/simulation")
def get_telemetry_simulation_mode():
    """Returns whether simulated telemetry is currently enabled by user, plus scenario and phase."""
    return {
        "simulation_enabled": influx_tool.is_simulation_enabled(),
        "is_simulated": influx_tool.is_simulation_enabled(),
        "scenario": influx_tool.get_simulation_scenario(),
        "phase": _SIMULATION_STATE.get("phase", "IDLE"),
        "countdown": _SIMULATION_STATE.get("countdown", 0.0),
    }


@api_app.post("/api/v1/telemetry/simulation")
async def set_telemetry_simulation_mode(request: SimulationToggleRequest):
    """
    Explicitly enables or disables fallback simulated telemetry.
    When enabling with an error scenario, executes a 5-second normal baseline before injecting fault.
    """
    global _SIMULATION_TASK
    if _SIMULATION_TASK and not _SIMULATION_TASK.done():
        _SIMULATION_TASK.cancel()
        try:
            await asyncio.sleep(0.02)
        except Exception:
            pass

    influx_tool.set_simulation_mode(
        request.enabled,
        scenario=request.scenario,
        normal_duration=request.normal_duration_sec,
    )

    if request.enabled:
        _SIMULATION_STATE["enabled"] = True
        _SIMULATION_STATE["scenario"] = request.scenario
        _SIMULATION_STATE["phase"] = "NORMAL"
        _SIMULATION_STATE["countdown"] = request.normal_duration_sec
        _SIMULATION_STATE["fault_injected"] = False
        _SIMULATION_TASK = asyncio.create_task(
            _run_telemetry_simulation(request.scenario, request.normal_duration_sec)
        )
        status_str = f"SIMULATION_STARTED_{request.scenario.upper()}"
    else:
        _SIMULATION_STATE["enabled"] = False
        _SIMULATION_STATE["phase"] = "STOPPED"
        _SIMULATION_STATE["countdown"] = 0.0
        status_str = "SIMULATION_DISABLED"

    logger.info(f"Telemetry simulation mode updated: enabled={request.enabled}, scenario={request.scenario}")
    return {
        "simulation_enabled": influx_tool.is_simulation_enabled(),
        "is_simulated": influx_tool.is_simulation_enabled(),
        "scenario": request.scenario,
        "phase": _SIMULATION_STATE.get("phase", "IDLE"),
        "countdown": _SIMULATION_STATE.get("countdown", 0.0),
        "status": status_str,
    }


@api_app.get("/api/v1/telemetry/health")
def get_telemetry_health():
    """Backward compatibility endpoint for test suite and HIL simulator."""
    return {
        "status": "ONLINE",
        "service": "Industrial RCA Ingestion Middleware",
        "timestamp": time.time(),
        "has_incident": bool(LATEST_HIL_INCIDENT.get("has_incident")),
        "latest_incident": LATEST_HIL_INCIDENT.get("incident_data"),
        "latest_hil_incident": LATEST_HIL_INCIDENT.get("incident_data"),
        "pipeline_status": LATEST_HIL_INCIDENT.get("pipeline_status"),
        "hil_status": LATEST_HIL_INCIDENT.get("pipeline_status"),
    }


# ── Live Edge HIL Ingestion & Reactive Push (Registered BEFORE parametrized /telemetry/{id}) ───

@api_app.post("/api/v1/telemetry/incident")
def ingest_hardware_incident(incident: IncidentPayload, background_tasks: BackgroundTasks):
    return ingest_incident(incident, background_tasks)


def ingest_incident(incident: IncidentPayload, background_tasks: BackgroundTasks, *, simulated: bool = False):
    """
    Receives an incident payload from Node-RED or physical edge gateway,
    formats it into a TelemetryDataset, registers it with TelemetryStore,
    and launches the LangGraph RCA workflow.
    """
    inc_id = incident.incident_id or f"INC-{'SIM' if simulated else 'HIL'}-{uuid4().hex}"
    fault_desc = incident.fault_description
    if not fault_desc:
        fault_info = get_vfd_fault_info(incident.fault_code)
        fault_desc = fault_info.get("description", f"WECON VM VFD Trip Code {incident.fault_code}")

    current_inc_fc = (LATEST_HIL_INCIDENT.get("incident_data") or {}).get("fault_code")
    # Guard: Prevent redundant pipeline dispatch only if an investigation for the exact same fault code is already in flight
    if LATEST_HIL_INCIDENT.get("pipeline_status") == "TRIGGERED" and current_inc_fc == incident.fault_code and (LATEST_HIL_INCIDENT.get("incident_data") or {}).get("asset_id") == incident.asset_id:
        logger.info(f"HIL RCA pipeline already in flight for fault {incident.fault_code}; ignoring redundant trigger.")
        return {
            "status": "ALREADY_RUNNING",
            "incident_id": (LATEST_HIL_INCIDENT.get("incident_data") or {}).get("incident_id"),
            "rca_pipeline": "IN_PROGRESS",
        }

    dataset = build_incident_dataset(incident, simulated=simulated)
    dataset.metadata["incident_id"] = inc_id
    df = dataset.df_1hz
    ds_id = TelemetryStore.register(dataset, f"ds_hil_{incident.fault_code}_{inc_id}")
    SCENARIOS_REGISTRY["hil"] = ds_id
    if simulated:
        SCENARIOS_REGISTRY["live_stream"] = ds_id

    thread_id = f"rca-hil-{inc_id}"
    LATEST_HIL_INCIDENT["has_incident"] = True
    LATEST_HIL_INCIDENT["incident_data"] = {
        "incident_id": inc_id,
        "asset_id": incident.asset_id,
        "fault_code": incident.fault_code,
        "fault_description": fault_desc,
        "dataset_id": ds_id,
        "thread_id": thread_id,
        "point_count": len(df),
        "is_simulated": simulated,
        "received_at": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    LATEST_HIL_INCIDENT["received_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC")
    LATEST_HIL_INCIDENT["pipeline_status"] = "TRIGGERED"
    LATEST_HIL_INCIDENT["version"] += 1

    _notify_hil_subscribers({
        "event": "hil_incident_detected",
        "data": LATEST_HIL_INCIDENT["incident_data"],
        "thread_id": thread_id,
        "dataset_id": ds_id,
        "timestamp": time.time(),
    })
    _broadcast_live_metric({
        "event": "incident",
        "incident_id": inc_id,
        "asset_id": incident.asset_id,
        "fault_code": incident.fault_code,
        "fault_description": fault_desc,
        # Use peak/last pre-fault values so KPI cards show meaningful data at trip moment
        "f_out": float(df["f_out"].iloc[-1]) if ("f_out" in df.columns and len(df) > 0) else 0.0,
        "v_dc": float(df["v_dc"].max()) if ("v_dc" in df.columns and len(df) > 0) else 0.0,
        "current": float(df["current"].max()) if ("current" in df.columns and len(df) > 0) else 0.0,
        "rpm": float(df["rpm"].iloc[-1]) if ("rpm" in df.columns and len(df) > 0) else 0.0,
        "status": "TRIPPED",
        "timestamp": time.time(),
    })

    def _run_graph():
        try:
            config = {"configurable": {"thread_id": thread_id}}
            init_state = {
                "dataset_id": ds_id,
                "asset_id": incident.asset_id,
                "has_active_trip": True,
                "incident_id": inc_id,
                "fault_code": incident.fault_code,
                "use_deepseek": True,
                "deepseek_model": deepseek_client.default_model,
            }
            for _ in GLOBAL_RCA_GRAPH.stream(init_state, config=config):
                pass
            snapshot = GLOBAL_RCA_GRAPH.get_state(config)
            # If the incident was already cleared while graph was running, do not re-latch
            if (LATEST_HIL_INCIDENT.get("incident_data") or {}).get("thread_id") != thread_id or not LATEST_HIL_INCIDENT.get("has_incident") or LATEST_HIL_INCIDENT.get("pipeline_status") == "READY":
                logger.info(f"RCA graph completed for thread {thread_id}, but incident was already cleared. Discarding result.")
                return

            LATEST_HIL_INCIDENT["graph_result"] = snapshot.values if snapshot else None
            paused = bool(snapshot and snapshot.tasks and snapshot.tasks[0].interrupts)
            status = "AWAITING_REVIEW" if paused else snapshot.values.get("pipeline_status", "INCONCLUSIVE")
            LATEST_HIL_INCIDENT["pipeline_status"] = status
            _notify_hil_subscribers({
                "event": "hil_pipeline_completed",
                "incident_id": inc_id,
                "thread_id": thread_id,
                "dataset_id": ds_id,
                "status": status,
            })
        except Exception as e:
            if (LATEST_HIL_INCIDENT.get("incident_data") or {}).get("thread_id") == thread_id:
                LATEST_HIL_INCIDENT["pipeline_status"] = "INCONCLUSIVE"
                _notify_hil_subscribers({"event": "hil_pipeline_completed", "thread_id": thread_id,
                                         "dataset_id": ds_id, "status": "INCONCLUSIVE", "error": str(e)})

    background_tasks.add_task(_run_graph)

    return {
        "status": "INCIDENT_INGESTED",
        "incident_id": inc_id,
        "asset_id": incident.asset_id,
        "fault_code": incident.fault_code,
        "fault_description": fault_desc,
        "telemetry_points_buffered": len(df),
        "rca_pipeline": "DISPATCHED_ASYNC",
    }


@api_app.get("/api/v1/telemetry/latest_incident")
def get_latest_incident():
    return LATEST_HIL_INCIDENT


@api_app.post("/api/v1/telemetry/incident/clear")
def clear_incident(asset_id: str = "VFD_VM_01"):
    """
    Clears the active hardware incident, restores nominal monitoring,
    and resets the TSDB trip triggers so the bench can monitor normally or trip again.
    """
    LATEST_HIL_INCIDENT["has_incident"] = False
    LATEST_HIL_INCIDENT["incident_data"] = None
    LATEST_HIL_INCIDENT["pipeline_status"] = "READY"
    LATEST_HIL_INCIDENT["graph_result"] = None
    LATEST_HIL_INCIDENT["received_at"] = None
    LATEST_HIL_INCIDENT["version"] += 1

    GLOBAL_TSDB.reset_trip()

    if influx_tool.is_simulation_enabled():
        _SIMULATION_STATE["fault_injected"] = False
        _SIMULATION_STATE["phase"] = "NORMAL"

    latest_pt = GLOBAL_TSDB.get_latest(asset_id) or {}
    f_out = float(latest_pt.get("f_out", 40.0))
    rpm = float(latest_pt.get("rpm", 1200.0))
    now = time.time()

    _notify_hil_subscribers({
        "event": "hil_incident_cleared",
        "asset_id": asset_id,
        "status": "READY",
        "has_active_trip": False,
        "has_incident": False,
        "fault_code": 0,
        "f_out": f_out,
        "rpm": rpm,
        "timestamp": now,
        "message": "Incident cleared. Telemetry monitoring resumed nominal state.",
    })

    # Broadcast recovery live metric so 1 Hz telemetry clients immediately synchronize
    recovery_metric = {
        "asset_id": asset_id,
        "f_out": f_out,
        "f_target": float(latest_pt.get("f_target", 40.0)),
        "f_in": float(latest_pt.get("f_in", 40.0)),
        "v_dc": float(latest_pt.get("v_dc", 276.0)),
        "v_bus": float(latest_pt.get("v_bus", 276.0)),
        "v_out": float(latest_pt.get("v_out", 184.0)),
        "current": float(latest_pt.get("current", 0.02)),
        "rpm": rpm,
        "torque": float(latest_pt.get("torque", 0.0)),
        "power": float(latest_pt.get("power", 0.0)),
        "fault_code": 0,
        "status": "RUNNING",
        "has_active_trip": False,
        "has_incident": False,
        "incident_cleared": True,
        "pipeline_status": "READY",
        "timestamp": now,
        "source": "auto_recovery",
    }
    _broadcast_live_metric(recovery_metric)

    return {
        "status": "INCIDENT_CLEARED",
        "message": "Active hardware incident cleared. System restored to real-time nominal monitoring.",
        "latest_incident": LATEST_HIL_INCIDENT,
    }


@api_app.post("/api/v1/rca/reset")
def reset_rca(thread_id: Optional[str] = None):
    """Alias to reset active incident and pipeline state back to normal."""
    return clear_incident()


@api_app.get("/api/v1/telemetry/events/stream")
async def stream_telemetry_events():
    """SSE endpoint for live edge HIL trip alerts push to React UI."""
    queue: asyncio.Queue = asyncio.Queue()
    with _SUBSCRIBER_LOCK:
        _HIL_EVENT_SUBSCRIBERS.append(queue)

    async def event_generator():
        try:
            init_payload = {
                "event": "connection_established",
                "timestamp": time.time(),
                "latest_incident": LATEST_HIL_INCIDENT.get("incident_data"),
            }
            yield f"data: {json.dumps(init_payload)}\n\n"

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'event': 'ping', 'timestamp': time.time()})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            with _SUBSCRIBER_LOCK:
                if queue in _HIL_EVENT_SUBSCRIBERS:
                    _HIL_EVENT_SUBSCRIBERS.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Live VFD Telemetry Metrics & SSE Stream ───────────────────────────

def _enrich_metric_with_simulation_state(m: dict) -> dict:
    if influx_tool.is_simulation_enabled():
        m["simulation_scenario"] = _SIMULATION_STATE.get("scenario", influx_tool.get_simulation_scenario())
        m["simulation_phase"] = _SIMULATION_STATE.get("phase", "IDLE")
        m["simulation_countdown"] = _SIMULATION_STATE.get("countdown", 0.0)
        m["simulation_enabled"] = True
        m["is_simulated"] = True
    return m


@api_app.get("/api/v1/telemetry/live/metrics")
def get_live_telemetry_metrics():
    """Returns the latest single live telemetry metric for the Wecon VFD."""
    m = influx_tool.get_latest_metrics(asset_id="VFD_VM_01")
    return _enrich_metric_with_simulation_state(m)


@api_app.get("/api/v1/telemetry/live/stream")
async def stream_live_telemetry():
    """
    Server-Sent Events (SSE) streaming 1 Hz real-time VFD telemetry metrics
    for live frontend timeseries chart updating and incident alerting.
    """
    queue: asyncio.Queue = asyncio.Queue()
    with _LIVE_STREAM_LOCK:
        _LIVE_STREAM_SUBSCRIBERS.append(queue)

    async def sse_generator():
        try:
            init_metric = await asyncio.to_thread(influx_tool.get_latest_metrics, "VFD_VM_01")
            yield f"data: {json.dumps(_enrich_metric_with_simulation_state(init_metric))}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(_enrich_metric_with_simulation_state(event))}\n\n"
                    continue
                except asyncio.TimeoutError:
                    pass

                metric = await asyncio.to_thread(influx_tool.get_latest_metrics, "VFD_VM_01")
                yield f"data: {json.dumps(_enrich_metric_with_simulation_state(metric))}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        except Exception as e:
            logger.debug(f"SSE client stream closed: {e}")
        finally:
            with _LIVE_STREAM_LOCK:
                if queue in _LIVE_STREAM_SUBSCRIBERS:
                    _LIVE_STREAM_SUBSCRIBERS.remove(queue)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@api_app.post("/api/v1/telemetry/live/feed")
def feed_live_telemetry(metric: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Ingests live telemetry readings directly from MQTT broker listener or Node-RED,
    commits to the embedded TSDB, evaluates autonomous trip conditions, and broadcasts to SSE clients.
    """
    def _unpack(v: Any, default: float = 0.0) -> float:
        if isinstance(v, (list, tuple)):
            v = v[0] if len(v) > 0 else default
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if "err02" in v_clean or v_clean == "2":
                return 2.0
            if "err06" in v_clean or v_clean == "6":
                return 6.0
            if "err03" in v_clean or v_clean == "3":
                return 3.0
            if "err11" in v_clean or v_clean == "11":
                return 11.0
            import re
            nums = re.findall(r"\d+", v_clean)
            if nums:
                try:
                    return float(nums[0])
                except ValueError:
                    pass
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    now = time.time()
    if metric.get("reset") is True or metric.get("clear") is True:
        return clear_incident()

    ts = metric.get("ts", metric.get("timestamp", now))
    if isinstance(ts, str):
        try:
            # Check if ISO format or epoch float
            if "T" in ts:
                # ISO timestamp
                ts = time.time()
            else:
                ts = float(ts)
        except ValueError:
            ts = now

    topic_name = str(metric.get("_mqtt_topic", metric.get("topic", ""))).lower()
    if topic_name.startswith("$") or "broker" in topic_name:
        return {"status": "IGNORED_BROKER_SYS_METRIC"}

    # Ensure this payload contains real equipment telemetry tags
    has_telemetry_tag = any(
        k in metric
        for k in (
            "f_out", "frequency", "f_in", "f_target", "v_dc", "bus_voltage", "v_bus", "v_out",
            "current", "rpm", "fault_code", "fault", "error", "trip", "d_trigger",
        )
    )
    if not has_telemetry_tag:
        return {"status": "IGNORED_NON_TELEMETRY_PAYLOAD"}

    raw_f_out = _unpack(metric.get("f_out", metric.get("frequency", None)))
    if raw_f_out is None:
        latest = GLOBAL_TSDB.get_latest("VFD_VM_01")
        f_out = float(latest.get("f_out", 0.0)) if latest else 0.0
    else:
        # Handle signed 16-bit Modbus rollover if sent as signed int
        if raw_f_out < 0:
            raw_f_out += 65536.0
        # Wecon VM VFD Modbus register 1001H / 3000H resolution is ALWAYS 0.01 Hz (divisor 100.0)
        # e.g., 3000 = 30.00 Hz, 300 = 3.00 Hz, 4000 = 40.00 Hz, 5000 = 50.00 Hz
        if raw_f_out > 60.0:
            f_out = round(raw_f_out / 100.0, 2)
        else:
            f_out = round(raw_f_out, 2)

    raw_f_target = _unpack(metric.get("f_target", metric.get("f_in", None)))
    if raw_f_target is None:
        f_target = f_out
    else:
        # Handle signed 16-bit Modbus rollover (e.g. 50000 sent as -15536)
        if raw_f_target < 0:
            raw_f_target += 65536.0
        # HMI / PLC setpoint register (f_in) resolution is 0.001 Hz or 1 Hz
        # e.g., 30000 = 30.00 Hz, 40 = 40.00 Hz, 4000 = 40.00 Hz
        if raw_f_target > 600.0:
            f_target = round(raw_f_target / 1000.0, 2)
        elif raw_f_target > 60.0:
            f_target = round(raw_f_target / 100.0, 2)
        else:
            f_target = round(raw_f_target, 2)

    raw_rpm = _unpack(metric.get("rpm", None))
    if raw_rpm is None:
        rpm = round(f_out * 29.0, 1) if f_out > 0 else 0.0
    else:
        rpm = round(raw_rpm, 1)

    raw_v_dc = _unpack(metric.get("v_dc", metric.get("bus_voltage", metric.get("v_bus", None))))
    if raw_v_dc is None:
        latest = GLOBAL_TSDB.get_latest("VFD_VM_01")
        v_dc = float(latest.get("v_dc", 0.0)) if latest else 0.0
    else:
        if raw_v_dc > 1000.0:
            v_dc = round(raw_v_dc / 10.0, 1)
        else:
            v_dc = round(raw_v_dc, 1)

    raw_v_out = _unpack(metric.get("v_out", None))
    if raw_v_out is None or raw_v_out <= 0:
        v_out = 220.0 if f_out > 0 else 0.0
    else:
        v_out = round(raw_v_out, 1)

    raw_current_val = metric.get("current", 0.0)
    raw_current = _unpack(raw_current_val, 0.0)
    # Physical Wecon VM Modbus register (1004H / 3005H) resolution is ALWAYS 0.01 A (e.g. 2 = 0.02 A, 115 = 1.15 A, 250 = 2.50 A).
    # Packets from edge gateway contain raw counts inside single-element lists/tuples [2] or raw integers 2.
    is_modbus_raw = (
        isinstance(raw_current_val, (list, tuple))
        or isinstance(raw_current_val, int)
        or (isinstance(raw_current_val, str) and "." not in raw_current_val)
        or raw_current > 10.0
    )
    if is_modbus_raw:
        current = round(raw_current / 100.0, 2)
    else:
        current = round(raw_current, 2)

    # Check for trip code across explicit industrial fault keys
    raw_fault = None
    for key in ("fault_code", "fault", "error", "error_code", "trip", "trip_code", "reg_700b", "700bh"):
        if metric.get(key) is not None:
            raw_fault = metric.get(key)
            break

    if raw_fault is None:
        topic_name = str(metric.get("_mqtt_topic", metric.get("topic", ""))).lower()
        if any(w in topic_name for w in ("fault", "error", "trip", "alarm", "700b")):
            if "err02" in topic_name or "error02" in topic_name:
                raw_fault = 2
            elif "err06" in topic_name or "error06" in topic_name:
                raw_fault = 6
            elif "err03" in topic_name or "error03" in topic_name:
                raw_fault = 3
            elif "err11" in topic_name or "error11" in topic_name:
                raw_fault = 11
            elif "err13" in topic_name or "error13" in topic_name:
                raw_fault = 13

    raw_torque_val = metric.get("torque", metric.get("Torque", metric.get("d006", metric.get("D006", 0.0))))
    raw_torque = _unpack(raw_torque_val, 0.0)
    # Wecon VM Modbus register 1006H (D006) resolution is 0.1% (e.g. 22 = 2.2%, 12 = 1.2%, 100 = 10.0%).
    # Packets from edge gateway contain raw counts inside single-element lists/tuples [22] or raw integers 22.
    is_torque_modbus_raw = (
        isinstance(raw_torque_val, (list, tuple))
        or (isinstance(raw_torque_val, int) and not isinstance(raw_torque_val, bool))
        or (isinstance(raw_torque_val, str) and "." not in raw_torque_val and raw_torque_val.strip().isdigit())
        or raw_torque > 15.0
    )
    if is_torque_modbus_raw:
        torque = round(raw_torque / 10.0, 1)
    else:
        torque = round(raw_torque, 1)

    raw_power_val = metric.get("power", metric.get("Power", metric.get("d005", metric.get("D005", 0.0))))
    raw_power = _unpack(raw_power_val, 0.0)
    # Wecon VM Modbus register 1005H (D005) resolution is 0.1 kW (e.g. 2 = 0.2 kW, 15 = 1.5 kW).
    is_power_modbus_raw = (
        isinstance(raw_power_val, (list, tuple))
        or (isinstance(raw_power_val, int) and not isinstance(raw_power_val, bool))
        or (isinstance(raw_power_val, str) and "." not in raw_power_val and raw_power_val.strip().isdigit())
        or raw_power > 5.0
    )
    if is_power_modbus_raw:
        power = round(raw_power / 10.0, 2)
    else:
        power = round(raw_power, 2)

    raw_v_bus = _unpack(metric.get("v_bus", v_dc))

    # Detect and persist any parameter updates passed in MQTT metric payload
    param_keys = ("f0.02", "f0.03", "f0.10", "f0.17", "f0.18", "f1.00", "f2.03", "f9.01", "decel", "accel")
    for mk, mv in metric.items():
        low_mk = mk.lower().replace("_", ".")
        for pk in param_keys:
            if pk in low_mk:
                clean_pk = mk.upper().replace("_", ".")
                try:
                    p_val = float(_unpack(mv))
                    GLOBAL_TSDB.set_parameter(clean_pk, p_val, f"Updated via MQTT {topic_name}")
                except Exception:
                    pass

    fault_code = int(_unpack(raw_fault, 0) if raw_fault is not None else 0)
    status = "TRIPPED" if fault_code > 0 else "RUNNING"
    asset_id = str(metric.get("asset_id", "VFD_VM_01"))

    has_trip = fault_code > 0
    is_nominal_running = (fault_code == 0) and (f_out > 0.5 or rpm > 10.0 or metric.get("reset") or status == "RUNNING")

    normalized = {
        "asset_id": asset_id,
        "f_out": f_out,
        "f_target": f_target,
        "f_in": f_target,
        "v_dc": v_dc,
        "v_bus": round(raw_v_bus / 10.0 if raw_v_bus > 1000.0 else raw_v_bus, 1) if raw_v_bus else v_dc,
        "v_out": v_out,
        "current": current,
        "rpm": rpm,
        "torque": torque,
        "power": power,
        "fault_code": fault_code,
        "status": status,
        "timestamp": ts if isinstance(ts, (int, float)) else now,
        "source": "mqtt_live",
    }

    # 1. Commit to high-performance embedded TSDB
    GLOBAL_TSDB.insert(normalized)

    # 2. Autonomous Trip Detection: When fault occurs, slice 60s pre-fault window and dispatch RCA
    trip_code = GLOBAL_TSDB.check_trip_trigger(normalized)
    if trip_code is not None:
        try:
            df_pre = GLOBAL_TSDB.get_window(seconds=60, asset_id=asset_id)
            pre_points = df_pre.to_dict("records")
            fault_info = get_vfd_fault_info(trip_code)
            fault_desc = fault_info.get("description", f"WECON VM VFD Trip Code {trip_code}")
            inc = IncidentPayload(
                asset_id=asset_id,
                fault_code=trip_code,
                fault_description=fault_desc,
                incident_id=f"INC-AUTO-{int(now)}",
                pre_fault_telemetry=pre_points,
            )
            ingest_incident(inc, background_tasks)
        except Exception as e:
            logger.warning(f"Auto-trip dispatch error: {e}")
    elif is_nominal_running:
        # Auto-clear active incident when equipment recovers and runs nominally with fault_code == 0
        if LATEST_HIL_INCIDENT.get("has_incident") or LATEST_HIL_INCIDENT.get("pipeline_status") != "READY" or getattr(GLOBAL_TSDB, "_last_fault_code", 0) > 0:
            logger.info("Equipment healthy and running (fault_code=0). Auto-clearing active incident.")
            clear_incident(asset_id=asset_id)

    normalized["has_active_trip"] = has_trip
    normalized["has_incident"] = LATEST_HIL_INCIDENT.get("has_incident", False)
    normalized["incident_cleared"] = not has_trip and not LATEST_HIL_INCIDENT.get("has_incident", False)
    normalized["pipeline_status"] = LATEST_HIL_INCIDENT.get("pipeline_status", "READY")

    # 3. Update active tools & broadcast live metric to connected SSE frontend clients
    influx_tool.update_latest(normalized)
    _broadcast_live_metric(normalized)

    return {"status": "INGESTED", "metric": normalized, "tsdb_buffered": True}


# ── Embedded TSDB History & Parameter APIs ──────────────────────────

class ParameterUpdateRequest(BaseModel):
    key: str
    value: float
    description: Optional[str] = ""
    asset_id: Optional[str] = "VFD_VM_01"


@api_app.get("/api/v1/telemetry/parameters")
def get_vfd_parameters(asset_id: str = "VFD_VM_01"):
    """Returns active VFD control parameters with current values and descriptions."""
    return {
        "asset_id": asset_id,
        "parameters": GLOBAL_TSDB.get_parameters(asset_id=asset_id),
    }


@api_app.post("/api/v1/telemetry/parameters")
def set_vfd_parameter(req: ParameterUpdateRequest):
    """Updates and persists a VFD control parameter."""
    updated = GLOBAL_TSDB.set_parameter(
        param_key=req.key,
        param_value=req.value,
        param_desc=req.description or "Configured via Dashboard UI",
        asset_id=req.asset_id or "VFD_VM_01",
    )
    return {
        "status": "UPDATED",
        "key": req.key,
        "parameter": updated,
        "all_parameters": GLOBAL_TSDB.get_parameters(),
    }


@api_app.get("/api/v1/telemetry/parameters/history")
def get_vfd_parameter_history(key: Optional[str] = None, limit: int = 50, asset_id: str = "VFD_VM_01"):
    """Returns audit trail history of VFD parameter updates."""
    history = GLOBAL_TSDB.get_parameter_history(param_key=key, limit=limit, asset_id=asset_id)
    return {
        "asset_id": asset_id,
        "count": len(history),
        "history": history,
    }


@api_app.get("/api/v1/telemetry/tsdb/history")
def get_tsdb_history(seconds: int = 120, asset_id: str = "VFD_VM_01"):
    """
    Returns the historical telemetry window from the embedded TSDB.
    Used by frontend charts to instantly pre-fill upon load.
    """
    df = GLOBAL_TSDB.get_window(seconds=seconds, asset_id=asset_id)
    records = df.to_dict("records") if not df.empty else []
    return {
        "asset_id": asset_id,
        "seconds": seconds,
        "count": len(records),
        "history": records,
    }


@api_app.get("/api/v1/telemetry/tsdb/stats")
def get_tsdb_stats(seconds: int = 300):
    """
    Returns real-time statistical performance, buffer health, and metrics of the embedded TSDB.
    """
    return GLOBAL_TSDB.get_stats(seconds=seconds)


# ── Scenarios Catalog ─────────────────────────────────────────────────

@api_app.get("/api/v1/scenarios")
def list_scenarios():
    _ensure_default_scenarios()
    scenarios = [
        {
            "id": "live_stream",
            "dataset_id": SCENARIOS_REGISTRY.get("live_stream", "ds_live_stream"),
            "name": "⚡ LIVE: Physical Wecon VFD Rig",
            "asset_id": "VFD_VM_01",
            "condition": "LIVE_STREAM",
            "description": "Continuous 1 Hz real-time telemetry from physical Wecon HMI (192.168.1.104) and VFD test bench via MQTT broker.",
            "duration_sec": 300,
            "has_trip": False,
            "badge": "LIVE_EDGE",
        }
    ]
    if LATEST_HIL_INCIDENT.get("has_incident"):
        inc = LATEST_HIL_INCIDENT["incident_data"]
        scenarios.append({
            "id": inc.get("dataset_id", "hil"),
            "dataset_id": inc.get("dataset_id"),
            "name": f"🚨 Active Hardware Trip: {inc.get('fault_description', 'VFD Trip')}",
            "asset_id": inc.get("asset_id", "VFD_VM_01"),
            "condition": "HARDWARE_FAULT_TRIP",
            "description": f"Live incident received from physical edge test bench via MQTT. Fault code {inc.get('fault_code')}.",
            "duration_sec": inc.get("point_count", 60),
            "has_trip": True,
            "badge": "HARDWARE_FAULT",
        })
    return {"scenarios": scenarios}


# ── Telemetry Timeseries & Spectrum ───────────────────────────────────

def _resolve_ds(dataset_id: str) -> TelemetryDataset:
    _ensure_default_scenarios()
    if dataset_id in ("live_stream", "ds_live_stream"):
        ds = generate_vfd_dataset(scenario="live_stream")
        TelemetryStore.register(ds, "ds_live_stream")
        SCENARIOS_REGISTRY["live_stream"] = "ds_live_stream"
        return ds

    if dataset_id in ("exp_err02", "ds_exp_err02"):
        ds = generate_vfd_dataset(scenario="exp_err02")
        TelemetryStore.register(ds, "ds_exp_err02")
        SCENARIOS_REGISTRY["exp_err02"] = "ds_exp_err02"
        return ds

    if dataset_id in ("exp_err06", "ds_exp_err06", "fault", "ds_fault"):
        ds = generate_vfd_dataset(scenario="exp_err06")
        TelemetryStore.register(ds, "ds_exp_err06")
        SCENARIOS_REGISTRY["exp_err06"] = "ds_exp_err06"
        return ds

    if "exp_err13" in dataset_id or dataset_id in ("exp_err13", "ds_exp_err13"):
        ds = generate_vfd_dataset(scenario="exp_err13")
        TelemetryStore.register(ds, "ds_exp_err13")
        SCENARIOS_REGISTRY["exp_err13"] = "ds_exp_err13"
        return ds

    if dataset_id in ("exp_nominal", "ds_exp_nominal", "normal", "ds_normal"):
        ds = generate_vfd_dataset(scenario="exp_nominal")
        TelemetryStore.register(ds, "ds_exp_nominal")
        SCENARIOS_REGISTRY["exp_nominal"] = "ds_exp_nominal"
        return ds

    actual_id = SCENARIOS_REGISTRY.get(dataset_id, dataset_id)
    try:
        return TelemetryStore.get(actual_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Dataset unavailable or expired")


@api_app.get("/api/v1/telemetry/{dataset_id}")
def get_telemetry_series(dataset_id: str):
    ds = _resolve_ds(dataset_id)
    df = ds.df_1hz

    timestamps = ds.get_timestamps().tolist() if not df.empty else []
    series_data: Dict[str, List[float]] = {}
    skip_cols = {"timestamp_sec", "timestamp", "asset_id", "status", "_time", "_measurement", "_field", "result", "table"}
    for col in df.columns:
        if col in skip_cols:
            continue
        try:
            values = pd.to_numeric(df[col], errors="coerce").round(3)
            series_data[col] = [float(value) if pd.notna(value) and math.isfinite(value) else None for value in values]
        except Exception:
            pass

    combined_limits = dict(OPERATIONAL_LIMITS)
    from industrial_rca.config import VFD_OPERATIONAL_LIMITS
    combined_limits.update(VFD_OPERATIONAL_LIMITS)

    return {
        "dataset_id": dataset_id,
        "scenario_name": ds.scenario_name,
        "metadata": ds.metadata,
        "sample_count": len(df),
        "timestamps": timestamps,
        "series": series_data,
        "operational_limits": combined_limits,
    }


@api_app.get("/api/v1/telemetry/{dataset_id}/spectrum")
def get_telemetry_spectrum(dataset_id: str):
    ds = _resolve_ds(dataset_id)
    is_fault = ds.metadata.get("condition") != "HEALTHY"
    wf_data = ds.fault_waveform if is_fault else ds.normal_waveform
    if "signal" not in wf_data or not len(wf_data["signal"]):
        return {"dataset_id": dataset_id, "available": False, "reason": "No waveform was supplied",
                "analysis": {}, "frequencies": [], "magnitudes": []}
    signal = wf_data["signal"]
    sampling_rate = HIGH_FREQ_SAMPLING_RATE_HZ

    spec_analysis = analytics_tool.spectral_analyzer.analyze_spectrum(signal)

    # Downsample FFT for smooth 60fps canvas visualization (600 frequency bins up to 10 kHz)
    n_samples = len(signal)
    fft_vals = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / sampling_rate)
    mag = np.abs(fft_vals) * 2.0 / n_samples

    mask_10k = freqs <= 10000.0
    f_sub = freqs[mask_10k]
    m_sub = mag[mask_10k]

    stride = max(1, len(f_sub) // 600)
    freqs_downsampled = f_sub[::stride].round(1).tolist()
    mags_downsampled = m_sub[::stride].round(4).tolist()

    return {
        "dataset_id": dataset_id,
        "analysis": spec_analysis,
        "frequencies": freqs_downsampled,
        "magnitudes": mags_downsampled,
        "shaft_1x_hz": RUNNING_FREQUENCY_1X_HZ,
        "shaft_2x_hz": RUNNING_FREQUENCY_2X_HZ,
        "cavitation_band": list(CAVITATION_BROADBAND_BAND_HZ),
    }


# ── ISA-95 Asset Topology ─────────────────────────────────────────────

@api_app.get("/api/v1/topology/{asset_id}")
def get_asset_topology(asset_id: str):
    eq = topology_tracer.get_equipment(asset_id)
    if not eq:
        raise HTTPException(status_code=404, detail="Asset topology is unavailable")

    upstream = topology_tracer.trace_upstream(asset_id)
    downstream = topology_tracer.trace_downstream(asset_id)

    nodes = []
    edges = []

    all_involved = [eq] + [topology_tracer.get_equipment(u["asset_id"]) for u in upstream] + [topology_tracer.get_equipment(d["asset_id"]) for d in downstream]
    seen_ids = set()

    pos_map = {
        "TK-300": {"x": 80, "y": 200},
        "LINE-30101": {"x": 260, "y": 200},
        "STR-301A": {"x": 440, "y": 200},
        "P-301A": {"x": 640, "y": 200},
        "M-301A": {"x": 640, "y": 80},
        "VFD_VM_01": {"x": 440, "y": 80},
        "HMI_TOUCH_01": {"x": 260, "y": 80},
        "MOTOR_M01": {"x": 640, "y": 80},
        "CV-30101": {"x": 840, "y": 200},
        "HDR-300": {"x": 1020, "y": 200},
    }

    for item in all_involved:
        if not item or item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        coords = pos_map.get(item["id"], {"x": 500, "y": 300})

        nodes.append({
            "id": item["id"],
            "name": item.get("name", item["id"]),
            "type": item.get("type", "Equipment"),
            "isa95_level": item.get("isa95_level", 2),
            "sensors": item.get("sensors", []),
            "operating_specs": item.get("operating_specs", {}),
            "status": "UNKNOWN",
            "position": coords,
        })

    for edge in topology_tracer.edges:
        if edge["source"] in seen_ids and edge["target"] in seen_ids:
            edges.append({
                "source": edge["source"],
                "target": edge["target"],
                "relation": edge.get("relation", "connected_to"),
                "medium": edge.get("medium", ""),
            })

    return {
        "target_asset": eq,
        "isa95_hierarchy": topology_tracer.hierarchy,
        "upstream_chain": upstream,
        "downstream_chain": downstream,
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
    }


# ── LangGraph RCA Pipeline ────────────────────────────────────────────

def _get_step_number(state_vals: Dict[str, Any], is_paused: bool) -> int:
    if state_vals.get("pipeline_status") in ("COMPLETED", "REJECTED"):
        return 7
    if state_vals.get("pipeline_status") == "INCONCLUSIVE":
        return 4
    if state_vals.get("pipeline_status") == "INVESTIGATING":
        return 4
    if is_paused or state_vals.get("human_review_required"):
        return 6
    status = state_vals.get("pipeline_status", "")
    if status == "INGESTED":
        return 1
    if status in ("ANOMALIES_DETECTED", "NORMAL_STABLE"):
        return 2
    if status == "HYPOTHESES_FORMULATED":
        return 3
    if status in ("HYPOTHESES_TESTED", "HYPOTHESES_AGGREGATED"):
        return 4
    if status == "CAUSAL_TRACE_COMPLETED":
        return 5
    return 1


@api_app.get("/api/v1/rca/state/{thread_id}")
def get_rca_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = GLOBAL_RCA_GRAPH.get_state(config)

    if not state_snapshot or not state_snapshot.values:
        return {
            "thread_id": thread_id,
            "pipeline_status": "NOT_STARTED",
            "current_step": 0,
            "is_paused_at_hitl": False,
            "has_active_trip": False,
            "detected_anomalies": [],
            "tag_profiles": {},
            "hypothesis_results": [],
            "winning_hypothesis": None,
            "falsification_summary": [],
            "fmea_classification": {},
            "causal_chain_5_whys": [],
            "root_cause_asset": "",
            "root_cause_description": "",
            "human_review_required": False,
            "human_review_payload": None,
            "human_review_decision": None,
            "incident_report_8d": None,
            "sap_work_order": None,
            "execution_logs": [],
            "deepseek_evaluation": None,
        }

    vals = state_snapshot.values
    is_paused = bool(state_snapshot.tasks and state_snapshot.tasks[0].interrupts)
    current_step = _get_step_number(vals, is_paused)

    review_payload = vals.get("human_review_payload")
    if is_paused and not review_payload and state_snapshot.tasks[0].interrupts:
        review_payload = state_snapshot.tasks[0].interrupts[0].value

    return {
        "thread_id": thread_id,
        "pipeline_status": "AWAITING_REVIEW" if is_paused else vals.get("pipeline_status", "UNKNOWN"),
        "current_step": current_step,
        "is_paused_at_hitl": is_paused,
        "has_active_trip": vals.get("has_active_trip", False),
        "detected_anomalies": vals.get("detected_anomalies", []),
        "tag_profiles": vals.get("tag_profiles", {}),
        "hypothesis_results": vals.get("hypothesis_results", []),
        "winning_hypothesis": vals.get("winning_hypothesis"),
        "falsification_summary": vals.get("falsification_summary", []),
        "fmea_classification": vals.get("fmea_classification", {}),
        "causal_chain_5_whys": vals.get("causal_chain_5_whys", []),
        "root_cause_asset": vals.get("root_cause_asset", ""),
        "root_cause_description": vals.get("root_cause_description", ""),
        "human_review_required": is_paused or vals.get("human_review_required", False),
        "human_review_payload": review_payload,
        "human_review_decision": vals.get("human_review_decision"),
        "incident_report_8d": vals.get("incident_report_8d"),
        "sap_work_order": vals.get("sap_work_order"),
        "execution_logs": vals.get("execution_logs", []),
        "deepseek_evaluation": vals.get("deepseek_evaluation"),
        "investigation_trace": vals.get("investigation_trace", []),
        "agent_observations": vals.get("agent_observations", []),
        "missing_evidence": vals.get("missing_evidence", []),
        "fault_code": vals.get("fault_code") or vals.get("trip_metadata", {}).get("fault_code", 0),
    }


@api_app.post("/api/v1/rca/run")
def run_rca_pipeline(request: RCARunRequest):
    _ensure_default_scenarios()
    thread_id = request.thread_id or f"rca-thread-{int(time.time())}"
    config = {"configurable": {"thread_id": thread_id}}

    actual_ds_id = SCENARIOS_REGISTRY.get(request.dataset_id, request.dataset_id)
    _ = _resolve_ds(actual_ds_id)

    fc_from_ds = 0
    ds_obj = TelemetryStore.get(actual_ds_id)
    if ds_obj and ds_obj.metadata:
        fc_from_ds = int(ds_obj.metadata.get("fault_code", 0) or 0)

    init_state = {
        "dataset_id": actual_ds_id,
        "asset_id": request.asset_id,
        "fault_code": fc_from_ds,
        "use_deepseek": request.use_deepseek,
        "deepseek_model": request.deepseek_model,
    }

    for _ in GLOBAL_RCA_GRAPH.stream(init_state, config=config):
        pass

    state_snapshot = GLOBAL_RCA_GRAPH.get_state(config)
    vals = state_snapshot.values if state_snapshot else {}
    is_paused = bool(state_snapshot and state_snapshot.tasks and state_snapshot.tasks[0].interrupts)

    review_payload = vals.get("human_review_payload")
    if is_paused and not review_payload and state_snapshot.tasks[0].interrupts:
        review_payload = state_snapshot.tasks[0].interrupts[0].value

    return {
        "status": "SUCCESS",
        "thread_id": thread_id,
        "pipeline_status": "AWAITING_REVIEW" if is_paused else vals.get("pipeline_status", "UNKNOWN"),
        "is_paused_at_hitl": is_paused,
        "current_step": _get_step_number(vals, is_paused),
        "has_active_trip": vals.get("has_active_trip", False),
        "anomaly_event": vals.get("anomaly_event"),
        "hypotheses": vals.get("hypotheses", []),
        "tested_hypotheses": vals.get("tested_hypotheses", []),
        "winning_hypothesis": vals.get("winning_hypothesis"),
        "causal_trace": vals.get("causal_trace"),
        "root_cause_asset": vals.get("root_cause_asset"),
        "root_cause_description": vals.get("root_cause_description"),
        "human_review_payload": review_payload,
        "incident_report_8d": vals.get("incident_report_8d"),
        "sap_work_order": vals.get("sap_work_order"),
        "execution_logs": vals.get("execution_logs", []),
        "deepseek_evaluation": vals.get("deepseek_evaluation"),
        "investigation_trace": vals.get("investigation_trace", []),
        "agent_observations": vals.get("agent_observations", []),
        "missing_evidence": vals.get("missing_evidence", []),
        "fault_code": vals.get("fault_code") or vals.get("trip_metadata", {}).get("fault_code", fc_from_ds),
    }


@api_app.post("/api/v1/rca/human-review")
def submit_human_review(request: HumanReviewRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    state_snapshot = GLOBAL_RCA_GRAPH.get_state(config)

    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail=f"Thread '{request.thread_id}' not found.")
    if not state_snapshot.tasks or not state_snapshot.tasks[0].interrupts:
        raise HTTPException(status_code=409, detail="This investigation is not awaiting human review")
    if request.action == "override" and not (request.override_root_cause or "").strip():
        raise HTTPException(status_code=422, detail="An override requires a root cause statement")

    action = request.action.lower().strip()
    decision_payload = {
        "action": action,
        "reviewer": request.reviewer,
        "notes": request.notes,
        "override_root_cause": request.override_root_cause,
    }

    for _ in GLOBAL_RCA_GRAPH.stream(Command(resume=decision_payload), config=config):
        pass

    final_snapshot = GLOBAL_RCA_GRAPH.get_state(config)
    vals = final_snapshot.values if final_snapshot else {}
    pipeline_status = vals.get("pipeline_status", "COMPLETED")

    # If this matches the active HIL incident, synchronize state and broadcast SSE
    active_inc_thread = (LATEST_HIL_INCIDENT.get("incident_data") or {}).get("thread_id")
    if active_inc_thread == request.thread_id:
        LATEST_HIL_INCIDENT["graph_result"] = vals
        LATEST_HIL_INCIDENT["pipeline_status"] = pipeline_status
        _notify_hil_subscribers({
            "event": "hil_human_review_submitted",
            "thread_id": request.thread_id,
            "action": action,
            "reviewer": request.reviewer,
            "status": pipeline_status,
            "timestamp": time.time(),
        })

    return {
        "status": "RESUMED",
        "thread_id": request.thread_id,
        "pipeline_status": pipeline_status,
        "current_step": 7,
        "decision": decision_payload,
        "incident_report_8d": vals.get("incident_report_8d"),
        "sap_work_order": vals.get("sap_work_order"),
        "root_cause_description": vals.get("root_cause_description"),
        "execution_logs": vals.get("execution_logs", []),
        "deepseek_evaluation": vals.get("deepseek_evaluation"),
        "investigation_trace": vals.get("investigation_trace", []),
        "agent_observations": vals.get("agent_observations", []),
        "missing_evidence": vals.get("missing_evidence", []),
        "fault_code": vals.get("fault_code") or vals.get("trip_metadata", {}).get("fault_code", 0),
    }


# ── DeepSeek AI Copilot Streaming ─────────────────────────────────────

def build_copilot_system_prompt(thread_id: Optional[str] = None) -> str:
    """Stable evidence rules followed by fresh, explicitly sourced context."""
    from industrial_rca.agent.runtime import SYSTEM_PROMPT

    lines = [
        "You are the Industrial RCA copilot. Answer using the supplied incident and telemetry context.",
        "=== DOMAIN KNOWLEDGE & EXPERT RULES ===",
        SYSTEM_PROMPT,
        "This chat explains observations; it does not execute diagnostic tools. Never claim a tool ran in chat.",
        "Protection-code references describe possible mechanisms, not a diagnosis. Do not infer wiring, PLC logic, "
        "braking-resistor presence, or hardware parameter readback from a fault code or a configured topology.",
        "No universal safe voltage or current is implied. Operational limits are installation configuration "
        "and must be checked against the actual equipment. Never choose a voltage limit by guessing rig type from a reading.",
        "When telemetry is offline, say measurements are unavailable. Zero is not a substitute for missing data. "
        "Always identify simulated data. Explain evidence gaps and propose measurements to resolve uncertainty. "
        "User-entered configuration is not verified hardware readback. Do not invent engineering settings or part ratings.",
        "=== REAL-TIME TELEMETRY & INVESTIGATION STATE (DYNAMIC) ===",
    ]
    simulated = influx_tool.is_simulation_enabled()
    latest = GLOBAL_TSDB.get_latest(EQUIPMENT_ID) or {}
    age = time.time() - latest.get("timestamp", 0)
    fresh = bool(latest and -5 <= age < 30)
    if simulated:
        latest = influx_tool.get_latest_metrics(EQUIPMENT_ID)
    elif not fresh:
        latest = {}
    lines.append(f"Telemetry source: {'SIMULATED' if simulated else 'MEASURED' if fresh else 'OFFLINE / UNAVAILABLE'}")
    for label, tag, precision, unit in [
        ("Output Frequency", "f_out", 2, "Hz"), ("Frequency Target", "f_target", 2, "Hz"),
        ("DC Bus Voltage", "v_dc", 1, "V"), ("Motor Output Current", "current", 2, "A"),
        ("Rotor Speed", "rpm", 0, "RPM"), ("Output Voltage", "v_out", 1, "V"),
    ]:
        value = latest.get("v_bus", latest.get("v_dc")) if tag == "v_dc" else latest.get(tag)
        try:
            reading = float(value)
            rendered = f"{reading:.{precision}f} {unit}" if math.isfinite(reading) else "Unavailable"
        except (TypeError, ValueError):
            rendered = "Unavailable"
        lines.append(f"- {label}: {rendered}")
    lines.append("Configured operational limits (not independently verified): " + json.dumps(OPERATIONAL_LIMITS))
    lines.append("Configured parameters (hardware readback unverified): " + json.dumps(GLOBAL_TSDB.get_parameters(EQUIPMENT_ID)))
    incident = LATEST_HIL_INCIDENT.get("incident_data") if LATEST_HIL_INCIDENT.get("has_incident") else None
    lines.append("Reported incident: " + json.dumps(incident))
    target = thread_id or (incident or {}).get("thread_id")
    if target:
        snapshot = GLOBAL_RCA_GRAPH.get_state({"configurable": {"thread_id": target}})
        values = snapshot.values if snapshot else {}
        lines.append("Investigation: " + json.dumps({key: values.get(key) for key in (
            "pipeline_status", "winning_hypothesis", "root_cause_description", "missing_evidence", "investigation_trace",
        )}))
    return "\n".join(lines)


@api_app.post("/api/v1/copilot/chat/stream")
def stream_copilot_chat(request: CopilotChatRequest):
    """
    Server-Sent Events (SSE) streaming endpoint for DeepSeek AI Copilot.
    Streams token deltas for both content and reasoning_content chunk by chunk.
    Automatically injects grounded real-time telemetry, asset topology, and RCA state context.
    """
    model = request.model or deepseek_client.default_model
    raw_messages = request.messages

    # Inject rich real-time context as system prompt
    system_prompt = build_copilot_system_prompt(request.thread_id)
    messages = []
    has_system = False
    for m in raw_messages:
        if m.get("role") == "system":
            messages.append({"role": "system", "content": system_prompt})
            has_system = True
        else:
            messages.append(m)
    if not has_system:
        messages.insert(0, {"role": "system", "content": system_prompt})

    def sse_event_generator() -> Generator[str, None, None]:
        try:
            for delta in deepseek_client.chat_completion_stream(
                messages=messages,
                model=model,
            ):
                json_data = json.dumps(delta)
                yield f"data: {json_data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            err_data = json.dumps({"error": str(e)})
            yield f"data: {err_data}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── DeepSeek API Key & .env Management Endpoints ──────────────────────────────

@api_app.get("/api/v1/settings/api-key")
def get_api_key_settings():
    """
    Returns current API key configuration and status.
    Masks the secret key to prevent plaintext exposure.
    """
    return get_api_key_status()


@api_app.post("/api/v1/settings/api-key")
def save_api_key_settings(req: ApiKeySaveRequest):
    """
    Saves API key to the root .env file, updates os.environ,
    and dynamically reconfigures active DeepSeek client instances.
    """
    try:
        status = save_api_key(
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
        )
        return status
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save API key to .env: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save API key to .env: {str(e)}")


@api_app.post("/api/v1/settings/api-key/test")
def test_api_key_settings(req: ApiKeyTestRequest):
    """
    Tests API connectivity with provided credentials or the currently configured API key.
    """
    try:
        return test_api_credentials(
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
        )
    except Exception as e:
        return {
            "success": False,
            "status": "FAILED",
            "is_live": False,
            "message": f"Connection test failed: {str(e)}",
        }


@api_app.delete("/api/v1/settings/api-key")
def delete_api_key_settings():
    """
    Removes DEEPSEEK_API_KEY from .env, removes from os.environ,
    and disables model investigation until reconfigured.
    """
    try:
        return delete_api_key()
    except Exception as e:
        logger.error(f"Failed to delete API key: {e}")

# ── Telegram Bot Lifecycle & Management Endpoints ──────────────────────

@api_app.get("/api/v1/bot/status")
def get_bot_status():
    """Returns Telegram Bot connection status, subscriber count, and configuration."""
    token_configured = bool(telegram_bot_service.token)
    masked_token = (
        f"{telegram_bot_service.token[:6]}...{telegram_bot_service.token[-4:]}"
        if token_configured and len(telegram_bot_service.token) > 10
        else ("CONFIGURED" if token_configured else "NOT_CONFIGURED")
    )
    return {
        "status": "ONLINE" if telegram_bot_service.is_running else ("READY" if token_configured else "UNCONFIGURED"),
        "is_configured": token_configured,
        "is_polling": telegram_bot_service.is_running,
        "token_masked": masked_token,
        "default_chat_id": telegram_bot_service.default_chat_id,
        "subscribers_count": len(telegram_bot_service.subscribers),
        "subscribers": list(telegram_bot_service.subscribers),
        "dashboard_url": telegram_bot_service.dashboard_url,
    }


@api_app.post("/api/v1/bot/test-alert")
async def send_bot_test_alert(req: Optional[BotTestAlertRequest] = None):
    """Sends a verification test alert with sample waveform to subscribers or specific chat ID."""
    if not telegram_bot_service.client:
        raise HTTPException(
            status_code=400,
            detail="Telegram Bot is not configured. Please set TELEGRAM_BOT_TOKEN in .env or via /api/v1/bot/settings",
        )

    targets = [req.chat_id] if (req and req.chat_id) else list(telegram_bot_service.subscribers)
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="No subscribers registered. Please send /start to your bot in Telegram or provide a chat_id.",
        )

    msg_text = (req and req.message) or (
        "🧪 <b>TEST ALERT — Industrial RCA Bot</b>\n\n"
        "• <b>Status:</b> Two-way communication verified\n"
        "• <b>Platform:</b> Industrial Root Cause Analysis Engine\n"
        "• <b>Sync:</b> React Web App + FastAPI Backend active"
    )

    from industrial_rca.bot.chart_generator import generate_trip_waveform
    sample_waveform = generate_trip_waveform(pd.DataFrame(), fault_code=6, title_suffix="Test Verification")

    keyboard = telegram_bot_service.client.build_inline_keyboard([
        [
            {"text": "📊 View Status", "callback_data": "refresh_telemetry"},
            {"text": "🔗 Web App", "url": telegram_bot_service.dashboard_url},
        ]
    ])

    sent_count = 0
    errors = []
    for cid in targets:
        try:
            await telegram_bot_service.client.send_photo(
                chat_id=cid,
                photo_bytes=sample_waveform,
                caption=msg_text,
                reply_markup=keyboard,
            )
            sent_count += 1
        except Exception as e:
            errors.append(f"Chat {cid}: {str(e)}")

    return {
        "status": "SUCCESS" if sent_count > 0 else "FAILED",
        "recipients_reached": sent_count,
        "recipients_total": len(targets),
        "errors": errors,
    }


@api_app.post("/api/v1/bot/settings")
async def update_bot_settings(req: BotSettingsRequest):
    """Updates Telegram bot token and target chat ID dynamically."""
    if req.bot_token is not None:
        telegram_bot_service.token = req.bot_token
        from industrial_rca.bot.telegram_client import TelegramClient
        telegram_bot_service.client = TelegramClient(req.bot_token) if req.bot_token else None

    if req.default_chat_id is not None:
        telegram_bot_service.default_chat_id = req.default_chat_id
        if req.default_chat_id:
            telegram_bot_service.add_subscriber(req.default_chat_id)

    if req.dashboard_url is not None:
        telegram_bot_service.dashboard_url = req.dashboard_url

    # Persist credentials into .env file
    try:
        from industrial_rca.utils.env_manager import save_telegram_credentials
        save_telegram_credentials(
            bot_token=req.bot_token,
            default_chat_id=req.default_chat_id,
            dashboard_url=req.dashboard_url,
        )
    except Exception as e:
        logger.warning(f"Failed to persist Telegram credentials to .env: {e}")

    # Restart polling loop if token changed and is valid
    if telegram_bot_service.token and not telegram_bot_service.is_running:
        telegram_bot_service.start_background_polling()

    return get_bot_status()


class BotCallbackSimulateRequest(BaseModel):
    thread_id: str
    action: str = "approved"
    reviewer: str = "@chief_engineer (Telegram)"


@api_app.post("/api/v1/bot/simulate-callback")
async def simulate_bot_callback(req: BotCallbackSimulateRequest):
    """Simulates a Telegram user clicking [✅ Approve Remediation] or [❌ Reject Remediation]."""
    if telegram_bot_service:
        await telegram_bot_service._execute_hitl_action(
            action=req.action,
            thread_id=req.thread_id,
            reviewer=req.reviewer,
            chat_id=telegram_bot_service.default_chat_id or "simulated_chat",
            message_id=None,
            orig_text="[Telegram Card: Active Trip Alert]",
        )
        final_snapshot = GLOBAL_RCA_GRAPH.get_state({"configurable": {"thread_id": req.thread_id}})
        vals = final_snapshot.values if final_snapshot else {}
        return {
            "status": "SUCCESS",
            "thread_id": req.thread_id,
            "action": req.action,
            "reviewer": req.reviewer,
            "pipeline_status": vals.get("pipeline_status", "COMPLETED"),
            "current_step": 7,
            "incident_report_8d": vals.get("incident_report_8d"),
            "sap_work_order": vals.get("sap_work_order"),
        }
    else:
        raise HTTPException(status_code=500, detail="Telegram bot service not initialized")


# ── Daemon Startup Helper ─────────────────────────────────────────────

_daemon_started = False
_daemon_lock = threading.Lock()


def start_fastapi_background_daemon(host: str = "0.0.0.0", port: int = 8000):
    """Starts FastAPI uvicorn server in a non-blocking daemon thread if port is free."""
    global _daemon_started
    with _daemon_lock:
        if _daemon_started:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
            sock.close()
        except OSError:
            _daemon_started = True
            return

        def _run_uvicorn():
            uvicorn.run(api_app, host=host, port=port, log_level="warning")

        t = threading.Thread(target=_run_uvicorn, daemon=True, name="IndustrialRCA-FastAPI")
        t.start()
        _daemon_started = True


if __name__ == "__main__":
    uvicorn.run("industrial_rca.api:api_app", host="0.0.0.0", port=8000, reload=True)
