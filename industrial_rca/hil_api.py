"""
Hardware-in-the-Loop (HIL) REST Telemetry & Incident Ingestion API.
Provides FastAPI endpoints for edge ingestion and runs on port 8000.
"""

import time
import socket
import threading
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from industrial_rca.data.oem_manuals import get_vfd_fault_info, get_vfd_spec
from industrial_rca.data.telemetry_generator import (
    TelemetryDataset,
    TelemetryStore,
    generate_high_frequency_vibration,
)
from industrial_rca.graph.workflow import create_rca_graph

api_app = FastAPI(
    title="Industrial RCA Telemetry & Incident Ingestion API",
    description="Edge ingestion endpoint for V-Box IoT Gateway, Node-RED, and PLC/VFD telemetry.",
    version="2.0.0",
)

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IncidentPayload(BaseModel):
    asset_id: str = Field(default="VFD_VM_01", description="Identifier of the tripped asset")
    fault_code: int = Field(default=6, description="WECON VM trip code (e.g. 6 for Err06, 11 for Err11)")
    fault_description: Optional[str] = Field(default="", description="Human-readable trip description")
    incident_id: Optional[str] = Field(default=None, description="Unique incident ID")
    pre_fault_telemetry: List[Dict[str, Any]] = Field(default_factory=list, description="Array of time-series points")
    model_config = ConfigDict(extra="allow")

# Global in-memory storage for latest HIL incident
LATEST_HIL_INCIDENT: Dict[str, Any] = {
    "has_incident": False,
    "incident_data": None,
    "received_at": None,
    "pipeline_status": "READY",
    "graph_result": None,
}

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
    # Ensure standardized columns
    for col, default in [("f_out", 0.0), ("f_target", 0.0), ("current", 0.0), ("v_out", 0.0), ("v_dc", 0.0), ("fault_code", 0)]:
        if col not in df.columns:
            df[col] = default

    # Map to pump / telemetry channels for seamless compatibility with analytics tool
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
            "trip_value": float(df["v_dc"].max()) if incident.fault_code == 6 else float(df["current"].max()),
            "trip_setpoint": 700.0 if incident.fault_code == 6 else 1.15,
        },
        normal_waveform={"t": t_norm, "signal": sig_norm},
        fault_waveform={"t": t_fault, "signal": sig_fault},
    )
    ds_id = TelemetryStore.register(dataset, f"ds_hil_{incident.fault_code}_{int(time.time())}")

    LATEST_HIL_INCIDENT["has_incident"] = True
    LATEST_HIL_INCIDENT["incident_data"] = {
        "incident_id": inc_id,
        "asset_id": incident.asset_id,
        "fault_code": incident.fault_code,
        "fault_description": fault_desc,
        "dataset_id": ds_id,
        "point_count": len(df),
        "received_at": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    LATEST_HIL_INCIDENT["received_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC")
    LATEST_HIL_INCIDENT["pipeline_status"] = "TRIGGERED"

    def _run_graph():
        try:
            hil_graph = create_rca_graph()
            config = {"configurable": {"thread_id": f"rca-hil-{inc_id}"}}
            init_state = {
                "dataset_id": ds_id,
                "asset_id": incident.asset_id,
                "has_active_trip": True,
                "use_deepseek": False,
            }
            for event in hil_graph.stream(init_state, config=config):
                pass
            snapshot = hil_graph.get_state(config)
            LATEST_HIL_INCIDENT["graph_result"] = snapshot.values if snapshot else None
            LATEST_HIL_INCIDENT["pipeline_status"] = "ANALYSIS_COMPLETE"
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

@api_app.get("/api/v1/telemetry/health")
def api_health():
    return {
        "status": "ONLINE",
        "service": "Industrial RCA Ingestion Middleware",
        "timestamp": time.time(),
        "latest_incident": LATEST_HIL_INCIDENT.get("incident_data"),
        "pipeline_status": LATEST_HIL_INCIDENT.get("pipeline_status"),
    }


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
