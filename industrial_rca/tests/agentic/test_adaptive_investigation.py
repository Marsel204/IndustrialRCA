"""Proposed public seam: inject a decision client into the real compiled graph.

The fake scripts provider decisions, never the executor's tool observations.
All cases exercise actual LangGraph state and termination without paid API calls.
"""

import json
from copy import deepcopy

import pandas as pd
from langgraph.types import Command

from industrial_rca.data.telemetry_generator import TelemetryDataset, TelemetryStore
from industrial_rca.graph.workflow import create_rca_graph


def tool_call(name, arguments, call_id):
    return {"success": True, "is_mock": False, "content": "", "tool_calls": [{
        "id": call_id, "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }]}


def inconclusive(missing):
    return tool_call("submit_diagnosis", {
        "status": "INCONCLUSIVE", "summary": "More measurements are required",
        "hypotheses": [], "causal_chain_5_whys": [], "root_cause_asset": None,
        "root_cause_description": "Unresolved", "missing_evidence": [missing],
    }, "finish")


class ScriptedDecisionClient:
    is_live = True
    default_model = "test-decision-client"

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": deepcopy(messages), **kwargs})
        index = len(self.calls) - 1
        assert index < len(self.responses), "Agent exceeded the scripted decision budget"
        return deepcopy(self.responses[index])


def investigate(client, *, max_iterations=4):
    dataset = TelemetryDataset(
        scenario_name="unrecognized field event",
        df_1hz=pd.DataFrame({"timestamp_sec": [0, 1, 2], "v_dc": [180.0, 181.0, 219.25], "fault_code": [0, 0, 99]}),
        metadata={"asset_id": "VFD_VM_01", "fault_code": 99, "anomaly_expected": True},
        normal_waveform={}, fault_waveform={},
    )
    dataset_id = TelemetryStore.register(dataset, "proposal-adaptive")
    graph = create_rca_graph(decision_client=client, max_agent_iterations=max_iterations)
    config = {"configurable": {"thread_id": "proposal-adaptive"}, "recursion_limit": 50}
    list(graph.stream({"dataset_id": dataset_id, "asset_id": "VFD_VM_01", "use_deepseek": True}, config))
    return graph.get_state(config)


def test_model_observes_tool_results_before_choosing_its_next_action():
    client = ScriptedDecisionClient([
        tool_call("profile_telemetry", {"tag": "v_dc"}, "measure-voltage"),
        tool_call("trace_topology", {"asset_id": "VFD_VM_01", "direction": "upstream"}, "trace-upstream"),
        inconclusive("Capture a pre-trip voltage waveform and inspect the supply"),
    ])
    snapshot = investigate(client)
    assert len(client.calls) == 3
    measurements = [message for message in client.calls[1]["messages"] if message.get("role") == "tool"]
    assert any(message.get("tool_call_id") == "measure-voltage" and "219.25" in message["content"] for message in measurements)
    topology = [message for message in client.calls[2]["messages"] if message.get("role") == "tool"]
    assert any(message.get("tool_call_id") == "trace-upstream" and "CB_01" in message["content"] for message in topology)
    assert client.calls[0]["tools"], "The model must receive executable tool schemas"
    assert snapshot.values["pipeline_status"] == "INCONCLUSIVE"
    assert snapshot.values.get("winning_hypothesis") is None
    assert not snapshot.values.get("sap_work_order")


def test_unknown_tool_returns_an_observation_and_can_be_replanned():
    client = ScriptedDecisionClient([
        tool_call("write_vfd_register", {"register": "F0.18", "value": 0.1}, "forbidden"),
        inconclusive("Only read-only investigation tools are available"),
    ])
    snapshot = investigate(client)
    errors = [message for message in client.calls[1]["messages"] if message.get("role") == "tool"]
    assert any(message.get("tool_call_id") == "forbidden" and "error" in message["content"].lower() for message in errors)
    assert snapshot.values["pipeline_status"] == "INCONCLUSIVE"


def test_invalid_tool_arguments_are_reported_without_crashing():
    invalid = tool_call("profile_telemetry", {}, "bad-arguments")
    invalid["tool_calls"][0]["function"]["arguments"] = "{invalid json"
    client = ScriptedDecisionClient([invalid, inconclusive("A valid measurement request is required")])
    snapshot = investigate(client)
    observations = [message for message in client.calls[1]["messages"] if message.get("role") == "tool"]
    assert any(message.get("tool_call_id") == "bad-arguments" and "error" in message["content"].lower() for message in observations)
    assert snapshot.values["pipeline_status"] == "INCONCLUSIVE"


def test_repeated_tool_requests_stop_at_the_investigation_budget():
    client = ScriptedDecisionClient([
        tool_call("profile_telemetry", {"tag": "v_dc"}, f"profile-{index}") for index in range(3)
    ])
    snapshot = investigate(client, max_iterations=3)
    assert len(client.calls) <= 3
    assert snapshot.values["pipeline_status"] == "INCONCLUSIVE"
    assert not snapshot.values.get("sap_work_order")


def test_provider_failure_stops_without_a_synthetic_root_cause():
    client = ScriptedDecisionClient([{"success": False, "is_mock": False, "error": "provider unavailable", "content": ""}])
    snapshot = investigate(client)
    assert len(client.calls) == 1
    assert snapshot.values["pipeline_status"] == "INCONCLUSIVE"
    assert snapshot.values.get("winning_hypothesis") is None
    assert not snapshot.values.get("causal_chain_5_whys")


def test_uncited_model_conclusion_cannot_become_a_confirmed_diagnosis():
    client = ScriptedDecisionClient([
        tool_call("submit_diagnosis", {
            "status": "SUPPORTED", "summary": "A speculative diagnosis",
            "root_cause_asset": "PLC_LX_01", "root_cause_description": "PLC stop caused the trip",
            "hypotheses": [{
                "hypothesis_id": "H_NOVEL", "name": "Novel control fault", "status": "CONFIRMED",
                "confidence": 0.99, "evidence_ids": ["nonexistent-observation"],
                "falsification_rationale": "No evidence was actually collected", "proposed_actions": [],
            }], "causal_chain_5_whys": [], "missing_evidence": [],
        }, "unsupported-conclusion"),
        inconclusive("Obtain measurements that can support or falsify the control fault"),
    ])
    snapshot = investigate(client)
    assert snapshot.values["pipeline_status"] == "INCONCLUSIVE"
    assert snapshot.values.get("winning_hypothesis") is None
    assert not snapshot.values.get("sap_work_order")


def test_novel_evidence_backed_hypothesis_reaches_review_without_a_fault_code_branch():
    conclusion = tool_call("submit_diagnosis", {
        "status": "SUPPORTED", "summary": "Unclassified DC bus transient",
        "root_cause_asset": "VFD_VM_01",
        "root_cause_description": "DC bus rose to 219.25 V; the upstream cause remains unverified",
        "hypotheses": [{
            "hypothesis_id": "H_FIELD_TRANSIENT", "name": "Unclassified DC bus transient",
            "status": "CONFIRMED", "confidence": 0.6, "evidence_ids": ["measure-voltage"],
            "falsification_rationale": "Bus rise is measured; supply and control causes remain open",
            "proposed_actions": ["Capture the upstream supply waveform before another run"],
        }], "causal_chain_5_whys": [], "missing_evidence": ["Upstream supply waveform"],
    }, "finish")
    client = ScriptedDecisionClient([
        tool_call("profile_telemetry", {"tag": "v_dc"}, "measure-voltage"), conclusion,
    ])
    dataset = TelemetryDataset(
        scenario_name="novel field event",
        df_1hz=pd.DataFrame({"timestamp_sec": [0, 1, 2], "v_dc": [180.0, 181.0, 219.25], "fault_code": [0, 0, 99]}),
        metadata={"asset_id": "VFD_VM_01", "fault_code": 99, "anomaly_expected": True},
        normal_waveform={}, fault_waveform={},
    )
    dataset_id = TelemetryStore.register(dataset, "proposal-novel")
    graph = create_rca_graph(decision_client=client, max_agent_iterations=4)
    config = {"configurable": {"thread_id": "proposal-novel"}, "recursion_limit": 50}
    list(graph.stream({"dataset_id": dataset_id, "asset_id": "VFD_VM_01", "use_deepseek": True}, config))
    pending = graph.get_state(config)
    assert pending.next == ("human_review",)
    assert pending.tasks[0].interrupts
    assert pending.values["winning_hypothesis"]["hypothesis_id"] == "H_FIELD_TRANSIENT"
    assert not pending.values.get("sap_work_order")

    list(graph.stream(Command(resume={"action": "approve", "reviewer": "Test Engineer", "notes": "Authorize diagnostic follow-up"}), config))
    complete = graph.get_state(config)
    assert complete.values["pipeline_status"] == "COMPLETED"
    assert len(client.calls) == 2, "Review resume must not rerun completed model or tool calls"
    report = complete.values["incident_report_8d"]
    assert "219.25" in report["d4_root_cause_analysis"]["root_cause_statement"]
    assert report["d5_permanent_corrective_actions"] == ["Capture the upstream supply waveform before another run"]
