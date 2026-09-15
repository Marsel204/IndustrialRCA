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
