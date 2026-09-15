"""
OEM Equipment Manuals, Operational Limits, and ISO 14224/FMEA Reference Standards.
Provides deterministic engineering thresholds and failure mode classification data.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass(frozen=True)
class EquipmentSpec:
    asset_id: str
    asset_name: str
    manufacturer: str
    model: str
    equipment_class_iso14224: str
    rated_speed_rpm: float
    running_frequency_1x_hz: float
    running_frequency_2x_hz: float
    rated_power_kw: float
    rated_voltage_v: float
    rated_current_a: float
    dc_bus_nominal_v: float
    dc_bus_trip_v: float
    max_operating_freq_hz: float


WECON_VM_VFD_SPEC_DATA = EquipmentSpec(
    asset_id="VFD_VM_01",
    asset_name="Wecon VM Series Variable Frequency Drive",
    manufacturer="WECON Technology Co., Ltd.",
    model="VM-0R7G-2 (Single-Phase 220V 0.75kW)",
    equipment_class_iso14224="Variable Frequency Drive / Inverter (EC: DR-VFD)",
    rated_speed_rpm=1440.0,
    running_frequency_1x_hz=40.0,
    running_frequency_2x_hz=80.0,
    rated_power_kw=0.75,
    rated_voltage_v=220.0,
    rated_current_a=2.50,
    dc_bus_nominal_v=182.0,
    dc_bus_trip_v=195.0,
    max_operating_freq_hz=40.0,
)

OEM_PUMP_SPEC = WECON_VM_VFD_SPEC_DATA


# ISO 14224 Failure Taxonomy for VFD Drives & Induction Motors
ISO_14224_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "VFD_DECEL_OVERVOLTAGE": {
        "failure_mode": "VLT (Overvoltage / DC bus surge)",
        "failure_mechanism": "Overfrequency excursion / Regenerative kinetic energy without braking resistor",
        "detection_method": "DC bus voltage surge (Reg 3004H > 195.0V) and VFD Trip Code 6 (Err06)",
        "iso_code": "ISO-14224-DR-ELC-OVV",
    },
    "VFD_ACCEL_OVERCURRENT": {
        "failure_mode": "CUR (Instantaneous overcurrent / Forced sudden stop current spike)",
        "failure_mechanism": "Forced sudden deceleration via PLC On/Off button / lack of controlled ramp",
        "detection_method": "Output current surge (Reg 3002H) upon stop command and VFD Trip Code 2 (Err02)",
        "iso_code": "ISO-14224-DR-ELC-OCI",
    },
    "VFD_DECEL_OVERCURRENT": {
        "failure_mode": "CUR (Instantaneous overcurrent during deceleration)",
        "failure_mechanism": "Deceleration time too short under high inertial load without dynamic braking",
        "detection_method": "Output current surge (Reg 3002H) during ramp-down and VFD Trip Code 3 (Err03)",
        "iso_code": "ISO-14224-DR-ELC-OCD",
    },
    "VFD_MOTOR_OVERLOAD": {
        "failure_mode": "OHT (Motor thermal overload / I2t protection trip)",
        "failure_mechanism": "Motor continuous line current exceeding parameter F2.03 threshold / mechanical binding",
        "detection_method": "Current elevation (Reg 3002H) exceeding rated current over time and VFD Trip Code 11 (Err11)",
        "iso_code": "ISO-14224-DR-ELC-THO",
    },
    "VFD_PHASE_LOSS": {
        "failure_mode": "PHS (Output phase disconnection / imbalance)",
        "failure_mechanism": "U/V/W terminal loose connection or motor lead fault",
        "detection_method": "Output phase current imbalance and VFD Trip Code 16 (Err16)",
        "iso_code": "ISO-14224-DR-ELC-PHS",
    },
}


# FMEA (Failure Mode and Effects Analysis) Reference Matrix for VFD Test Rig
FMEA_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "hypothesis_id": "H_VFD_ERR02",
        "name": "Forced Sudden Deceleration Overcurrent (WECON VM Err02)",
        "failure_mode": "Instantaneous current surge upon forced stop command via PLC On/Off button",
        "potential_causes": [
            "Operator toggled PLC On/Off stop button (D variable trigger) without controlled ramp",
            "Deceleration ramp time F0.18 set to instantaneous stop",
            "Dynamic braking resistor missing from terminals P+ and PB",
        ],
        "effects": "Drive trip Err02, instantaneous IGBT shutdown, motor deactivation",
        "severity": 7,
        "occurrence": 5,
        "detection": 1,
        "rpn": 35,
        "falsification_checks": [
            "Verify PLC On/Off stop trigger was actuated",
            "Verify output current Reg 3002H spiked past trip threshold",
            "Verify fault code Reg 700BH reported 2 (Err02)",
            "Inspect parameter F0.18 deceleration time setting",
        ],
    },
    {
        "hypothesis_id": "H_VFD_ERR06",
        "name": "Overfrequency Deceleration Overvoltage (WECON VM Err06)",
        "failure_mode": "DC link overvoltage trip when frequency exceeds 40 Hz ceiling toward 50 Hz",
        "potential_causes": [
            "Output frequency setpoint raised past 40.00 Hz operational ceiling",
            "DC bus voltage exceeded calibrated 195.0 V protection threshold (reaching ~207V)",
            "Dynamic braking resistor missing or open-circuit on terminals P+ and PB",
        ],
        "effects": "Drive trip Err06, DC bus voltage > 195V, motor deactivation",
        "severity": 8,
        "occurrence": 4,
        "detection": 1,
        "rpn": 32,
        "falsification_checks": [
            "Verify output frequency Reg 3000H exceeded 40.00 Hz limit",
            "Verify DC bus voltage Reg 3004H breached 195.0 V trip limit",
            "Verify fault code Reg 700BH reported 6 (Err06)",
            "Check parameter F0.10 maximum frequency clamp",
        ],
    },
    {
        "hypothesis_id": "H_VFD_ERR03",
        "name": "Deceleration Overcurrent (WECON VM Err03)",
        "failure_mode": "Overcurrent trip during motor deceleration ramp-down",
        "potential_causes": [
            "Deceleration time F0.18 set too steep for load inertia",
            "Mechanical brake engaged prematurely during electrical decel",
        ],
        "effects": "Drive trip Err03, motor deactivation",
        "severity": 7,
        "occurrence": 3,
        "detection": 2,
        "rpn": 42,
        "falsification_checks": [
            "Verify deceleration command was active",
            "Verify fault code Reg 700BH reported 3 (Err03)",
        ],
    },
    {
        "hypothesis_id": "H_VFD_ERR11",
        "name": "Motor Thermal Overload (WECON VM Err11)",
        "failure_mode": "Inverter electronic thermal overload protection trip (I2t)",
        "potential_causes": [
            "Motor continuous operating current exceeded rated parameter F2.03 threshold",
            "Mechanical binding, misalignment, or excessive load on induction motor",
            "Low motor speed prolonged operation with insufficient cooling fan airflow",
        ],
        "effects": "Drive trip Err11, motor shutdown, winding thermal accumulation",
        "severity": 8,
        "occurrence": 4,
        "detection": 2,
        "rpn": 64,
        "falsification_checks": [
            "Verify output current Reg 3002H exceeded F2.03 setting continuously",
            "Verify fault code Reg 700BH reported 11 (Err11)",
            "Inspect motor shaft free rotation and load mechanical binding",
        ],
    },
]


# WECON VM Series VFD Specifications & Modbus Registers
WECON_VM_VFD_SPEC: Dict[str, Any] = {
    "asset_id": "VFD_VM_01",
    "asset_name": "WECON VM Series Variable Frequency Drive",
    "manufacturer": "WECON Technology Co., Ltd.",
    "model": "VM-0R7G-2 (Single-Phase 220V 0.75kW)",
    "equipment_class_iso14224": "Variable Frequency Drive / Inverter (EC: DR-VFD)",
    "modbus_comm": {
        "slave_id": 1,
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": "None",
        "stop_bits": 1,
        "function_code_read": 3,
        "function_code_write": 6,
    },
    "registers": {
        # ── 1000H Monitoring Group (OEM Manual Specification) ──
        "1001H": {"dec": 4097, "name": "Running Frequency", "unit": "Hz", "scale": 0.01, "access": "RO"},
        "1002H": {"dec": 4098, "name": "Set Frequency", "unit": "Hz", "scale": 0.01, "access": "RO"},
        "1003H": {"dec": 4099, "name": "Bus Voltage (DC)", "unit": "V", "scale": 0.1, "access": "RO"},
        "1004H": {"dec": 4100, "name": "Output Voltage", "unit": "V", "scale": 0.1, "access": "RO"},
        "1005H": {"dec": 4101, "name": "Output Current", "unit": "A", "scale": 0.01, "access": "RO"},
        "1008H": {"dec": 4104, "name": "DI Input Status", "unit": "bitmask", "scale": 1, "access": "RO"},
        "100AH": {"dec": 4106, "name": "AI Input Voltage", "unit": "V", "scale": 0.1, "access": "RO"},
        "100CH": {"dec": 4108, "name": "Keypad Potentiometer Voltage", "unit": "V", "scale": 0.1, "access": "RO"},
        "100DH": {"dec": 4109, "name": "IGBT Temperature", "unit": "C", "scale": 0.1, "access": "RO"},
        "100FH": {"dec": 4111, "name": "Motor RPM", "unit": "RPM", "scale": 0.1, "access": "RO"},
        "1012H": {"dec": 4114, "name": "PLC Stage", "unit": "stage", "scale": 1, "access": "RO"},
        # ── 3000H / 2000H Control & Legacy Aliases ──
        "3000H": {"dec": 12288, "name": "Output Frequency", "unit": "Hz", "scale": 0.01, "access": "RO"},
        "3001H": {"dec": 12289, "name": "Target Set Frequency", "unit": "Hz", "scale": 0.01, "access": "RO"},
        "3002H": {"dec": 12290, "name": "Output Current", "unit": "A", "scale": 0.01, "access": "RO"},
        "3003H": {"dec": 12291, "name": "Output Voltage", "unit": "V", "scale": 1.0, "access": "RO"},
        "3004H": {"dec": 12292, "name": "DC Bus Voltage", "unit": "V", "scale": 0.1, "access": "RO"},
        "700BH": {"dec": 28683, "name": "Active Trip Fault Code", "unit": "code", "scale": 1, "access": "RO"},
        "2000H": {"dec": 8192, "name": "Control Command", "unit": "enum", "scale": 1, "access": "WO"},
        "2001H": {"dec": 8193, "name": "Frequency Command", "unit": "Hz", "scale": 0.01, "access": "RW"},
    },
    "control_parameters": {
        "F0.02": {"name": "Run Command Source", "setting": 2, "desc": "RS-485 Communication"},
        "F0.03": {"name": "Frequency Reference Source", "setting": 2, "desc": "RS-485 Communication"},
        "F0.10": {"name": "Max Operating Frequency", "default_hz": 40.0},
        "F0.17": {"name": "Acceleration Time", "default_s": 5.0},
        "F0.18": {"name": "Deceleration Time", "default_s": 5.0, "trip_injection_s": 0.1},
        "F2.03": {"name": "Motor Rated Current", "default_a": 1.15, "trip_injection_a": 0.3},
        "F9.00": {"name": "Slave Address", "setting": 1},
        "F9.01": {"name": "Baud Rate", "setting": 3, "desc": "9600 bps"},
        "F9.02": {"name": "Data Format", "setting": 0, "desc": "8-N-1"},
    },
    "fault_codes": {
        0: "Normal Operation (No Active Fault)",
        2: "Forced Decel Overcurrent (Err02)",
        3: "Deceleration Overcurrent (Err03)",
        6: "Overfrequency Overvoltage (Err06)",
        11: "Motor Thermal Overload (Err11)",
        16: "Output Phase Loss (Err16)",
    },
    "dc_bus_nominal_v": 182.0,
    "dc_bus_overvoltage_threshold_v": 195.0,
}


def get_oem_spec(asset_id: str = "VFD_VM_01") -> Any:
    """Retrieve OEM specifications for the specified asset."""
    if asset_id in ("VFD_VM_01", "VFD", "P-301A"):
        return WECON_VM_VFD_SPEC
    raise ValueError(f"Unknown asset_id: {asset_id}. Currently supported: VFD_VM_01")


def get_vfd_spec() -> Dict[str, Any]:
    """Retrieve WECON VM Series VFD specification and register map."""
    return WECON_VM_VFD_SPEC


def get_vfd_fault_info(fault_code: int) -> Dict[str, Any]:
    """Retrieve description and failure taxonomy for a VFD fault code."""
    desc = WECON_VM_VFD_SPEC["fault_codes"].get(fault_code, f"Unknown Fault (Code {fault_code})")
    iso_map = {
        2: ISO_14224_TAXONOMY.get("VFD_ACCEL_OVERCURRENT", {}),
        3: ISO_14224_TAXONOMY.get("VFD_DECEL_OVERCURRENT", {}),
        6: ISO_14224_TAXONOMY.get("VFD_DECEL_OVERVOLTAGE", {}),
        11: ISO_14224_TAXONOMY.get("VFD_MOTOR_OVERLOAD", {}),
        16: ISO_14224_TAXONOMY.get("VFD_PHASE_LOSS", {}),
    }
    return {
        "fault_code": fault_code,
        "description": desc,
        "iso_info": iso_map.get(fault_code, {}),
    }


def get_fmea_entry(hypothesis_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve FMEA matrix entry for a hypothesis ID."""
    for entry in FMEA_KNOWLEDGE_BASE:
        if entry["hypothesis_id"] == hypothesis_id:
            return entry
    return None


