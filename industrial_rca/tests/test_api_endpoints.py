"""
Integration Tests for Unified FastAPI Backend Endpoints.
Tests:
- Health and status
- Scenario catalog
- Telemetry timeseries extraction
- 20 kHz vibration FFT spectrum
- ISA-95 Asset Topology graph traversal
- LangGraph RCA pipeline execution, state retrieval, and HITL authorization
- Copilot chat SSE token streaming
"""

import json
import pytest
from starlette.testclient import TestClient

from industrial_rca.api import api_app


@pytest.fixture(scope="module")
def client():
    return TestClient(api_app)


def test_api_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ONLINE"
    assert "telemetry_cache" in data
    assert "active_scenarios" in data


def test_api_scenarios(client):
    resp = client.get("/api/v1/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json().get("scenarios", [])
    scenario_ids = [s["id"] for s in scenarios]
    assert "exp_err06" in scenario_ids
    assert "exp_err02" in scenario_ids
    assert "exp_nominal" in scenario_ids
    assert "live_stream" in scenario_ids


def test_api_telemetry_series(client):
    resp = client.get("/api/v1/telemetry/exp_err06")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["timestamps"]) >= 300
    series = data["series"]
    assert "f_out" in series
    assert "v_dc" in series
    assert "current" in series
    assert "rpm" in series
    assert len(series["v_dc"]) >= 300


def test_api_telemetry_spectrum(client):
    resp = client.get("/api/v1/telemetry/exp_err06/spectrum")
    assert resp.status_code == 200
    data = resp.json()
    analysis = data["analysis"]
    assert "overall_rms" in analysis
    assert len(data["frequencies"]) > 50
    assert len(data["magnitudes"]) == len(data["frequencies"])


def test_api_topology(client):
    resp = client.get("/api/v1/topology/VFD_VM_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_asset"]["id"] == "VFD_VM_01"
    assert "upstream_chain" in data
    assert "downstream_chain" in data
    graph = data["graph"]
    node_ids = [n["id"] for n in graph["nodes"]]
    assert "VFD_VM_01" in node_ids
    assert "PLC_LX_01" in node_ids
    assert "IND_MOTOR_01" in node_ids
    assert len(graph["edges"]) > 0


def test_api_rca_workflow_lifecycle(client):
    thread_id = "test-api-lifecycle-thread"

    # 1. Check initial state before run
    resp_init = client.get(f"/api/v1/rca/state/{thread_id}")
    assert resp_init.status_code == 200
    assert resp_init.json()["pipeline_status"] == "NOT_STARTED"

    # 2. Run RCA on exp_err06 scenario
    resp_run = client.post("/api/v1/rca/run", json={
        "dataset_id": "exp_err06",
        "asset_id": "VFD_VM_01",
        "thread_id": thread_id,
        "use_deepseek": False,
    })
    assert resp_run.status_code == 200
    data_run = resp_run.json()
    assert data_run["status"] == "SUCCESS"
    assert data_run["is_paused_at_hitl"] is True
    assert data_run["current_step"] == 6
    assert data_run["winning_hypothesis"]["hypothesis_id"] == "H_VFD_ERR06"

    # 3. Fetch state after pause
    resp_state = client.get(f"/api/v1/rca/state/{thread_id}")
    assert resp_state.status_code == 200
    state_data = resp_state.json()
    assert state_data["is_paused_at_hitl"] is True
    assert len(state_data["hypothesis_results"]) >= 4
    assert len(state_data["causal_chain_5_whys"]) == 5

    # 4. Submit Human Review Approval
    resp_review = client.post("/api/v1/rca/human-review", json={
        "thread_id": thread_id,
        "action": "approve",
        "reviewer": "Chief Reliability Engineer",
        "notes": "Vdc > 195V overfrequency trip verified via API test.",
    })
    assert resp_review.status_code == 200
    review_data = resp_review.json()
    assert review_data["pipeline_status"] == "COMPLETED"
    assert review_data["current_step"] == 7
    assert "incident_report_8d" in review_data
    assert "sap_work_order" in review_data
    assert review_data["sap_work_order"]["equipment_id"] == "10049201"


def test_api_copilot_chat_stream(client):
    payload = {
        "messages": [
            {"role": "user", "content": "What is the acoustic evidence for impeller cavitation?"}
        ],
        "model": "deepseek-chat",
    }
    with client.stream("POST", "/api/v1/copilot/chat/stream", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        chunks = []
        for line in response.iter_lines():
            if line and line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                chunk = json.loads(data_str)
                chunks.append(chunk)

        assert len(chunks) > 0
        all_content = "".join([c.get("content", "") for c in chunks])
        all_reasoning = "".join([c.get("reasoning_content", "") for c in chunks])
        assert len(all_content) > 0 or len(all_reasoning) > 0


def test_api_hil_incident_and_latest(client):
    # Ingest incident
    ingest_payload = {
        "asset_id": "VFD_VM_01",
        "fault_code": 6,
        "fault_description": "Deceleration Overvoltage (Err06) - DC link regeneration surge",
        "incident_id": "INC-TEST-API-001",
        "pre_fault_telemetry": [
            {"timestamp": 1726041000, "f_out": 45.0, "current": 1.4, "v_dc": 312.0, "fault_code": 0},
            {"timestamp": 1726041060, "f_out": 0.0, "current": 3.6, "v_dc": 745.0, "fault_code": 6},
        ],
    }
    resp = client.post("/api/v1/telemetry/incident", json=ingest_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "INCIDENT_INGESTED"

    # Verify latest incident
    resp_latest = client.get("/api/v1/telemetry/latest_incident")
    assert resp_latest.status_code == 200
    latest = resp_latest.json()
    assert latest["has_incident"] is True
    assert latest["incident_data"]["incident_id"] == "INC-TEST-API-001"
    assert latest["incident_data"]["fault_code"] == 6


def test_api_rca_normal_baseline(client):
    thread_id = "test-normal-baseline-thread"
    resp = client.post("/api/v1/rca/run", json={
        "dataset_id": "normal",
        "asset_id": "P-301A",
        "thread_id": thread_id,
        "use_deepseek": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_active_trip"] is False
    assert data["pipeline_status"] == "NORMAL_STABLE"
    assert data["is_paused_at_hitl"] is False
    assert data["current_step"] == 2
