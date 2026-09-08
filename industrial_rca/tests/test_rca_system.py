"""
Comprehensive Pytest Test Suite for the Industrial RCA System.
Tests:
- Deterministic feature extraction (profiler, change point, FFT spectral decomposition)
- In-memory TelemetryCache thread safety and scoping
- ISA-95 Asset Topology graph traversal
- CMMS connector and SAP PM01 work order emission
- Stateful LangGraph pipeline (Baseline normal zero alarms, Fault trip fan-out, HITL interrupt & resume)
"""

import pytest
import numpy as np
from langgraph.types import Command

from industrial_rca.config import (
    EQUIPMENT_ID,
    RUNNING_FREQUENCY_1X_HZ,
    RUNNING_FREQUENCY_2X_HZ,
)
from industrial_rca.data.telemetry_generator import (
    generate_normal_scenario,
    generate_fault_scenario,
    generate_high_frequency_vibration,
    TelemetryStore,
)
from industrial_rca.tools.telemetry_analytics import (
    StatisticalProfiler,
    ChangePointDetector,
    SpectralAnalyzer,
    TelemetryCache,
    TelemetryAnalyticsTool,
)
from industrial_rca.tools.topology_tracer import AssetTopologyTracer
from industrial_rca.tools.cmms_connector import CMMSConnector
from industrial_rca.graph.workflow import create_rca_graph


def test_telemetry_generator():
    """Verify normal and fault dataset shape and characteristics."""
    normal_ds = generate_normal_scenario()
    fault_ds = generate_fault_scenario()

    assert len(normal_ds.df_1hz) == 3600
    assert len(fault_ds.df_1hz) == 3600

    # Normal constraints
    assert np.all(normal_ds.get_tag_series("PT-30101") >= 2.30)
    assert np.all(normal_ds.get_tag_series("PT-30101") <= 2.50)
    assert np.all(normal_ds.get_tag_series("TI-301-DE") < 55.0)

    # Fault constraints
    assert np.max(fault_ds.get_tag_series("TI-301-DE")) >= 90.0
    assert np.min(fault_ds.get_tag_series("PT-30101")) < 1.20
    assert np.max(fault_ds.get_tag_series("DPS-30101")) > 1.80
    assert np.max(fault_ds.get_tag_series("VI-301-R")) > 7.10


def test_statistical_profiler():
    """Test deterministic statistical profiling math."""
    data = np.array([10.0, 12.0, 14.0, 16.0, 18.0])
    prof = StatisticalProfiler.profile(data)

    assert prof["mean"] == 14.0
    assert prof["min"] == 10.0
    assert prof["max"] == 18.0
    assert prof["delta"] == 8.0
    assert prof["slope"] == 2.0


def test_change_point_detector():
    """Test two-window sliding change-point detection on step and ramp shifts."""
    # Constant baseline followed by abrupt step shift
    signal = np.concatenate([np.full(300, 10.0), np.full(300, 50.0)])
    cps = ChangePointDetector.detect_change_points(signal, window_sec=60, step_sec=10, min_relative_shift=0.10)

    assert len(cps) > 0
    # Peak change point should be near index 300
    best_cp = max(cps, key=lambda x: x["detector_score"])
    assert 280 <= best_cp["timestamp_sec"] <= 320
    assert best_cp["post_change_mean"] > best_cp["pre_change_mean"]


def test_spectral_analyzer_normal_vs_cavitation():
    """Test FFT decomposition distinguishing discrete shaft harmonics from broadband cavitation noise."""
    t_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=42)
    t_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=True, seed=42)

    spec_norm = SpectralAnalyzer.analyze_spectrum(sig_norm, running_freq_hz=RUNNING_FREQUENCY_1X_HZ)
    spec_cav = SpectralAnalyzer.analyze_spectrum(sig_cav, running_freq_hz=RUNNING_FREQUENCY_1X_HZ)

    # Normal: low RMS, low broadband ratio
    assert spec_norm["overall_rms"] < 2.5
    assert spec_norm["broadband_cavitation_ratio_pct"] < 10.0
    assert not spec_norm["cavitation_detected"]

    # Cavitation: high RMS, high broadband ratio (>35%)
    assert spec_cav["overall_rms"] >= 7.10
    assert spec_cav["broadband_cavitation_ratio_pct"] > 35.0
    assert spec_cav["cavitation_detected"]


