"""
Shared state, dependencies, and models for Industrial RCA FastAPI routers.
"""

import time
import asyncio
import threading
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from langgraph.checkpoint.memory import MemorySaver

from industrial_rca.config import EQUIPMENT_ID
from industrial_rca.tools.telemetry_analytics import (
    TelemetryAnalyticsTool,
    GLOBAL_TELEMETRY_CACHE,
)
from industrial_rca.tools.topology_tracer import AssetTopologyTracer
from industrial_rca.tools.cmms_connector import CMMSConnector
from industrial_rca.tools.deepseek_client import DeepSeekClient
from industrial_rca.tools.influx_tool import InfluxDBTelemetryTool
from industrial_rca.data.embedded_tsdb import GLOBAL_TSDB
from industrial_rca.graph.workflow import create_rca_graph
from industrial_rca.data.telemetry_generator import (
    TelemetryStore,
    generate_vfd_dataset,
)
from industrial_rca.utils.logging import get_logger

logger = get_logger("industrial_rca.routers")

# Shared tool instances
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


def ensure_default_scenarios():
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


ensure_default_scenarios()

# Global HIL Incident State
LATEST_HIL_INCIDENT: Dict[str, Any] = {
    "has_incident": False,
    "incident_data": None,
    "received_at": None,
    "pipeline_status": "READY",
    "graph_result": None,
    "version": 0,
}
HIL_EVENT_SUBSCRIBERS: List[asyncio.Queue] = []
SUBSCRIBER_LOCK = threading.Lock()

LIVE_STREAM_SUBSCRIBERS: List[asyncio.Queue] = []
LIVE_STREAM_LOCK = threading.Lock()


def notify_hil_subscribers(event_data: Dict[str, Any]):
    with SUBSCRIBER_LOCK:
        for q in HIL_EVENT_SUBSCRIBERS:
            try:
                q.put_nowait(event_data)
            except Exception:
                pass


def broadcast_live_metric(metric_data: Dict[str, Any]):
    with LIVE_STREAM_LOCK:
        for q in LIVE_STREAM_SUBSCRIBERS:
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
    dataset_id: str = Field(default="exp_err06", description="Dataset identifier or preset")
    asset_id: str = Field(default=EQUIPMENT_ID, description="Target asset ID")
    thread_id: Optional[str] = Field(default=None, description="Session thread ID")
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
    thread_id: Optional[str] = Field(default=None, description="Associated RCA thread ID")
    model: Optional[str] = Field(default="deepseek-chat", description="Model to use")
