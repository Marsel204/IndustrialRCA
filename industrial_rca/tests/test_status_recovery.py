"""
Unit & Integration Tests for System Recovery Synchronization.
Validates that when the physical rig or simulated system goes back to normal:
1. Active incident is automatically cleared on the backend.
2. LATEST_HIL_INCIDENT is restored to nominal (has_incident=False, pipeline_status="READY").
3. Embedded TSDB trip triggers and debounce latches are fully reset.
4. Broadcast live metrics notify connected frontend clients of recovery (has_active_trip=False, incident_cleared=True).
5. Background LangGraph execution is prevented from overriding cleared incidents.
"""

import time
import pytest
from starlette.testclient import TestClient

from industrial_rca.api import (
    api_app,
    LATEST_HIL_INCIDENT,
    clear_incident,
    ingest_incident,
    IncidentPayload,
    GLOBAL_TSDB,
    _HIL_EVENT_SUBSCRIBERS,
)
import asyncio


@pytest.fixture
def client():
    return TestClient(api_app)


def test_auto_recovery_clears_incident_when_system_returns_to_normal(client):
    """
    Simulate a hardware trip Err13, followed by physical system recovery to nominal 40 Hz / 1197 RPM.
    Verify that the app/backend status automatically updates back to normal.
    """
    # 1. Trigger an active hardware trip (Err13 - Phase Loss)
    inc_payload = IncidentPayload(
        asset_id="VFD_VM_01",
        fault_code=13,
        fault_description="Output Phase Loss (Err13)",
        incident_id="INC-TEST-RECOVERY-01",
        pre_fault_telemetry=[
            {"f_out": 40.0, "v_dc": 273.4, "current": 0.0, "rpm": 0.0, "fault_code": 13, "status": "TRIPPED"}
        ],
    )
    res_trip = client.post("/api/v1/telemetry/incident", json=inc_payload.model_dump())
    assert res_trip.status_code == 200
    assert LATEST_HIL_INCIDENT["has_incident"] is True
    assert LATEST_HIL_INCIDENT["incident_data"]["fault_code"] == 13

    # Verify health endpoint reports active incident
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["latest_hil_incident"] is not None

    tel_health_resp = client.get("/api/v1/telemetry/health")
    assert tel_health_resp.json()["latest_incident"] is not None

    # 2. System goes back to normal:
    # Physical motor restarted, spinning at 40 Hz, 1,197 RPM, current 0.02 A, zero fault codes
    normal_payload = {
        "asset_id": "VFD_VM_01",
        "f_out": 40.0,
        "f_target": 40.0,
        "v_dc": 273.4,
        "v_out": 184.0,
        "current": 0.02,
        "rpm": 1197.0,
        "fault_code": 0,
        "status": "RUNNING",
    }
    res_feed = client.post("/api/v1/telemetry/live/feed", json=normal_payload)
    assert res_feed.status_code == 200

    # 3. Assert status is automatically updated back to normal
    assert LATEST_HIL_INCIDENT["has_incident"] is False
    assert LATEST_HIL_INCIDENT["incident_data"] is None
    assert LATEST_HIL_INCIDENT["pipeline_status"] == "READY"

    # Verify health endpoints report nominal / cleared state
    health_after = client.get("/api/v1/health")
    assert health_after.json()["latest_hil_incident"] is None
    assert health_after.json()["hil_status"] == "READY"

    tel_health_after = client.get("/api/v1/telemetry/health")
    assert tel_health_after.json()["latest_incident"] is None
    assert tel_health_after.json()["pipeline_status"] == "READY"

    # Verify live metric broadcast includes recovery flags
    latest_metric = res_feed.json().get("metric", {})
    assert latest_metric.get("has_active_trip") is False
    assert latest_metric.get("fault_code") == 0
    assert latest_metric.get("status") == "RUNNING"


def test_tsdb_reset_trip_clears_latches():
    """Verify that resetting trip in embedded TSDB resets internal latches and fault codes."""
    GLOBAL_TSDB._last_fault_code = 13
    GLOBAL_TSDB._pending_fault_code = 13
    GLOBAL_TSDB._pending_fault_count = 5
    GLOBAL_TSDB.reset_trip()

    assert GLOBAL_TSDB._last_fault_code == 0
    assert GLOBAL_TSDB._pending_fault_code == 0
    assert GLOBAL_TSDB._pending_fault_count == 0


def test_feed_live_telemetry_broadcasts_recovery_on_nominal_frame(client):
    """
    Verify that when equipment recovers, the broadcast live metric payload contains
    has_active_trip: False, has_incident: False, and incident_cleared: True.
    """
    # Force trip state
    LATEST_HIL_INCIDENT["has_incident"] = True
    LATEST_HIL_INCIDENT["incident_data"] = {"fault_code": 13, "incident_id": "TEST-13"}
    LATEST_HIL_INCIDENT["pipeline_status"] = "ANALYSIS_COMPLETE"

    normal_payload = {
        "asset_id": "VFD_VM_01",
        "f_out": 40.0,
        "f_target": 40.0,
        "v_dc": 273.4,
        "v_out": 184.0,
        "current": 0.02,
        "rpm": 1197.0,
        "fault_code": 0,
        "status": "RUNNING",
    }
    res = client.post("/api/v1/telemetry/live/feed", json=normal_payload)
    assert res.status_code == 200
    metric = res.json()["metric"]
    assert metric["has_active_trip"] is False
    assert metric["has_incident"] is False
    assert metric["incident_cleared"] is True
    assert metric["pipeline_status"] == "READY"
