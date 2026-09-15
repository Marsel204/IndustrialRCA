"""
Unit tests for industrial_rca.graph.debugger module.
Verifies state snapshot dumping, serialization sanitization, and state replay loading.
"""

import os
import shutil
from pathlib import Path
from industrial_rca.graph.debugger import (
    dump_node_state,
    load_node_state,
    debug_node,
    DEBUG_DIR,
)


def test_dump_and_load_node_state():
    test_thread = "test-thread-debug-01"
    sample_state = {
        "dataset_id": "ds_test_123",
        "asset_id": "P-301A",
        "metrics": {"rpm": 2980.0, "current": 84.2},
    }
    sample_output = {
        "pipeline_status": "TEST_SUCCESS",
        "detected_anomalies": ["VI-301-R"],
    }

    dumped_path = dump_node_state(
        node_name="test_node",
        state_data=sample_state,
        output_data=sample_output,
        thread_id=test_thread,
        is_error=False,
    )

    assert dumped_path is not None
    assert dumped_path.exists()

    loaded = load_node_state(dumped_path)
    assert loaded["node_name"] == "test_node"
    assert loaded["thread_id"] == test_thread
    assert loaded["is_error"] is False
    assert loaded["input_state"]["dataset_id"] == "ds_test_123"
    assert loaded["output_state"]["pipeline_status"] == "TEST_SUCCESS"

    # Clean up test output
    shutil.rmtree(DEBUG_DIR / "runs" / test_thread, ignore_errors=True)


def test_debug_node_decorator_catches_and_dumps():
    test_thread = "test-thread-err"

    @debug_node("failing_test_node")
    def faulty_node(state):
        raise ValueError("Simulated sensor failure in node")

    sample_state = {"asset_id": "P-301A", "incident_id": test_thread}

    try:
        faulty_node(sample_state)
    except ValueError as e:
        assert "Simulated sensor failure" in str(e)

    err_files = list((DEBUG_DIR / "runs" / test_thread).glob("ERR_*_failing_test_node.json"))
    assert len(err_files) == 1

    loaded_err = load_node_state(err_files[0])
    assert loaded_err["is_error"] is True
    assert "ValueError: Simulated sensor failure" in loaded_err["error_msg"]

    # Clean up
    shutil.rmtree(DEBUG_DIR / "runs" / test_thread, ignore_errors=True)
