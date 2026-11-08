"""Additional adversarial checks on incident isolation and model/tool boundaries."""

import pandas as pd
import pytest

from industrial_rca.agent.contracts import Hypothesis
from industrial_rca.agent.tools import InvestigationTools
from industrial_rca.data.telemetry_generator import (
    TelemetryDataset,
    TelemetryStore,
    generate_normal_scenario,
)
from industrial_rca.graph.workflow import create_rca_graph
from industrial_rca.tests.agentic.test_adaptive_investigation import (
    ScriptedDecisionClient,
    inconclusive,
    investigate,
    tool_call,
)
from industrial_rca.tests.support_decisions import MeasuredDecisionClient


def test_oversized_function_name_terminates_without_an_unhandled_exception():
    client = ScriptedDecisionClient([tool_call("x" * 129, {}, "call")])
    assert investigate(client).values["pipeline_status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01, 1.01])
def test_nonfinite_or_out_of_range_confidence_is_rejected(value):
    with pytest.raises(ValueError):
        Hypothesis(
            hypothesis_id="H",
            name="Test",
            status="SUPPORTED",
            confidence=value,
            evidence_ids=[],
            falsification_rationale="Needs evidence",
        )


def test_duplicate_call_id_does_not_overwrite_the_original_observation():
    client = ScriptedDecisionClient(
        [
            tool_call("profile_telemetry", {"tag": "v_dc"}, "measurement"),
            tool_call("profile_telemetry", {"tag": "fault_code"}, "measurement"),
            inconclusive("Collect more evidence"),
        ]
    )
    snapshot = investigate(client)
    observations = snapshot.values["agent_observations"]
    assert len({item["observation_id"] for item in observations}) == len(observations)
    assert observations[0]["result"]["max"] == 219.25
    assert observations[1]["error"]


def test_model_cannot_select_another_dataset_through_tool_arguments():
    client = ScriptedDecisionClient(
        [
            tool_call(
                "profile_telemetry",
                {"tag": "v_dc", "dataset_id": "another-incident"},
                "cross-incident",
            ),
            inconclusive("Only the incident dataset is accessible"),
        ]
    )
    snapshot = investigate(client)
    assert snapshot.values["agent_observations"][0]["error"]


def test_live_maintenance_tool_reports_unavailable_instead_of_simulation_records():
    client = ScriptedDecisionClient(
        [
            tool_call("lookup_maintenance", {"asset_id": "VFD_VM_01"}, "history"),
            inconclusive("Obtain actual maintenance records"),
        ]
    )
    snapshot = investigate(client)
    observation = snapshot.values["agent_observations"][0]
    assert observation["source_type"] == "unavailable"
    assert observation["result"] is None
    assert "No live CMMS" in observation["error"]


def test_topology_reference_alone_cannot_confirm_a_cause():
    client = ScriptedDecisionClient(
        [
            tool_call("trace_topology", {"asset_id": "VFD_VM_01"}, "topology"),
            tool_call(
                "submit_diagnosis",
                {
                    "status": "SUPPORTED",
                    "summary": "Unsupported origin",
                    "root_cause_asset": "PLC_LX_01",
                    "root_cause_description": "PLC caused the trip",
                    "hypotheses": [
                        {
                            "hypothesis_id": "H",
                            "name": "PLC issue",
                            "status": "SUPPORTED",
                            "confidence": 0.9,
                            "evidence_ids": ["topology"],
                            "falsification_rationale": "Only a configured edge was found",
                            "proposed_actions": [],
                        }
                    ],
                    "missing_evidence": [],
                    "causal_chain_5_whys": [],
                },
                "finish",
            ),
            inconclusive("PLC telemetry or an inspection is required"),
        ]
    )
    snapshot = investigate(client)
    assert snapshot.values["winning_hypothesis"] is None
    assert snapshot.values["agent_observations"][1]["error"]


def test_no_sensor_channels_cannot_be_declared_a_healthy_baseline():
    dataset = TelemetryDataset(
        "only timestamps", pd.DataFrame({"timestamp_sec": [0, 1]}), {}, {}, {}
    )
    dataset_id = TelemetryStore.register(dataset, "no-sensors")
    client = ScriptedDecisionClient([inconclusive("No sensor channels were provided")])
    graph = create_rca_graph(decision_client=client)
    result = graph.invoke(
        {"dataset_id": dataset_id}, {"configurable": {"thread_id": "no-sensors"}}
    )
    assert result["pipeline_status"] == "INCONCLUSIVE"
    assert result["missing_evidence"]


def test_new_incident_in_a_reused_thread_clears_prior_winner_and_approval():
    client = MeasuredDecisionClient()
    dataset = generate_normal_scenario(duration_sec=10)
    dataset.metadata["fault_code"] = 99
    first_id = TelemetryStore.register(dataset, "isolation-first")
    graph = create_rca_graph(decision_client=client)
    config = {"configurable": {"thread_id": "reuse-incident"}}
    first = graph.invoke({"dataset_id": first_id}, config)
    assert first["winning_hypothesis"]
    second_id = TelemetryStore.register(
        generate_normal_scenario(duration_sec=10), "isolation-second"
    )
    second = graph.invoke({"dataset_id": second_id}, config)
    assert second["pipeline_status"] == "NORMAL_STABLE"
    assert second.get("winning_hypothesis") is None
    assert second.get("human_review_decision") is None
    assert second.get("sap_work_order") is None
    assert second["agent_messages"] == []
    assert second["incident_id"] != first["incident_id"]


def test_simulated_maintenance_is_labelled_and_asset_scoped():
    dataset = generate_normal_scenario(duration_sec=10)
    dataset_id = TelemetryStore.register(dataset, "simulated-source")
    tools = InvestigationTools(dataset_id, "VFD_VM_01")
    registry = tools.registry["lookup_maintenance"]
    result = registry.handler(registry.arguments(asset_id="VFD_VM_01"))
    assert registry.source == "simulated"
    assert all(record["source_type"] == "simulated" for record in result["records"])
    with pytest.raises(ValueError, match="outside"):
        tools.require_asset("ANOTHER-PLANT")


def test_live_dataset_preserves_sparse_channels_and_has_no_generated_waveforms():
    from industrial_rca.data.telemetry_generator import generate_vfd_dataset

    frame = pd.DataFrame({"timestamp": [100, 101], "current": [0.7, 0.8]})
    dataset = generate_vfd_dataset("live_stream", df_live=frame)
    assert dataset.metadata["is_simulated"] is False
    assert set(dataset.df_1hz.columns) == {"timestamp", "timestamp_sec", "current"}
    assert not dataset.normal_waveform and not dataset.fault_waveform
    assert frame.columns.tolist() == ["timestamp", "current"]


def test_offline_live_query_does_not_manufacture_zero_readings(monkeypatch):
    from industrial_rca.tools.influx_tool import GLOBAL_TSDB, InfluxDBTelemetryTool

    monkeypatch.setattr(GLOBAL_TSDB, "get_latest", lambda asset_id: None)
    tool = InfluxDBTelemetryTool()
    monkeypatch.setattr(tool, "query_flux", lambda query: [])
    assert tool.get_live_telemetry(limit=20).empty


def test_nonstandard_json_constants_become_a_tool_error():
    call = tool_call("profile_telemetry", {}, "nonfinite")
    call["tool_calls"][0]["function"]["arguments"] = '{"tag":"v_dc","start_index":NaN}'
    client = ScriptedDecisionClient(
        [call, inconclusive("Valid arguments are required")]
    )
    snapshot = investigate(client)
    assert snapshot.values["pipeline_status"] == "INCONCLUSIVE"
    assert snapshot.values["agent_observations"][0]["error"]


def test_long_external_incident_id_remains_usable_as_a_dataset_reference():
    dataset = generate_normal_scenario(duration_sec=10)
    dataset.metadata["fault_code"] = 99
    dataset_id = TelemetryStore.register(dataset, "ds_hil_6_" + "x" * 128)
    graph = create_rca_graph(decision_client=MeasuredDecisionClient())
    result = graph.invoke(
        {"dataset_id": dataset_id}, {"configurable": {"thread_id": "long-id"}}
    )
    assert result["winning_hypothesis"]


def test_classification_requires_exact_reference_fields():
    from industrial_rca.agent.contracts import Diagnosis, InvestigationBudget
    from industrial_rca.agent.runtime import InvestigationRuntime

    dataset_id = TelemetryStore.register(
        generate_normal_scenario(duration_sec=10), "classification"
    )
    tools = InvestigationTools(dataset_id, "VFD_VM_01")
    observations = [
        {
            "observation_id": "measurement",
            "tool": "profile_telemetry",
            "source_type": "measured",
            "result": {"max": 219.25},
        },
        {
            "observation_id": "oem",
            "tool": "lookup_oem",
            "source_type": "reference",
            "result": {"iso_info": {"iso_code": "ISO-EXAMPLE"}},
        },
    ]
    diagnosis = Diagnosis(
        status="SUPPORTED",
        summary="Observed transient",
        root_cause_asset="VFD_VM_01",
        root_cause_description="Transient cause remains open",
        hypotheses=[
            Hypothesis(
                hypothesis_id="H",
                name="Transient",
                status="SUPPORTED",
                confidence=0.6,
                evidence_ids=["measurement"],
                falsification_rationale="Upstream cause unverified",
            )
        ],
        fmea_classification={"iso_code": ":"},
    )
    runtime = InvestigationRuntime(None, InvestigationBudget())
    with pytest.raises(ValueError, match="Classification"):
        runtime.validate_diagnosis(diagnosis, observations, tools)
    diagnosis.fmea_classification = {"iso_code": "ISO-EXAMPLE"}
    runtime.validate_diagnosis(diagnosis, observations, tools)


def test_review_endpoint_requires_an_explicit_named_decision():
    from fastapi.testclient import TestClient

    from industrial_rca.api import api_app

    response = TestClient(api_app).post(
        "/api/v1/rca/human-review", json={"thread_id": "unknown"}
    )
    assert response.status_code == 422


def test_review_endpoint_cannot_approve_an_unresolved_investigation(monkeypatch):
    from fastapi.testclient import TestClient

    from industrial_rca import api

    graph = create_rca_graph(
        decision_client=ScriptedDecisionClient(
            [inconclusive("Missing physical evidence")]
        )
    )
    dataset = generate_normal_scenario(duration_sec=10)
    dataset.metadata["fault_code"] = 99
    dataset_id = TelemetryStore.register(dataset, "unresolved-review")
    graph.invoke(
        {"dataset_id": dataset_id}, {"configurable": {"thread_id": "unresolved-review"}}
    )
    monkeypatch.setattr(api, "GLOBAL_RCA_GRAPH", graph)
    response = TestClient(api.api_app).post(
        "/api/v1/rca/human-review",
        json={
            "thread_id": "unresolved-review",
            "action": "approve",
            "reviewer": "Test Engineer",
        },
    )
    assert response.status_code == 409


def test_reviewing_one_thread_does_not_replace_another_active_incident(monkeypatch):
    from fastapi.testclient import TestClient

    from industrial_rca import api

    graph = create_rca_graph(decision_client=MeasuredDecisionClient())
    dataset = generate_normal_scenario(duration_sec=10)
    dataset.metadata["fault_code"] = 99
    dataset_id = TelemetryStore.register(dataset, "review-scoped")
    graph.invoke(
        {"dataset_id": dataset_id}, {"configurable": {"thread_id": "review-scoped"}}
    )
    active = {
        "has_incident": True,
        "incident_data": {"thread_id": "another-thread"},
        "graph_result": {"sentinel": True},
        "pipeline_status": "TRIGGERED",
    }
    monkeypatch.setattr(api, "LATEST_HIL_INCIDENT", active)
    monkeypatch.setattr(api, "GLOBAL_RCA_GRAPH", graph)
    response = TestClient(api.api_app).post(
        "/api/v1/rca/human-review",
        json={
            "thread_id": "review-scoped",
            "action": "approve",
            "reviewer": "Test Engineer",
        },
    )
    assert response.status_code == 200
    assert active["graph_result"] == {"sentinel": True}
    assert active["pipeline_status"] == "TRIGGERED"
