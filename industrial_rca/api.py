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
import time
import json
import socket
import asyncio
import threading
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
from industrial_rca.utils.middleware import CorrelationIdMiddleware
from industrial_rca.utils.logging import get_logger

logger = get_logger("industrial_rca.api")

api_app = FastAPI(
    title="Industrial RCA Unified REST & SSE API",
    description="High-performance backend serving telemetry, ISA-95 topology, LangGraph RCA, and DeepSeek streaming.",
    version="2.1.0",
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

# Global instances
analytics_tool = TelemetryAnalyticsTool(GLOBAL_TELEMETRY_CACHE)
topology_tracer = AssetTopologyTracer()
cmms_tool = CMMSConnector()
deepseek_client = DeepSeekClient()
influx_tool = InfluxDBTelemetryTool()

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


def _notify_hil_subscribers(event_data: Dict[str, Any]):
    with _SUBSCRIBER_LOCK:
        for q in _HIL_EVENT_SUBSCRIBERS:
            try:
                q.put_nowait(event_data)
            except Exception:
                pass


def _broadcast_live_metric(metric_data: Dict[str, Any]):
    with _LIVE_STREAM_LOCK:
        for q in _LIVE_STREAM_SUBSCRIBERS:
            try:
                q.put_nowait(metric_data)
            except Exception:
                pass


# ── Request / Response Models ─────────────────────────────────────────

class IncidentPayload(BaseModel):
    asset_id: str = Field(default="VFD_VM_01", description="Identifier of the tripped asset")
    fault_code: int = Field(default=6, description="WECON VM trip code (e.g. 6 for Err06, 11 for Err11)")
    fault_description: Optional[str] = Field(default="", description="Human-readable trip description")
    incident_id: Optional[str] = Field(default=None, description="Unique incident ID")
    pre_fault_telemetry: List[Dict[str, Any]] = Field(default_factory=list, description="Array of time-series points")
    model_config = ConfigDict(extra="allow")


class RCARunRequest(BaseModel):
    dataset_id: str = Field(default="exp_err06", description="Dataset identifier or preset (live_stream, exp_err02, exp_err06, exp_nominal)")
    asset_id: str = Field(default=EQUIPMENT_ID, description="Target asset ID")
    thread_id: Optional[str] = Field(default=None, description="Session thread ID for LangGraph checkpointer")
    use_deepseek: bool = Field(default=True, description="Enable DeepSeek AI evaluation")
    deepseek_model: str = Field(default="deepseek-chat", description="Model: deepseek-chat or deepseek-reasoner")


class HumanReviewRequest(BaseModel):
    thread_id: str = Field(description="Thread ID of paused RCA workflow")
    action: str = Field(default="approve", description="'approve', 'reject', or 'override'")
    reviewer: str = Field(default="Lead Reliability Engineer", description="Signing engineer name")
    notes: str = Field(default="", description="Engineering justification notes")
    override_root_cause: Optional[str] = Field(default=None, description="Optional overridden root cause description")


class CopilotChatRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(description="Chat history messages")
    thread_id: Optional[str] = Field(default=None, description="Associated RCA thread ID for contextual grounding")
    model: Optional[str] = Field(default="deepseek-chat", description="Model to use")


# ── Health & Diagnostics ──────────────────────────────────────────────

@api_app.get("/api/v1/health")
def get_health():
    _ensure_default_scenarios()
    cache_stats = GLOBAL_TELEMETRY_CACHE.get_stats()
    mqtt_online = influx_tool.is_mqtt_active()
    latest_tsdb = GLOBAL_TSDB.get_latest("VFD_VM_01")
    is_real = bool(latest_tsdb and (time.time() - latest_tsdb.get("timestamp", 0) < 60))
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
        "is_simulated": not is_real,
        "telemetry_source": "hardware" if is_real else "fallback_simulation",
    }


@api_app.get("/api/v1/telemetry/health")
def get_telemetry_health():
    """Backward compatibility endpoint for test suite and HIL simulator."""
    return {
        "status": "ONLINE",
        "service": "Industrial RCA Ingestion Middleware",
        "timestamp": time.time(),
        "latest_incident": LATEST_HIL_INCIDENT.get("incident_data"),
        "pipeline_status": LATEST_HIL_INCIDENT.get("pipeline_status"),
    }