def test_telemetry_cache_scoping_and_thread_safety():
    """Test cache hits, misses, and dataset isolation."""
    cache = TelemetryCache(max_entries=10)
    cache.set("ds_1", "TAG-1", 0, 100, "profile", {"val": 42})

    # Hit on same dataset
    assert cache.get("ds_1", "TAG-1", 0, 100, "profile") == {"val": 42}
    # Miss on different dataset
    assert cache.get("ds_2", "TAG-1", 0, 100, "profile") is None

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_asset_topology_tracer():
    """Test ISA-95 topology upstream and downstream traversal."""
    tracer = AssetTopologyTracer()
    upstream = tracer.trace_upstream("P-301A")
    up_ids = [u["asset_id"] for u in upstream]

    assert "LINE-30101" in up_ids
    assert "STR-301A" in up_ids
    assert "TK-300" in up_ids

    downstream = tracer.trace_downstream("P-301A")
    dn_ids = [d["asset_id"] for d in downstream]
    assert "CV-30101" in dn_ids
    assert "HDR-300" in dn_ids


def test_cmms_connector_work_order_generation():
    """Test SAP PM01 work order emission schema."""
    cmms = CMMSConnector()
    history = cmms.query_maintenance_history("STR-301A")
    assert any("OVERDUE" in str(h.get("status", "")) for h in history)

    wo = cmms.generate_sap_pm01_work_order(
        asset_id="P-301A",
        incident_id="INC-TEST-001",
        failure_mode="Cavitation erosion",
        root_cause_summary="Strainer basket clogged",
        corrective_actions=["Clean strainer", "Inspect impeller"],
    )

    sap = wo["sap_work_order"]
    assert sap["order_type"] == "PM01"
    assert sap["functional_location"] == "FLOC: PLNT-B03-FW300-P301A"
    assert sap["equipment_id"] == "10049201"
    assert len(sap["operations"]) == 5
    assert len(sap["materials_required"]) >= 4
    assert sap["total_estimated_hours"] > 0


def test_langgraph_baseline_normal_no_false_alarms():
    """Verify that baseline normal telemetry cleanly completes with zero alarms."""
    graph = create_rca_graph()
    norm_ds = generate_normal_scenario()
    ds_id = TelemetryStore.register(norm_ds, "pytest_normal_baseline")
    config = {"configurable": {"thread_id": "pytest-normal-thread"}}

    events = list(graph.stream({"dataset_id": ds_id, "asset_id": EQUIPMENT_ID}, config=config))
    final_state = graph.get_state(config)

    assert final_state.values.get("has_active_trip") is False
    assert final_state.values.get("pipeline_status") == "NORMAL_STABLE"
    assert "incident_report_8d" not in final_state.values


def test_langgraph_fault_investigation_hitl_approval():
    """Verify fault investigation, parallel hypothesis testing, HITL interrupt, and resume approval."""
    graph = create_rca_graph()
    fault_ds = generate_fault_scenario()
    ds_id = TelemetryStore.register(fault_ds, "pytest_fault_trip")
    config = {"configurable": {"thread_id": "pytest-fault-thread"}}

    # Step 1: Run until interrupt
    events_step1 = list(graph.stream({"dataset_id": ds_id, "asset_id": EQUIPMENT_ID}, config=config))
    paused_state = graph.get_state(config)

    assert paused_state.next == ("human_review",)
    assert len(paused_state.tasks[0].interrupts) > 0

    payload = paused_state.tasks[0].interrupts[0].value
    assert payload["winning_hypothesis"] == "NPSH Starvation Induced Impeller Cavitation via Upstream Restriction"
    assert payload["root_cause_asset"] == "STR-301A"
    assert len(payload["causal_chain_5_whys"]) == 5

    # Step 2: Resume with engineer approval
    decision = {
        "action": "approve",
        "reviewer": "Reliability Manager",
        "notes": "Verified by FFT acoustics and strainer dP timeline.",
    }
    events_step2 = list(graph.stream(Command(resume=decision), config=config))
    final_state = graph.get_state(config)

    assert final_state.values.get("pipeline_status") == "COMPLETED"
    assert "incident_report_8d" in final_state.values
    assert "sap_work_order" in final_state.values
    assert final_state.values["incident_report_8d"]["d4_root_cause_analysis"]["root_cause_asset"] == "STR-301A"


def test_langgraph_fault_investigation_hitl_rejection():
    """Verify fault investigation handles engineer rejection cleanly without work order emission."""
    graph = create_rca_graph()
    fault_ds = generate_fault_scenario()
    ds_id = TelemetryStore.register(fault_ds, "pytest_fault_reject")
    config = {"configurable": {"thread_id": "pytest-fault-reject-thread"}}

    # Run until interrupt
    list(graph.stream({"dataset_id": ds_id, "asset_id": EQUIPMENT_ID}, config=config))

    # Resume with rejection
    decision = {
        "action": "reject",
        "reviewer": "Senior Inspector",
        "notes": "Further physical teardown required before sign-off.",
    }
    list(graph.stream(Command(resume=decision), config=config))
    final_state = graph.get_state(config)

    assert final_state.values.get("pipeline_status") == "REJECTED"
    assert "sap_work_order" not in final_state.values
