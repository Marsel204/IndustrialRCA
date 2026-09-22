"""
Configuration and constants for the Industrial Root Cause Analysis (RCA) System.
Complies with ISA-95 Asset Modeling, ISO 14224 Equipment Taxonomy, and ISO 10816 Vibration Standards.
"""

import os
from pathlib import Path
from typing import Dict, Any

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env"
DATA_DIR = BASE_DIR / "data"
TOPOLOGY_FILE = DATA_DIR / "asset_topology.json"

# Automatically load environment variables from root .env
try:
    import dotenv
    if ENV_FILE.exists():
        dotenv.load_dotenv(ENV_FILE, override=False)
except ImportError:
    pass

# Simulation / Telemetry Parameters
SAMPLING_RATE_HZ = 1.0  # 1 Hz macro time-series
HIGH_FREQ_SAMPLING_RATE_HZ = 20000.0  # 20 kHz vibration waveform snapshot
SIMULATION_DURATION_SEC = 3600  # 60 minutes
SCENARIO_START_TIME = "2026-09-04T02:14:00Z"
TRIP_TIME = "2026-09-04T03:09:00Z"  # T = 3300s (55 min)
TRIP_INDEX = 3300

# Critical Equipment: VFD_VM_01 (Wecon VM Inverter & Induction Motor)
EQUIPMENT_ID = "VFD_VM_01"
EQUIPMENT_NAME = "Wecon VM Series Variable Frequency Drive & Induction Motor Test Bench"
RATED_SPEED_RPM = 1440.0
RUNNING_FREQUENCY_1X_HZ = 40.0  # 40.0 Hz nominal setpoint
RUNNING_FREQUENCY_2X_HZ = 80.0

# Engineering Operational Limits & Trip Setpoints (Calibrated for 220V Hardware Bench)
OPERATIONAL_LIMITS: Dict[str, Dict[str, Any]] = {
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
        "normal_min": 170.0,
        "normal_max": 188.0,
        "nominal_40hz": 182.0,
        "alarm_high": 190.0,
        "trip_high": 195.0,  # Calibrated hardware trip threshold (>195V trips Err06 consistently)
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
        "normal_max": 1250.0,
        "nominal_40hz": 1199.0,
        "trip_high": 1500.0,
    },
    "v_out": {
        "description": "Output Voltage",
        "unit": "V",
        "normal_min": 0.0,
        "normal_max": 220.0,
        "trip_high": 250.0,
    },
    "fault_code": {
        "description": "Active Trip Fault Code",
        "unit": "code",
        "normal_typical": 0,
        "trip_min": 1,
    },
}

# Cache Settings
CACHE_MAX_ENTRIES = 256

# Auxiliary Spectral Constants (Compatibility)
CAVITATION_BROADBAND_BAND_HZ = (2000.0, 8000.0)
CAVITATION_ENERGY_RATIO_ALARM = 0.25

# Checkpointer Thread ID Default
DEFAULT_THREAD_ID = "rca-session-vfd-001"

# InfluxDB 2.0 Live Telemetry Configuration
INFLUXDB_URL = "http://127.0.0.1:8086"
INFLUXDB_ORG = "factory"
INFLUXDB_BUCKET = "telemetry"
INFLUXDB_TOKEN = "rca_super_secret_token_123"
INFLUXDB_MEASUREMENT = "vfd_telemetry"

# Hardware-in-the-Loop VFD Specifications & Operational Limits Alias
VFD_EQUIPMENT_ID = EQUIPMENT_ID
VFD_OPERATIONAL_LIMITS = OPERATIONAL_LIMITS

# Telegram Bot & Alert Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_POLLING_INTERVAL = float(os.getenv("TELEGRAM_POLLING_INTERVAL", "1.0"))
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5173")

