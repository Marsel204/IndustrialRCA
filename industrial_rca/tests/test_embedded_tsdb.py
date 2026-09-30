import time
import pytest
import pandas as pd
from industrial_rca.data.embedded_tsdb import EmbeddedTSDB


def test_embedded_tsdb_basic_insert_and_latest(tmp_path):
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    now = time.time()
    metric = {
        "timestamp": now,
        "asset_id": "VFD_VM_01",
        "f_out": 40.0,
        "v_dc": 182.0,
        "current": 1.4,
        "rpm": 1200.0,
        "fault_code": 0,
        "status": "RUNNING",
    }
    tsdb.insert(metric)

    latest = tsdb.get_latest("VFD_VM_01")
    assert latest is not None
    assert latest["f_out"] == 40.0
    assert latest["v_dc"] == 182.0
    assert latest["fault_code"] == 0


def test_embedded_tsdb_window_slicing_and_enrichment(tmp_path):
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=200)

    now = time.time()
    # Insert 30 seconds of telemetry
    for i in range(30):
        tsdb.insert({
            "timestamp": now - (29 - i),
            "asset_id": "VFD_VM_01",
            "f_out": 40.0,
            "v_dc": 182.0,
            "current": 1.35,
            "rpm": 1160.0,
            "fault_code": 0,
        })

    df = tsdb.get_window(seconds=15, asset_id="VFD_VM_01")
    assert isinstance(df, pd.DataFrame)
    assert len(df) >= 14
    # Verify ISA-95 enrichment tags
    assert "PT-30101" in df.columns
    assert "DPS-30101" in df.columns
    assert "VI-301-R" in df.columns
    assert "TI-301-DE" in df.columns
    assert "IT-30101" in df.columns


def test_embedded_tsdb_trip_detection(tmp_path):
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    # Normal packet -> No trip
    assert tsdb.check_trip_trigger({"fault_code": 0}) is None

    # Trip packet -> Triggers code
    assert tsdb.check_trip_trigger({"fault_code": 6}) == 6

    # Immediate duplicate -> Debounced (None)
    assert tsdb.check_trip_trigger({"fault_code": 6}) is None


def test_embedded_tsdb_stats(tmp_path):
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    for i in range(10):
        tsdb.insert({
            "timestamp": time.time(),
            "asset_id": "VFD_VM_01",
            "f_out": 40.0 + i,
            "v_dc": 200.0,
            "current": 1.0,
            "rpm": 1200.0,
            "fault_code": 0,
        })

    stats = tsdb.get_stats(seconds=60)
    assert stats["point_count"] == 10
    assert stats["is_active"] is True
    assert stats["v_dc_avg"] == 200.0


def test_embedded_tsdb_startup_inrush_current_no_trip(tmp_path):
    """
    Verify that motor startup inrush current spikes (e.g. 3.85A exceeding 2.50A trip limit)
    do NOT trigger a false trip when telemetry reports fault_code == 0 (normal startup).
    Only explicit telemetry fault codes (fault_code > 0) must trigger an incident.
    """
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    # 1. Startup inrush packet: current jumps to 3.85 A, fault_code is 0 -> Must NOT trip
    inrush_metric = {
        "fault_code": 0,
        "v_dc": 204.0,
        "current": 3.85,
        "f_out": 25.0,
        "rpm": 750.0,
    }
    assert tsdb.check_trip_trigger(inrush_metric) is None

    # 2. Settled nominal packet: current hovers back to 1.00 A -> Must NOT trip
    running_metric = {
        "fault_code": 0,
        "v_dc": 204.0,
        "current": 1.00,
        "f_out": 40.0,
        "rpm": 1196.0,
    }
    assert tsdb.check_trip_trigger(running_metric) is None

    # 3. Telemetry explicitly reports hardware trip (e.g. Err02, Err06, Err13) -> MUST trip
    trip_metric = {
        "fault_code": 2,
        "v_dc": 204.0,
        "current": 3.20,
        "f_out": 40.0,
        "rpm": 1190.0,
    }
    assert tsdb.check_trip_trigger(trip_metric) == 2