# ── Live Edge HIL Ingestion & Reactive Push (Registered BEFORE parametrized /telemetry/{id}) ───

@api_app.post("/api/v1/telemetry/incident")
def ingest_incident(incident: IncidentPayload, background_tasks: BackgroundTasks):
    """
    Receives an incident payload from Node-RED or physical edge gateway,
    formats it into a TelemetryDataset, registers it with TelemetryStore,
    and launches the LangGraph RCA workflow.
    """
    inc_id = incident.incident_id or f"INC-HIL-{int(time.time())}"
    fault_desc = incident.fault_description
    if not fault_desc:
        fault_info = get_vfd_fault_info(incident.fault_code)
        fault_desc = fault_info.get("description", f"WECON VM VFD Trip Code {incident.fault_code}")

    raw_points = incident.pre_fault_telemetry
    if not raw_points:
        now = time.time()
        raw_points = [
            {"timestamp": now - t, "f_out": 45.0, "f_target": 45.0, "current": 1.4, "v_out": 220.0, "v_dc": 312.0, "fault_code": 0}
            for t in range(60, 0, -1)
        ]
        raw_points.append({"timestamp": now, "f_out": 0.0, "f_target": 0.0, "current": 2.8, "v_out": 0.0, "v_dc": 745.0, "fault_code": incident.fault_code})

    df = pd.DataFrame(raw_points)
    for col, default in [("f_out", 0.0), ("f_target", 0.0), ("current", 0.0), ("v_out", 0.0), ("v_dc", 0.0), ("fault_code", 0)]:
        if col not in df.columns:
            df[col] = default

    if "PT-30101" not in df.columns:
        df["PT-30101"] = np.where(df["fault_code"] > 0, 0.58, 2.40)
    if "DPS-30101" not in df.columns:
        df["DPS-30101"] = np.where(df["fault_code"] > 0, 1.85, 0.12)
    if "VI-301-R" not in df.columns:
        df["VI-301-R"] = np.where(df["fault_code"] > 0, 11.4, 1.80)
    if "TI-301-DE" not in df.columns:
        df["TI-301-DE"] = np.where(df["fault_code"] > 0, 92.3, 48.5)
    if "IT-30101" not in df.columns:
        df["IT-30101"] = df["current"] * 60.0

    t_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False)
    t_fault, sig_fault = generate_high_frequency_vibration(is_cavitating=True)

    dataset = TelemetryDataset(
        scenario_name=f"HIL Incident: {fault_desc}",
        df_1hz=df,
        metadata={
            "asset_id": incident.asset_id,
            "condition": "HARDWARE_FAULT_TRIP",
            "anomaly_expected": True,
            "fault_code": incident.fault_code,
            "fault_description": fault_desc,
            "trip_timestamp_sec": len(df) - 1,
            "trip_time_str": time.strftime("%H:%M:%S UTC"),
            "primary_trip_sensor": "VFD_V_DC" if incident.fault_code == 6 else "VFD_I_OUT",
            "trip_value": float(df["v_dc"].max()) if (incident.fault_code == 6 and "v_dc" in df.columns and len(df) > 0) else (float(df["current"].max()) if ("current" in df.columns and len(df) > 0) else 0.0),
            "trip_setpoint": 700.0 if incident.fault_code == 6 else 1.15,
        },
        normal_waveform={"t": t_norm, "signal": sig_norm},
        fault_waveform={"t": t_fault, "signal": sig_fault},
    )
    ds_id = TelemetryStore.register(dataset, f"ds_hil_{incident.fault_code}_{int(time.time())}")
    SCENARIOS_REGISTRY["hil"] = ds_id

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
                "use_deepseek": True,
                "deepseek_model": "deepseek-reasoner",
            }
            for _ in GLOBAL_RCA_GRAPH.stream(init_state, config=config):
                pass
            snapshot = GLOBAL_RCA_GRAPH.get_state(config)
            LATEST_HIL_INCIDENT["graph_result"] = snapshot.values if snapshot else None
            LATEST_HIL_INCIDENT["pipeline_status"] = "ANALYSIS_COMPLETE"
            _notify_hil_subscribers({
                "event": "hil_pipeline_completed",
                "incident_id": inc_id,
                "thread_id": thread_id,
                "dataset_id": ds_id,
                "status": "ANALYSIS_COMPLETE",
            })
        except Exception as e:
            LATEST_HIL_INCIDENT["pipeline_status"] = f"ERROR: {e}"

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
def clear_incident():
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

    GLOBAL_TSDB._last_fault_code = 0
    GLOBAL_TSDB._last_trip_time = 0.0

    _notify_hil_subscribers({
        "event": "hil_incident_cleared",
        "status": "READY",
        "timestamp": time.time(),
    })

    return {
        "status": "INCIDENT_CLEARED",
        "message": "Active hardware incident cleared. System restored to real-time nominal monitoring.",
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

@api_app.get("/api/v1/telemetry/live/metrics")
def get_live_telemetry_metrics():
    """Returns the latest single live telemetry metric for the Wecon VFD."""
    return influx_tool.get_latest_metrics(asset_id="VFD_VM_01")


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
            yield f"data: {json.dumps(init_metric)}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    continue
                except asyncio.TimeoutError:
                    pass

                metric = await asyncio.to_thread(influx_tool.get_latest_metrics, "VFD_VM_01")
                yield f"data: {json.dumps(metric)}\n\n"
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

    raw_f_out = _unpack(metric.get("f_out", metric.get("frequency", 40.0)))
    # If scaled as 4000 for 40.00 Hz (standard Modbus register scaling)
    f_out = round(raw_f_out / 100.0 if raw_f_out > 200.0 else raw_f_out, 2)

    raw_rpm = _unpack(metric.get("rpm", f_out * 29.0))
    rpm = round(raw_rpm, 1)

    raw_v_dc = _unpack(metric.get("v_dc", metric.get("bus_voltage", 182.0)))
    v_dc = round(raw_v_dc, 1)

    raw_current = _unpack(metric.get("current", 0.0))
    current = round(raw_current / 100.0 if raw_current > 100.0 else raw_current, 2)

    # Check for trip code across common industrial keys (fault_code, error, err, trip, code, d_trigger, D-registers)
    raw_fault = None
    for key in ("fault_code", "fault", "error", "err", "code", "trip", "trip_code", "d_trigger"):
        if metric.get(key) is not None:
            raw_fault = metric.get(key)
            break

    if raw_fault is None:
        for k, v in metric.items():
            if k.upper().startswith("D") or "PLC" in k.upper():
                try:
                    val = int(_unpack(v, 0))
                    if val in (2, 3, 6, 11) or val > 0:
                        raw_fault = val
                        break
                except (ValueError, TypeError):
                    pass
    if raw_fault is None:
        topic_name = str(metric.get("_mqtt_topic", "")).lower()
        if "err02" in topic_name or "error02" in topic_name:
            raw_fault = 2
        elif "err06" in topic_name or "error06" in topic_name:
            raw_fault = 6

    fault_code = int(_unpack(raw_fault, 0) if raw_fault is not None else 0)
    status = "TRIPPED" if fault_code > 0 else "RUNNING"
    asset_id = str(metric.get("asset_id", "VFD_VM_01"))

    normalized = {
        "asset_id": asset_id,
        "f_out": f_out,
        "v_dc": v_dc,
        "current": current,
        "rpm": rpm,
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

    # 3. Update active tools & broadcast live metric to connected SSE frontend clients
    influx_tool.update_latest(normalized)
    _broadcast_live_metric(normalized)

    return {"status": "INGESTED", "metric": normalized, "tsdb_buffered": True}


# ── Embedded TSDB History & Diagnostics ───────────────────────────────

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

    if dataset_id in ("exp_nominal", "ds_exp_nominal", "normal", "ds_normal"):
        ds = generate_vfd_dataset(scenario="exp_nominal")
        TelemetryStore.register(ds, "ds_exp_nominal")
        SCENARIOS_REGISTRY["exp_nominal"] = "ds_exp_nominal"
        return ds

    actual_id = SCENARIOS_REGISTRY.get(dataset_id, dataset_id)
    try:
        return TelemetryStore.get(actual_id)
    except KeyError:
        ds = generate_vfd_dataset(scenario="live_stream")
        TelemetryStore.register(ds, actual_id)
        return ds


@api_app.get("/api/v1/telemetry/{dataset_id}")
def get_telemetry_series(dataset_id: str):
    ds = _resolve_ds(dataset_id)
    df = ds.df_1hz

    timestamps = ds.get_timestamps().tolist()
    series_data: Dict[str, List[float]] = {}
    skip_cols = {"timestamp_sec", "timestamp", "asset_id", "status", "_time", "_measurement", "_field", "result", "table"}
    for col in df.columns:
        if col in skip_cols:
            continue
        try:
            series_data[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).round(3).tolist()
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
        eq = topology_tracer.get_equipment(EQUIPMENT_ID)
        asset_id = EQUIPMENT_ID

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
        is_root = item["id"] == "STR-301A"
        is_target = item["id"] == asset_id

        nodes.append({
            "id": item["id"],
            "name": item.get("name", item["id"]),
            "type": item.get("type", "Equipment"),
            "isa95_level": item.get("isa95_level", 2),
            "sensors": item.get("sensors", []),
            "operating_specs": item.get("operating_specs", {}),
            "status": "ROOT_CAUSE" if is_root else ("TRIPPED" if is_target else "HEALTHY"),
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
    }


@api_app.post("/api/v1/rca/run")
def run_rca_pipeline(request: RCARunRequest):
    _ensure_default_scenarios()
    thread_id = request.thread_id or f"rca-thread-{int(time.time())}"
    config = {"configurable": {"thread_id": thread_id}}

    actual_ds_id = SCENARIOS_REGISTRY.get(request.dataset_id, request.dataset_id)
    _ = _resolve_ds(actual_ds_id)

    init_state = {
        "dataset_id": actual_ds_id,
        "asset_id": request.asset_id,
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
        "winning_hypothesis": vals.get("winning_hypothesis"),
        "human_review_payload": review_payload,
        "root_cause_asset": vals.get("root_cause_asset"),
        "incident_report_8d": vals.get("incident_report_8d"),
        "sap_work_order": vals.get("sap_work_order"),
    }


@api_app.post("/api/v1/rca/human-review")
def submit_human_review(request: HumanReviewRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    state_snapshot = GLOBAL_RCA_GRAPH.get_state(config)

    if not state_snapshot:
        raise HTTPException(status_code=404, detail=f"Thread '{request.thread_id}' not found.")

    decision_payload = {
        "action": request.action.lower(),
        "reviewer": request.reviewer,
        "notes": request.notes,
        "override_root_cause": request.override_root_cause,
    }

    for _ in GLOBAL_RCA_GRAPH.stream(Command(resume=decision_payload), config=config):
        pass

    final_snapshot = GLOBAL_RCA_GRAPH.get_state(config)
    vals = final_snapshot.values if final_snapshot else {}

    return {
        "status": "RESUMED",
        "thread_id": request.thread_id,
        "pipeline_status": vals.get("pipeline_status", "COMPLETED"),
        "current_step": 7,
        "decision": decision_payload,
        "incident_report_8d": vals.get("incident_report_8d"),
        "sap_work_order": vals.get("sap_work_order"),
        "root_cause_description": vals.get("root_cause_description"),
    }


# ── DeepSeek AI Copilot Streaming ─────────────────────────────────────

@api_app.post("/api/v1/copilot/chat/stream")
def stream_copilot_chat(request: CopilotChatRequest):
    """
    Server-Sent Events (SSE) streaming endpoint for DeepSeek AI Copilot.
    Streams token deltas for both content and reasoning_content chunk by chunk.
    """
    model = request.model or "deepseek-chat"
    messages = request.messages

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
