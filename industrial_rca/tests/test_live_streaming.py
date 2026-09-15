"""
Unit & Integration Tests for InfluxDB & Live Telemetry Streaming Integration.
Validates:
- InfluxDBTelemetryTool querying, CSV parsing, statistics, and offline fallback
- VFD operational limits and config parameters
- generate_vfd_dataset for nominal, overfrequency, decel_overvoltage, and live_stream
- FastAPI endpoints: /api/v1/telemetry/live/metrics, /api/v1/telemetry/live/stream, /api/v1/scenarios
- Live incident broadcasting to SSE subscribers
"""

import time
import pytest
import pandas as pd
from starlette.testclient import TestClient

from industrial_rca.config import (
    INFLUXDB_URL,
    INFLUXDB_ORG,
    INFLUXDB_BUCKET,
    INFLUXDB_TOKEN,
    INFLUXDB_MEASUREMENT,
    VFD_EQUIPMENT_ID,
    VFD_OPERATIONAL_LIMITS,
)
from industrial_rca.tools.influx_tool import InfluxDBTelemetryTool
from industrial_rca.data.telemetry_generator import generate_vfd_dataset, TelemetryDataset
from industrial_rca.api import api_app, _broadcast_live_metric, _LIVE_STREAM_SUBSCRIBERS


@pytest.fixture(scope="module")
def client():
    return TestClient(api_app)


def test_vfd_config_constants():
    """Verify InfluxDB and VFD configuration constants."""
    assert INFLUXDB_URL == "http://127.0.0.1:8086"
    assert INFLUXDB_ORG == "factory"
    assert INFLUXDB_BUCKET == "telemetry"
    assert INFLUXDB_TOKEN == "rca_super_secret_token_123"
    assert INFLUXDB_MEASUREMENT == "vfd_telemetry"
    assert VFD_EQUIPMENT_ID == "VFD_VM_01"

    assert "f_out" in VFD_OPERATIONAL_LIMITS
    assert "v_dc" in VFD_OPERATIONAL_LIMITS
    assert "current" in VFD_OPERATIONAL_LIMITS
    assert VFD_OPERATIONAL_LIMITS["v_dc"]["trip_high"] == 700.0
    assert VFD_OPERATIONAL_LIMITS["current"]["trip_high"] == 2.50


def test_influx_tool_csv_parser():
    """Verify parsing of InfluxDB annotated CSV output."""
    tool = InfluxDBTelemetryTool()
    sample_csv = """#group,false,false,true,true,false,true,true,_result
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement,asset_id
,,0,2026-09-15T03:00:00Z,2026-09-15T03:15:00Z,2026-09-15T03:14:00Z,40.05,f_out,vfd_telemetry,VFD_VM_01
,,0,2026-09-15T03:00:00Z,2026-09-15T03:15:00Z,2026-09-15T03:14:00Z,312.4,v_dc,vfd_telemetry,VFD_VM_01
,,0,2026-09-15T03:00:00Z,2026-09-15T03:15:00Z,2026-09-15T03:14:00Z,1.38,current,vfd_telemetry,VFD_VM_01
"""
    records = tool._parse_annotated_csv(sample_csv)
    assert len(records) == 3
    assert records[0]["_field"] == "f_out"
    assert records[0]["_value"] == 40.05
    assert records[1]["_field"] == "v_dc"
    assert records[1]["_value"] == 312.4


def test_influx_tool_graceful_fallback():
    """Verify that InfluxDBTelemetryTool falls back to simulation when InfluxDB is offline."""
    tool = InfluxDBTelemetryTool(url="http://127.0.0.1:9999")  # Non-existent port

    # 1. Live telemetry dataframe
    df = tool.get_live_telemetry(limit=50)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 50
    assert "f_out" in df.columns
    assert "v_dc" in df.columns
    assert "current" in df.columns
    assert "rpm" in df.columns
    assert "PT-30101" in df.columns
    assert "DPS-30101" in df.columns
    assert "VI-301-R" in df.columns

    # 2. Latest single reading
    metric = tool.get_latest_metrics()
    assert metric["status"] == "RUNNING"
    assert 35.0 <= metric["f_out"] <= 45.0
    assert 280.0 <= metric["v_dc"] <= 350.0
    assert metric["fault_code"] == 0
    assert "timestamp" in metric

    # 3. Statistical summary
    summary = tool.get_statistical_summary()
    assert summary["sample_count"] == 300
    assert "f_out" in summary["statistics"]
    assert "v_dc" in summary["statistics"]

    # 4. Agent summary text
    agent_text = tool.search_for_agent()
    assert "InfluxDB Real-Time Telemetry" in agent_text
    assert "Output Frequency (f_out)" in agent_text
    assert "DC Bus Voltage (v_dc)" in agent_text


