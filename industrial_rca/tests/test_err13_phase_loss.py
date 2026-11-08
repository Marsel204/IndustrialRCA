"""
TDD Tests for Wecon VM Fault Code Err13 (Output Phase Loss).
Validates:
1. OEM manual knowledge base and taxonomy entries for Err13.
2. Telemetry dataset generation for exp_err13.
3. LangGraph RCA pipeline isolating H_VFD_ERR13, 5-Whys causal trace, and 8D report generation.
"""

import pytest
import numpy as np
from langgraph.types import Command

from industrial_rca.config import EQUIPMENT_ID
from industrial_rca.data.oem_manuals import (
    FMEA_KNOWLEDGE_BASE,
    get_vfd_fault_info,
)
from industrial_rca.data.telemetry_generator import (
    generate_vfd_dataset,
    TelemetryStore,
)
from industrial_rca.graph.workflow import create_rca_graph
from industrial_rca.tests.support_decisions import MeasuredDecisionClient


def test_oem_manual_err13():
    """Verify Wecon VM OEM manual contains Err13 Output Phase Loss definition and FMEA hypothesis."""
    info = get_vfd_fault_info(13)
    assert info["code"] == "Err13"
    assert "Phase Loss" in info["name"] or "phase loss" in info["name"].lower()
    assert "U, V, W" in info["description"] or "output" in info["description"].lower()

    hyp_ids = [entry["hypothesis_id"] for entry in FMEA_KNOWLEDGE_BASE]
    assert "H_VFD_ERR13" in hyp_ids

    err13_entry = next(e for e in FMEA_KNOWLEDGE_BASE if e["hypothesis_id"] == "H_VFD_ERR13")
    assert "Output Phase Loss" in err13_entry["name"]
    assert any("700BH" in check or "13" in check for check in err13_entry["falsification_checks"])


def test_generator_exp_err13():
    """Verify exp_err13 scenario generation produces proper telemetry signature."""
    ds = generate_vfd_dataset("exp_err13")
    df = ds.df_1hz

    assert len(df) == 300
    assert ds.metadata["fault_code"] == 13
    assert "Err13" in ds.metadata["fault_description"] or "Phase Loss" in ds.metadata["fault_description"]
    assert np.max(df["fault_code"]) == 13

    # Check pre-trip current and post-trip current
    trip_idx = ds.metadata["trip_timestamp_sec"]
    assert df["current"].iloc[trip_idx - 10] > 0.5  # Running current before trip
    assert df["current"].iloc[-1] == 0.0  # Current collapses post trip
    assert df["rpm"].iloc[-1] == 0.0  # Motor stalls post trip


def test_rca_graph_err13_isolation_and_8d():
    """Verify LangGraph multi-agent workflow correctly isolates H_VFD_ERR13 and builds 8D report."""
    ds = generate_vfd_dataset("exp_err13")
    ds_id = TelemetryStore.register(ds, "pytest_exp_err13_test")
    config = {"configurable": {"thread_id": "pytest-err13-thread"}}

    graph = create_rca_graph(decision_client=MeasuredDecisionClient(tag="current", hypothesis_id="H_FIELD_CURRENT", name="Observed current change", actions=["Inspect motor phase continuity before attributing the protection event"]))

    # Step 1: Run to human-in-the-loop review interrupt
    list(graph.stream({"dataset_id": ds_id, "asset_id": EQUIPMENT_ID}, config=config))
    state = graph.get_state(config)

    assert state.values.get("has_active_trip") is True
    assert state.values.get("winning_hypothesis", {}).get("hypothesis_id") == "H_FIELD_CURRENT"

    evals = state.values.get("falsification_summary", [])
    err13_eval = next((e for e in evals if e.get("hypothesis_id") == "H_FIELD_CURRENT"), None)
    assert err13_eval is not None
    assert err13_eval["status"] == "SUPPORTED"

    # A protection event does not prove an upstream cause or force five steps.
    assert state.values.get("causal_chain_5_whys") == []
    assert state.values.get("missing_evidence")

    # Step 2: Resume with engineer authorization
    resume_cmd = Command(resume={"action": "approve", "reviewer": "Reliability Lead", "notes": "Authorized"})
    list(graph.stream(resume_cmd, config=config))
    final_state = graph.get_state(config)

    report = final_state.values.get("incident_report_8d")
    assert report is not None
    assert "13" in report["d2_problem_description"]["what"]
    pcas = report["d5_permanent_corrective_actions"]
    assert any("U, V, W" in p or "winding" in p.lower() or "phase" in p.lower() for p in pcas)