def test_embedded_tsdb_d_trigger_no_trip(tmp_path):
    """Verify that PLC command/trigger registers (d_trigger) do not trigger false hardware trips."""
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    # Motor start command actuated via PLC D-register (d_trigger = 2), but fault_code is 0
    start_metric = {
        "fault_code": 0,
        "d_trigger": 2,
        "current": 2.80,
        "f_out": 20.0,
        "rpm": 600.0,
    }
    assert tsdb.check_trip_trigger(start_metric) is None


def test_embedded_tsdb_nominal_voltage_no_trip(tmp_path):
    """Verify that DC bus voltage variations do not trigger a trip unless telemetry reports an error."""
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    # 1. Steady-state 210.0 V with 1.50 A current (nominal bench) -> Must NOT trip
    nominal_metric = {
        "fault_code": 0,
        "v_dc": 210.0,
        "current": 1.50,
        "f_out": 40.0,
        "rpm": 1196.0,
    }
    assert tsdb.check_trip_trigger(nominal_metric) is None

    # 2. DC bus transient with fault_code 0 -> Must NOT trip
    transient_metric = {
        "fault_code": 0,
        "v_dc": 222.0,
        "current": 1.50,
        "f_out": 48.0,
        "rpm": 1400.0,
    }
    assert tsdb.check_trip_trigger(transient_metric) is None

    # 3. Actual hardware overvoltage trip where telemetry reports fault_code 6 -> MUST trip
    trip_metric = {
        "fault_code": 6,
        "v_dc": 222.0,
        "current": 1.50,
        "f_out": 48.0,
        "rpm": 1400.0,
    }
    assert tsdb.check_trip_trigger(trip_metric) == 6


def test_embedded_tsdb_new_hardware_channels(tmp_path):
    """Verify that new Wecon VM channels (v_out, torque, power, f_in) are stored and retrievable."""
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    metric = {
        "timestamp": time.time(),
        "asset_id": "VFD_VM_01",
        "f_out": 40.0,
        "f_target": 40.0,
        "f_in": 40.0,
        "v_dc": 276.4,
        "v_out": 184.0,
        "current": 0.02,
        "rpm": 1198.0,
        "torque": 2.2,
        "power": 0.0,
        "fault_code": 0,
        "status": "RUNNING",
    }
    tsdb.insert(metric)

    latest = tsdb.get_latest("VFD_VM_01")
    assert latest is not None
    assert latest["f_out"] == 40.0
    assert latest["v_dc"] == 276.4
    assert latest["v_out"] == 184.0
    assert latest["torque"] == 2.2
    assert latest["f_in"] == 40.0


def test_embedded_tsdb_parameters_persistence(tmp_path):
    """Verify storing, retrieving, and auditing VFD control parameters."""
    db_file = tmp_path / "test_tsdb.db"
    tsdb = EmbeddedTSDB(db_path=str(db_file), memory_capacity=100)

    # Set parameters
    tsdb.set_parameter("F0.10", 40.0, "Max Output Frequency")
    tsdb.set_parameter("F0.18", 5.0, "Deceleration Ramp Time")
    tsdb.set_parameter("F2.03", 1.15, "Motor Rated Current")

    params = tsdb.get_parameters()
    assert params["F0.10"]["value"] == 40.0
    assert params["F0.18"]["value"] == 5.0
    assert params["F2.03"]["value"] == 1.15

    # Update F0.18 to trip test ramp (0.2s)
    tsdb.set_parameter("F0.18", 0.2, "Trip Injection Decel")
    updated = tsdb.get_parameters()
    assert updated["F0.18"]["value"] == 0.2
    assert updated["F0.18"]["desc"] == "Trip Injection Decel"