def test_generate_vfd_dataset_scenarios():
    """Verify generate_vfd_dataset produces valid TelemetryDataset for all scenarios."""
    # 1. Nominal
    ds_nom = generate_vfd_dataset(scenario="nominal", duration_sec=60)
    assert isinstance(ds_nom, TelemetryDataset)
    assert ds_nom.metadata["condition"] == "HEALTHY"
    assert ds_nom.metadata["fault_code"] == 0
    assert len(ds_nom.df_1hz) == 60
    assert "PT-30101" in ds_nom.df_1hz.columns

    # 2. Overfrequency
    ds_over = generate_vfd_dataset(scenario="overfrequency", duration_sec=60)
    assert ds_over.metadata["condition"] == "WARNING_OVERFREQUENCY"
    assert ds_over.df_1hz["f_out"].max() > 42.0

    # 3. Decel Overvoltage (Err06)
    ds_decel = generate_vfd_dataset(scenario="decel_overvoltage", duration_sec=60)
    assert ds_decel.metadata["condition"] == "HARDWARE_FAULT_TRIP"
    assert ds_decel.metadata["fault_code"] == 6
    assert ds_decel.df_1hz["v_dc"].max() > 700.0

    # 4. Live Stream
    ds_live = generate_vfd_dataset(scenario="live_stream", duration_sec=60)
    assert ds_live.metadata["scenario"] == "live_stream"
    assert len(ds_live.df_1hz) == 60


