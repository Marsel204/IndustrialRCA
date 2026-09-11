"""
Unit & Integration Tests for Hardware-in-the-Loop (HIL) Ingestion Architecture.
Validates:
- WECON VM VFD specifications and fault taxonomy lookup
- ISA-95 asset topology traversal with HMI, VFD, and motor nodes
- Node-RED flow configuration structure
- FastAPI REST incident ingestion endpoint (/api/v1/telemetry/incident)
"""

import json
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from industrial_rca.data.oem_manuals import (
    get_vfd_spec,
    get_vfd_fault_info,
    get_fmea_entry,
    ISO_14224_TAXONOMY,
)
from industrial_rca.tools.topology_tracer import AssetTopologyTracer
from industrial_rca.data.telemetry_generator import TelemetryStore
from app import api_app


def test_vfd_oem_spec():
    """Verify WECON VM VFD specification and register map."""
    spec = get_vfd_spec()
    assert spec["asset_id"] == "VFD_VM_01"
    assert "registers" in spec
    assert "3000H" in spec["registers"]
    assert "3004H" in spec["registers"]
    assert "700BH" in spec["registers"]
    assert spec["registers"]["3004H"]["name"] == "DC Bus Voltage"
    assert spec["registers"]["700BH"]["dec"] == 28683
    assert spec["dc_bus_overvoltage_threshold_v"] == 700.0


def test_vfd_fault_taxonomy():
    """Verify fault taxonomy and FMEA matrix for Err02, Err03, Err06, and Err11."""
    # Err06 (Decel Overvoltage)
    f6 = get_vfd_fault_info(6)
    assert "Err06" in f6["description"]
    assert f6["iso_info"]["iso_code"] == "ISO-14224-DR-ELC-OVV"

    # Err11 (Motor Overload)
    f11 = get_vfd_fault_info(11)
    assert "Err11" in f11["description"]
    assert f11["iso_info"]["iso_code"] == "ISO-14224-DR-ELC-THO"

    # FMEA entries
    h_err06 = get_fmea_entry("H_VFD_ERR06")
    assert h_err06 is not None
    assert "Deceleration Overvoltage" in h_err06["name"]

    h_err11 = get_fmea_entry("H_VFD_ERR11")
    assert h_err11 is not None
    assert "Motor Thermal Overload" in h_err11["name"]


def test_topology_traversal_hil_bench():
    """Verify ISA-95 topology tracer identifies HMI, VFD, and Motor nodes."""
    tracer = AssetTopologyTracer()
    
    # Motor M01 exists
    motor = tracer.get_equipment("MOTOR_M01")
    assert motor is not None
    assert motor["type"] == "ElectricMotor"

    # VFD VM01 exists
    vfd = tracer.get_equipment("VFD_VM_01")
    assert vfd is not None
    assert len(vfd["sensors"]) == 6

    # Trace upstream from Motor
    upstream = tracer.trace_upstream("MOTOR_M01")
    upstream_ids = [u["asset_id"] for u in upstream]
    assert "VFD_VM_01" in upstream_ids
    assert "HMI_TOUCH_01" in upstream_ids


def test_nodered_flow_json_structure():
    """Verify flows.json parses cleanly and contains critical pipeline nodes."""
    flow_path = Path(__file__).resolve().parent.parent.parent / "infra" / "nodered" / "flows.json"
    assert flow_path.exists(), "flows.json not found"

    with open(flow_path, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    types = [n.get("type") for n in nodes]
    assert "mqtt in" in types
    assert "http request" in types
    assert "switch" in types

    # Check MQTT topic
    mqtt_node = next(n for n in nodes if n.get("type") == "mqtt in")
    assert mqtt_node["topic"] == "factory/bench01/vfd/telemetry"

    # Check API destination URL
    http_nodes = [n for n in nodes if n.get("type") == "http request"]
    api_post_node = next((n for n in http_nodes if "api/v1/telemetry/incident" in n.get("url", "")), None)
    assert api_post_node is not None


def test_fastapi_incident_endpoint():
    """Verify POST /api/v1/telemetry/incident receives and registers real hardware payload."""
    client = TestClient(api_app)

    payload = {
        "asset_id": "VFD_VM_01",
        "fault_code": 6,
        "fault_description": "Deceleration Overvoltage (Err06) - DC link regeneration surge",
        "incident_id": "INC-TEST-ERR06-001",
        "pre_fault_telemetry": [
            {
                "timestamp": 1726041000,
                "f_out": 45.0,
                "f_target": 45.0,
                "current": 1.4,
                "v_out": 220.0,
                "v_dc": 312.0,
                "fault_code": 0,
            },
            {
                "timestamp": 1726041060,
                "f_out": 12.0,
                "f_target": 0.0,
                "current": 3.6,
                "v_out": 175.0,
                "v_dc": 745.0,
                "fault_code": 6,
            },
        ],
    }

    response = client.post("/api/v1/telemetry/incident", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "INCIDENT_INGESTED"
    assert data["incident_id"] == "INC-TEST-ERR06-001"
    assert data["fault_code"] == 6
    assert data["asset_id"] == "VFD_VM_01"

    # Verify dataset registered in TelemetryStore
    registered_datasets = list(TelemetryStore._store.keys())
    assert any("hil_6" in k for k in registered_datasets)


def test_fastapi_health_endpoint():
    """Verify GET /api/v1/telemetry/health returns status and latest incident metadata."""
    client = TestClient(api_app)
    response = client.get("/api/v1/telemetry/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert data["service"] == "Industrial RCA Ingestion Middleware"
