"""Behavioral regressions: observations must never be rewritten to fit a diagnosis."""

from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import BackgroundTasks

from industrial_rca.data.telemetry_generator import TelemetryDataset, TelemetryStore
from industrial_rca.graph.nodes import aggregate_hypotheses, ingest_telemetry_event
from industrial_rca.graph.workflow import route_after_review
from industrial_rca.tools.cmms_connector import CMMSConnector
from industrial_rca.tools.deepseek_client import DeepSeekClient


@pytest.mark.parametrize("fault_code,tag,value", [
    (2, "current", 0.7), (3, "current", 0.8),
    (6, "v_dc", 181.3), (11, "current", 0.9),
])
def test_hardware_readings_are_not_forced_over_a_trip_threshold(ingestion, fault_code, tag, value):
    rows = [{"timestamp": 100, tag: value}, {"timestamp": 101, tag: value}]
    incident = ingestion.IncidentPayload(
        incident_id="INC-REAL", fault_code=fault_code, pre_fault_telemetry=deepcopy(rows),
    )
    original = deepcopy(incident.pre_fault_telemetry)
    ingestion.ingest_incident(incident, BackgroundTasks())
    dataset = TelemetryStore.get(ingestion.SCENARIOS_REGISTRY["hil"])
    assert dataset.df_1hz[tag].tolist() == [value, value]
    assert incident.pre_fault_telemetry == original, "Ingestion mutated its caller's observations"


def test_historical_fault_transitions_are_preserved(ingestion):
    rows = [{"timestamp": 100, "fault_code": 2}, {"timestamp": 101, "fault_code": 6}]
    incident = ingestion.IncidentPayload(fault_code=6, pre_fault_telemetry=rows)
    ingestion.ingest_incident(incident, BackgroundTasks())
    dataset = TelemetryStore.get(ingestion.SCENARIOS_REGISTRY["hil"])
    assert dataset.df_1hz["fault_code"].tolist() == [2, 6]


def test_missing_hardware_channels_and_waveforms_remain_missing(ingestion):
    incident = ingestion.IncidentPayload(
        fault_code=6, pre_fault_telemetry=[{"timestamp": 100, "fault_code": 6}],
    )
    ingestion.ingest_incident(incident, BackgroundTasks())
    dataset = TelemetryStore.get(ingestion.SCENARIOS_REGISTRY["hil"])
    observed = dataset.df_1hz.drop(columns=["timestamp_sec"], errors="ignore")
    assert set(observed.columns) == {"timestamp", "fault_code"}
    assert not dataset.normal_waveform
    assert not dataset.fault_waveform


def test_incident_without_samples_does_not_manufacture_a_history(ingestion):
    ingestion.ingest_incident(ingestion.IncidentPayload(fault_code=6), BackgroundTasks())
    dataset = TelemetryStore.get(ingestion.SCENARIOS_REGISTRY["hil"])
    assert dataset.df_1hz.empty
    assert dataset.metadata["fault_code"] == 6


def test_ingestion_keeps_the_external_incident_identity():
    dataset = TelemetryDataset(
        scenario_name="hardware incident", df_1hz=pd.DataFrame({"fault_code": [6]}),
        metadata={"asset_id": "VFD_VM_01", "incident_id": "INC-EXTERNAL-123", "fault_code": 6},
        normal_waveform={}, fault_waveform={},
    )
    dataset_id = TelemetryStore.register(dataset, "proposal-identity")
    result = ingest_telemetry_event({"dataset_id": dataset_id, "incident_id": "INC-EXTERNAL-123"})
    assert result["incident_id"] == "INC-EXTERNAL-123"


def test_all_refuted_hypotheses_do_not_produce_a_winner():
    result = aggregate_hypotheses({"asset_id": "VFD_VM_01", "hypothesis_results": [{
        "hypothesis_id": "H_VFD_ERR06", "name": "Overvoltage", "status": "REFUTED",
        "confidence": 0.99, "falsification_rationale": "No observed voltage excursion",
        "evidence": [], "metrics": {}, "proposed_actions": [],
    }]})
    assert result.get("winning_hypothesis") is None


def test_missing_credentials_report_unavailable_instead_of_a_canned_diagnosis(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = DeepSeekClient(api_key="mock", register_active=False)
    result = client.chat_completion([{"role": "user", "content": "Why did the motor trip?"}])
    assert result["success"] is False
    assert result.get("error")
    assert "Err06" not in result.get("content", "")


def test_provider_failure_is_not_replaced_with_a_successful_mock():
    def fail(**kwargs):
        raise TimeoutError("provider timed out")

    client = DeepSeekClient(api_key="mock", register_active=False)
    client.is_live = True
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
    result = client.chat_completion([{"role": "user", "content": "Diagnose Err13"}])
    assert result["success"] is False
    assert "provider timed out" in result.get("error", "")
    assert not result.get("content")


def test_provider_adapter_round_trips_native_tool_calls_and_reasoning():
    captured = {}
    native_call = {
        "id": "measure-voltage", "type": "function",
        "function": {"name": "profile_telemetry", "arguments": '{"tag":"v_dc"}'},
    }

    def create(**kwargs):
        captured.update(kwargs)
        call = SimpleNamespace(**native_call, model_dump=lambda **options: native_call)
        message = SimpleNamespace(content=None, reasoning_content="Select a measurement tool", tool_calls=[call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    client = DeepSeekClient(api_key="mock", register_active=False)
    client.is_live = True
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    schemas = [{"type": "function", "function": {
        "name": "profile_telemetry", "description": "Profile a measured channel",
        "parameters": {"type": "object", "properties": {"tag": {"type": "string"}}, "required": ["tag"]},
    }}]
    result = client.chat_completion([{"role": "user", "content": "Inspect the trip"}], tools=schemas, tool_choice="auto")
    assert captured["tools"] == schemas
    assert captured["tool_choice"] == "auto"
    assert result["tool_calls"] == [native_call]
    assert result["reasoning_content"] == "Select a measurement tool"


def test_stream_failure_does_not_emit_a_fabricated_diagnosis():
    client = DeepSeekClient(api_key="mock", register_active=False)
    chunks = list(client.chat_completion_stream([{"role": "user", "content": "Why did it trip?"}]))
    assert any(chunk.get("error") for chunk in chunks)
    assert not any("Err06" in chunk.get("content", "") for chunk in chunks)


def test_unknown_asset_has_no_borrowed_maintenance_history():
    assert CMMSConnector().query_maintenance_history("UNREGISTERED-MOTOR") == []


def test_work_order_uses_the_reviewed_actions_without_unrelated_parts():
    action = "Inspect cooling fan obstruction and record airflow"
    order = CMMSConnector().generate_sap_pm01_work_order(
        asset_id="IND_MOTOR_01", incident_id="INC-THERMAL", failure_mode="Cooling restriction",
        root_cause_summary="Cooling requires inspection", corrective_actions=[action],
    )["sap_work_order"]
    assert any(action in str(operation) for operation in order["operations"])
    assert not order["materials_required"], "No parts were specified by the reviewed diagnosis"
    assert "braking resistor" not in str(order).lower()


@pytest.mark.parametrize("state", [{}, {"human_review_decision": {}}, {"human_review_decision": None}])
def test_absent_review_decision_never_approves_maintenance(state):
    assert route_after_review(state) == "handle_rejection"