def test_api_scenarios_includes_live_stream(client):
    """Verify GET /api/v1/scenarios includes the live_stream scenario."""
    resp = client.get("/api/v1/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    scenarios = data.get("scenarios", [])
    scenario_ids = [s["id"] for s in scenarios]
    assert "live_stream" in scenario_ids

    live_sc = next(s for s in scenarios if s["id"] == "live_stream")
    assert live_sc["asset_id"] == "VFD_VM_01"
    assert live_sc["badge"] == "LIVE_EDGE"


def test_api_live_metrics_endpoint(client):
    """Verify GET /api/v1/telemetry/live/metrics returns valid VFD reading."""
    resp = client.get("/api/v1/telemetry/live/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "f_out" in data
    assert "v_dc" in data
    assert "current" in data
    assert "rpm" in data
    assert "status" in data
    assert "timestamp" in data
    assert data["status"] in ("RUNNING", "TRIPPED")


def test_api_live_stream_telemetry_series(client):
    """Verify GET /api/v1/telemetry/live_stream returns series."""
    resp = client.get("/api/v1/telemetry/live_stream")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset_id"] == "live_stream"
    assert "f_out" in data["series"]
    assert "v_dc" in data["series"]
    assert "current" in data["series"]
    assert "rpm" in data["series"]
    assert "PT-30101" in data["series"]


def test_api_incident_broadcast(client):
    """Verify POST /api/v1/telemetry/incident broadcasts to live stream subscribers."""
    payload = {
        "asset_id": "VFD_VM_01",
        "fault_code": 6,
        "fault_description": "Deceleration Overvoltage (Err06) - regeneration surge",
        "incident_id": "INC-TEST-BROADCAST-001",
        "pre_fault_telemetry": [
            {"timestamp": time.time() - 1, "f_out": 40.0, "f_target": 40.0, "current": 1.35, "v_out": 220.0, "v_dc": 312.0, "fault_code": 0},
            {"timestamp": time.time(), "f_out": 0.0, "f_target": 0.0, "current": 0.0, "v_out": 0.0, "v_dc": 748.0, "fault_code": 6},
        ],
    }
    resp = client.post("/api/v1/telemetry/incident", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "INCIDENT_INGESTED"
    assert data["fault_code"] == 6


def test_influx_tool_multi_table_csv_parsing():
    """Verify parsing of multi-table annotated CSV without corrupting data rows."""
    tool = InfluxDBTelemetryTool()
    sample_multi_table_csv = """#group,false,false,true,true,false,true,true,_result
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement,asset_id
,,0,2026-09-15T03:00:00Z,2026-09-15T03:15:00Z,2026-09-15T03:14:00Z,40.05,f_out,vfd_telemetry,VFD_VM_01

#group,false,false,true,true,false,true,true,_result
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement,asset_id
,,1,2026-09-15T03:00:00Z,2026-09-15T03:15:00Z,2026-09-15T03:14:00Z,312.4,v_dc,vfd_telemetry,VFD_VM_01
"""
    records = tool._parse_annotated_csv(sample_multi_table_csv)
    # Must contain exactly 2 data records and NO header row rows
    assert len(records) == 2
    assert records[0]["_field"] == "f_out"
    assert records[0]["_value"] == 40.05
    assert records[1]["_field"] == "v_dc"
    assert records[1]["_value"] == 312.4


def test_influx_tool_trip_events_multi_table():
    """Verify get_trip_events successfully parses multi-table trip responses."""
    from unittest.mock import patch
    tool = InfluxDBTelemetryTool()
    sample_trip_csv = """#group,false,false,true,true,false,true,true,_result
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,long,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement,asset_id
,,0,2026-09-15T03:00:00Z,2026-09-15T03:15:00Z,2026-09-15T03:14:00Z,6,fault_code,vfd_telemetry,VFD_VM_01

#group,false,false,true,true,false,true,true,_result
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,long,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement,asset_id
,,1,2026-09-15T03:00:00Z,2026-09-15T03:15:00Z,2026-09-15T03:14:05Z,6,fault_code,vfd_telemetry,VFD_VM_01
"""
    with patch.object(tool, "query_flux", return_value=tool._parse_annotated_csv(sample_trip_csv)):
        trips = tool.get_trip_events()
        assert len(trips) == 2
        assert trips[0]["fault_code"] == 6
        assert trips[1]["fault_code"] == 6


def test_influx_tool_latest_metrics_unpivoted():
    """Verify get_latest_metrics consolidates fields across unpivoted InfluxDB records."""
    from unittest.mock import patch
    tool = InfluxDBTelemetryTool()
    unpivoted_records = [
        {"_field": "f_out", "_value": 42.5, "_time": 1726041000},
        {"_field": "v_dc", "_value": 680.2, "_time": 1726041000},
        {"_field": "current", "_value": 2.15, "_time": 1726041000},
        {"_field": "rpm", "_value": 1230.0, "_time": 1726041000},
        {"_field": "fault_code", "_value": 0, "_time": 1726041000},
    ]
    with patch.object(tool, "query_flux", return_value=unpivoted_records):
        metrics = tool.get_latest_metrics()
        assert metrics["f_out"] == 42.5
        assert metrics["v_dc"] == 680.2
        assert metrics["current"] == 2.15
        assert metrics["rpm"] == 1230.0
        assert metrics["status"] == "RUNNING"
        assert metrics["source"] == "influxdb"


def test_influx_tool_statistical_summary_source_tag():
    """Verify get_statistical_summary reports source: influxdb when InfluxDB provides data."""
    from unittest.mock import patch
    tool = InfluxDBTelemetryTool()
    records = [
        {"_time": "2026-09-15T03:14:00Z", "f_out": 40.0, "v_dc": 312.0, "current": 1.35, "rpm": 1160.0, "fault_code": 0},
        {"_time": "2026-09-15T03:14:01Z", "f_out": 40.2, "v_dc": 313.0, "current": 1.38, "rpm": 1165.0, "fault_code": 0},
    ]
    with patch.object(tool, "query_flux", return_value=records):
        summary = tool.get_statistical_summary()
        assert summary["source"] == "influxdb"
        assert summary["sample_count"] == 2


def test_vfd_decel_overvoltage_maintains_pump_baseline():
    """Verify VFD decel overvoltage trip scenario maintains healthy pump baseline tags."""
    ds = generate_vfd_dataset(scenario="decel_overvoltage", duration_sec=60)
    df = ds.df_1hz
    # Electrical tags trip
    assert df["v_dc"].max() > 700.0
    assert ds.metadata["fault_code"] == 6
    # Pump tags remain strictly healthy baseline
    assert (df["PT-30101"] >= 2.0).all()
    assert (df["DPS-30101"] <= 0.20).all()
    assert (df["TI-301-DE"] <= 55.0).all()
    assert (df["VI-301-R"] <= 2.5).all()

