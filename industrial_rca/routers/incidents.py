"""
Hardware-in-the-Loop (HIL) incident ingestion and reset router.
"""

import time
from typing import Optional
import numpy as np
import pandas as pd
from fastapi import APIRouter, BackgroundTasks

from industrial_rca.data.oem_manuals import get_vfd_fault_info
from industrial_rca.data.telemetry_generator import (
    TelemetryDataset,
    TelemetryStore,
    generate_high_frequency_vibration,
)
from industrial_rca.data.embedded_tsdb import GLOBAL_TSDB
from industrial_rca.utils.logging import get_logger, set_trace_context
from industrial_rca.routers.common import (
    IncidentPayload,
    LATEST_HIL_INCIDENT,
    SCENARIOS_REGISTRY,
    GLOBAL_RCA_GRAPH,
    notify_hil_subscribers,
    broadcast_live_metric,
)

logger = get_logger("industrial_rca.routers.incidents")
router = APIRouter(tags=["HIL Incidents"])


@router.post("/api/v1/telemetry/incident")
def ingest_incident(incident: IncidentPayload, background_tasks: BackgroundTasks):
    """
    Receives an incident payload from Node-RED or physical edge gateway,
    formats it into a TelemetryDataset, registers it with TelemetryStore,
    and launches the LangGraph RCA workflow.
    """
    inc_id = incident.incident_id or f"INC-HIL-{int(time.time())}"
    set_trace_context(incident_id=inc_id)
    logger.info(f"Ingesting HIL incident {inc_id} for asset {incident.asset_id} (fault_code={incident.fault_code})")

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

    notify_hil_subscribers({
        "event": "hil_incident_detected",
        "data": LATEST_HIL_INCIDENT["incident_data"],
        "thread_id": thread_id,
        "dataset_id": ds_id,
        "timestamp": time.time(),
    })
    broadcast_live_metric({
        "event": "incident",
        "incident_id": inc_id,
        "asset_id": incident.asset_id,
        "fault_code": incident.fault_code,
        "fault_description": fault_desc,
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
            notify_hil_subscribers({
                "event": "hil_rca_complete",
                "thread_id": thread_id,
                "dataset_id": ds_id,
                "status": "ANALYSIS_COMPLETE",
            })
        except Exception as e:
            logger.error(f"Async graph execution error for incident {inc_id}: {e}")
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


@router.get("/api/v1/telemetry/latest_incident")
def get_latest_incident():
    return LATEST_HIL_INCIDENT


@router.post("/api/v1/telemetry/incident/clear")
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

    notify_hil_subscribers({
        "event": "hil_incident_cleared",
        "status": "READY",
        "timestamp": time.time(),
    })

    return {
        "status": "INCIDENT_CLEARED",
        "message": "Active hardware incident cleared. System restored to real-time nominal monitoring.",
    }


@router.post("/api/v1/rca/reset")
def reset_rca(thread_id: Optional[str] = None):
    """Alias to reset active incident and pipeline state back to normal."""
    return clear_incident()
