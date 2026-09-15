"""
Configuration and constants for the Industrial Root Cause Analysis (RCA) System.
Complies with ISA-95 Asset Modeling, ISO 14224 Equipment Taxonomy, and ISO 10816 Vibration Standards.
"""

from pathlib import Path
from typing import Dict, Any

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TOPOLOGY_FILE = DATA_DIR / "asset_topology.json"

# Simulation / Telemetry Parameters
SAMPLING_RATE_HZ = 1.0  # 1 Hz macro time-series
HIGH_FREQ_SAMPLING_RATE_HZ = 20000.0  # 20 kHz vibration waveform snapshot
SIMULATION_DURATION_SEC = 3600  # 60 minutes
SCENARIO_START_TIME = "2026-09-04T02:14:00Z"
TRIP_TIME = "2026-09-04T03:09:00Z"  # T = 3300s (55 min)
TRIP_INDEX = 3300

# Critical Equipment: P-301A (High-Pressure Boiler Feed Pump)
EQUIPMENT_ID = "P-301A"
EQUIPMENT_NAME = "High-Pressure Centrifugal Boiler Feed Pump A"
RATED_SPEED_RPM = 2980.0
RUNNING_FREQUENCY_1X_HZ = RATED_SPEED_RPM / 60.0  # ~49.67 Hz
RUNNING_FREQUENCY_2X_HZ = RUNNING_FREQUENCY_1X_HZ * 2.0  # ~99.33 Hz

# Engineering Operational Limits & Trip Setpoints
OPERATIONAL_LIMITS: Dict[str, Dict[str, Any]] = {
    "PT-30101": {
        "description": "Pump Suction Pressure",
        "unit": "bar",
        "normal_min": 2.30,
        "normal_max": 2.50,
        "npsh_r": 1.20,
        "trip_min": 1.20,  # Below NPSHr triggers cavitation alarm/trip
    },
    "DPS-30101": {
        "description": "Suction Strainer Differential Pressure",
        "unit": "bar",
        "normal_min": 0.05,
        "normal_max": 0.25,
        "alarm_high": 1.00,
        "trip_high": 1.80,
    },
    "VI-301-R": {
        "description": "Radial Overall Vibration RMS (ISO 10816)",
        "unit": "mm/s RMS",
        "normal_typical": 1.80,
        "zone_c_alarm": 4.50,  # ISO 10816 Class III Zone C (Unrestricted long-term operation not permitted)
        "zone_d_trip": 7.10,   # ISO 10816 Class III Zone D (Vibration causes damage)
    },
    "TI-301-DE": {
        "description": "Drive-End Bearing Temperature",
        "unit": "deg C",
        "normal_typical": 48.5,
        "alarm_high": 80.0,
        "trip_high": 90.0,
    },
    "IT-30101": {
        "description": "Drive Motor Line Current",
        "unit": "A",
        "normal_typical": 84.2,
        "rated_fla": 115.0,  # Full Load Amperes
        "instability_pct_threshold": 0.15,  # +/-15% fluctuation indicates two-phase cavitation load
    },
}

# Spectral Cavitation Detection Parameters
CAVITATION_BROADBAND_BAND_HZ = (2000.0, 8000.0)  # 2 kHz to 8 kHz high-frequency noise floor
CAVITATION_ENERGY_RATIO_ALARM = 0.35  # If >35% spectral energy is broadband, cavitation is present

# Cache Settings
CACHE_MAX_ENTRIES = 256

# Checkpointer Thread ID Default
DEFAULT_THREAD_ID = "rca-session-p301a-001"

# InfluxDB 2.0 Live Telemetry Configuration
INFLUXDB_URL = "http://127.0.0.1:8086"
INFLUXDB_ORG = "factory"
INFLUXDB_BUCKET = "telemetry"
INFLUXDB_TOKEN = "rca_super_secret_token_123"
INFLUXDB_MEASUREMENT = "vfd_telemetry"

# Hardware-in-the-Loop VFD Specifications & Operational Limits
VFD_EQUIPMENT_ID = "VFD_VM_01"
VFD_OPERATIONAL_LIMITS: Dict[str, Dict[str, Any]] = {
    "f_out": {
        "description": "VFD Output Frequency",
        "unit": "Hz",
        "normal_min": 0.0,
        "normal_max": 40.0,
        "rated_max": 50.0,
        "alarm_high": 42.0,
        "trip_high": 50.0,
    },
    "v_dc": {
        "description": "DC Bus Voltage",
        "unit": "V",
        "normal_min": 280.0,
        "normal_max": 380.0,
        "alarm_high": 650.0,
        "trip_high": 700.0,
    },
    "current": {
        "description": "Motor Line / Output Current",
        "unit": "A",
        "normal_min": 0.0,
        "normal_max": 1.50,
        "alarm_high": 2.00,
        "trip_high": 2.50,
    },
    "rpm": {
        "description": "Motor Speed",
        "unit": "RPM",
        "normal_min": 0.0,
        "normal_max": 1450.0,
        "trip_high": 1750.0,
    },
    "v_out": {
        "description": "Output Voltage",
        "unit": "V",
        "normal_min": 0.0,
        "normal_max": 220.0,
        "trip_high": 250.0,
    },
}
