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
    npsh_required_bar: float
    normal_suction_pressure_bar: tuple[float, float]
    normal_discharge_pressure_bar: tuple[float, float]
    bearing_temp_alarm_c: float
    bearing_temp_trip_c: float
    vibration_alarm_rms_mms: float
    vibration_trip_rms_mms: float
    strainer_clean_dp_bar: float
    strainer_alarm_dp_bar: float
    strainer_trip_dp_bar: float
    lube_oil_type: str
    lube_oil_normal_temp_c: tuple[float, float]


OEM_PUMP_SPEC = EquipmentSpec(
    asset_id="P-301A",
    asset_name="High-Pressure Centrifugal Boiler Feed Pump A",
    manufacturer="Sulzer Pumps Ltd",
    model="GSG 150-360 6-Stage High Pressure Feed Pump",
    equipment_class_iso14224="Centrifugal Pump (EC: PU-CE)",
    rated_speed_rpm=2980.0,
    running_frequency_1x_hz=2980.0 / 60.0,  # 49.667 Hz
    running_frequency_2x_hz=(2980.0 / 60.0) * 2.0,  # 99.333 Hz
    npsh_required_bar=1.20,
    normal_suction_pressure_bar=(2.30, 2.50),
    normal_discharge_pressure_bar=(62.0, 65.0),
    bearing_temp_alarm_c=80.0,
    bearing_temp_trip_c=90.0,
    vibration_alarm_rms_mms=4.50,  # ISO 10816 Class III Zone C
    vibration_trip_rms_mms=7.10,   # ISO 10816 Class III Zone D (Trip)
    strainer_clean_dp_bar=0.12,
    strainer_alarm_dp_bar=1.00,
    strainer_trip_dp_bar=1.80,
    lube_oil_type="ISO VG 46 Turbine Oil",
    lube_oil_normal_temp_c=(40.0, 55.0),
)


# ISO 14224 Failure Taxonomy for Centrifugal Pumps
ISO_14224_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "CAVITATION": {
        "failure_mode": "FTO (Fail to operate / output low) / VIB (High vibration)",
        "failure_mechanism": "Cavitation erosion / Hydraulic instability / Flow starvation",
        "detection_method": "Acoustic / High-Frequency Broadband Vibration (>2kHz) & Suction Depression",
        "iso_code": "ISO-14224-PU-HYD-CAV",
    },
    "LUBRICATION_FAILURE": {
        "failure_mode": "OHT (Overheating) / BRG (Bearing degradation)",
        "failure_mechanism": "Oil film breakdown / Thermal runaway / Lubricant starvation",
        "detection_method": "Bearing temperature progressive rise without upstream hydraulic anomaly",
        "iso_code": "ISO-14224-PU-MEC-LUB",
    },
    "ELECTRICAL_OVERLOAD": {
        "failure_mode": "ELC (Electrical failure) / BRK (Motor circuit trip)",
        "failure_mechanism": "Winding insulation breakdown / Phase imbalance / Stator core saturation",
        "detection_method": "Steady symmetrical/asymmetrical line current elevation exceeding FLA without fluid pulsation",
        "iso_code": "ISO-14224-DR-ELC-OVL",
    },
    "STRAINER_FOULING": {
        "failure_mode": "RES (Fluid restriction) / BLK (Blockage)",
        "failure_mechanism": "Particulate accumulation / Foreign object obstruction / Biofouling",
        "detection_method": "Differential pressure transmitter spike (DPS > 1.0 bar)",
        "iso_code": "ISO-14224-STR-PRC-BLK",
    },
    "VFD_DECEL_OVERVOLTAGE": {
        "failure_mode": "VLT (Overvoltage / DC bus surge)",
        "failure_mechanism": "Regenerative kinetic energy without dynamic braking resistor / decel ramp too steep",
        "detection_method": "DC bus voltage surge (Reg 3004H > 700V) and VFD Trip Code 6 (Err06)",
        "iso_code": "ISO-14224-DR-ELC-OVV",
    },
    "VFD_MOTOR_OVERLOAD": {
        "failure_mode": "OHT (Motor thermal overload / I2t protection trip)",
        "failure_mechanism": "Motor continuous line current exceeding parameter F2.03 threshold / mechanical binding",
        "detection_method": "Current elevation (Reg 3002H) exceeding rated current over time and VFD Trip Code 11 (Err11)",
        "iso_code": "ISO-14224-DR-ELC-THO",
    },
    "VFD_ACCEL_OVERCURRENT": {
        "failure_mode": "CUR (Instantaneous overcurrent during acceleration)",
        "failure_mechanism": "Acceleration time too short (F0.17) / locked rotor / stator phase short-circuit",
        "detection_method": "Output current surge (Reg 3002H) during ramp-up and VFD Trip Code 2 (Err02)",
        "iso_code": "ISO-14224-DR-ELC-OCI",
    },
    "VFD_DECEL_OVERCURRENT": {
        "failure_mode": "CUR (Instantaneous overcurrent during deceleration)",
        "failure_mechanism": "Deceleration time too short (F0.18) under high inertial load without dynamic braking",
        "detection_method": "Output current surge (Reg 3002H) during ramp-down and VFD Trip Code 3 (Err03)",
        "iso_code": "ISO-14224-DR-ELC-OCD",
    },
}


# FMEA (Failure Mode and Effects Analysis) Reference Matrix
FMEA_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "hypothesis_id": "H1",
        "name": "Drive-End Bearing Lubrication Starvation / Degradation",
        "failure_mode": "Hydrodynamic sleeve bearing wiped / oil film breakdown",
        "potential_causes": [
            "Lube oil pump delivery failure",
            "Lubricant thermal degradation or contamination",
            "Oil reservoir low level",
        ],
        "effects": "Metal-to-metal contact, severe temperature spike, shaft seizure",
        "severity": 9,
        "occurrence": 3,
        "detection": 4,
        "rpn": 108,
        "falsification_checks": [
            "Check if bearing temp elevation preceded any hydraulic disturbances",
            "Check if vibration signature shows high cage/ball-pass frequency without suction drop",
            "Check CMMS lube oil maintenance and sampling logs",
        ],
    },
    {
        "hypothesis_id": "H2",
        "name": "NPSH Starvation Induced Impeller Cavitation via Upstream Restriction",
        "failure_mode": "First-stage impeller eye cavitation, vapor pocket collapse, destructive pressure pulsations",
        "potential_causes": [
            "Upstream suction strainer basket blinding/fouling",
            "Suction valve partially closed or throttled",
            "Deaerator vessel level/pressure collapse",
        ],
        "effects": "Broadband high-frequency vibration, suction pressure drop below NPSHr, severe bearing thermal loading, pump trip",
        "severity": 9,
        "occurrence": 6,
        "detection": 2,
        "rpn": 108,
        "falsification_checks": [
            "Verify suction pressure PT-30101 < NPSHr (1.20 bar)",
            "Verify strainer differential pressure DPS-30101 > 1.00 bar alarm",
            "Verify FFT vibration spectral energy shows broadband cavitation floor (2kHz - 8kHz) surge",
            "Verify motor current IT-30101 shows two-phase flow fluctuations (+/- 15-25%)",
        ],
    },
    {
        "hypothesis_id": "H3",
        "name": "Electric Drive Motor Rotor/Stator Electrical Overload",
        "failure_mode": "Induction motor electrical winding overheating or broken rotor bar",
        "potential_causes": [
            "Supply grid voltage unbalance",
            "Inter-turn insulation breakdown",
            "Mechanical rotor binding from internal pump seizure",
        ],
        "effects": "High line current draw, thermal breaker trip, motor winding burn-out",
        "severity": 8,
        "occurrence": 2,
        "detection": 3,
        "rpn": 48,
        "falsification_checks": [
            "Verify motor current IT-30101 exceeded continuous Full Load Amps (FLA 115A) steadily",
            "Verify pole-pass frequency sidebands in current spectrum",
            "Check if current anomaly was isolated from suction/process hydraulic drops",
        ],
    },
    {
        "hypothesis_id": "H_VFD_ERR06",
        "name": "Deceleration Overvoltage (WECON VM Err06)",
        "failure_mode": "DC link overvoltage trip during motor deceleration / regenerative back-EMF",
        "potential_causes": [
            "Deceleration time F0.18 set too short for load inertia",
            "Dynamic braking resistor missing or open-circuit",
            "Supply mains transient overvoltage surge",
        ],
        "effects": "Drive trip Err06, DC bus voltage > 700V, motor coasting to stop, process shutdown",
        "severity": 7,
        "occurrence": 5,
        "detection": 1,
        "rpn": 35,
        "falsification_checks": [
            "Verify DC bus voltage Reg 3004H surged past 700V limit during deceleration",
            "Verify fault code Reg 700BH reported 6 (Err06)",
            "Check parameter F0.18 decel time vs load inertia",
            "Inspect braking resistor connection on terminals P+ and PB",
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
    {
        "hypothesis_id": "H_VFD_ERR02",
        "name": "Acceleration Overcurrent (WECON VM Err02)",
        "failure_mode": "Instantaneous overcurrent trip during acceleration ramp",
        "potential_causes": [
            "Acceleration time F0.17 set too short",
            "Motor rotor locked or seized",
            "Motor winding insulation breakdown or phase short-circuit",
        ],
        "effects": "Drive trip Err02, immediate inverter IGBT shutdown",
        "severity": 8,
        "occurrence": 3,
        "detection": 1,
        "rpn": 24,
        "falsification_checks": [
            "Verify output current Reg 3002H exceeded 200% inverter rated current during startup",
            "Verify fault code Reg 700BH reported 2 (Err02)",
        ],
    },
]


# WECON VM Series VFD Specifications & Modbus Registers
WECON_VM_VFD_SPEC: Dict[str, Any] = {
    "asset_id": "VFD_VM_01",
    "asset_name": "WECON VM Series Variable Frequency Drive",
    "manufacturer": "WECON Technology Co., Ltd.",
    "model": "VM-0R7G-4 (3-Phase 380V 0.75kW)",
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
        "F0.17": {"name": "Acceleration Time", "default_s": 5.0},
        "F0.18": {"name": "Deceleration Time", "default_s": 5.0, "trip_injection_s": 0.2},
        "F2.03": {"name": "Motor Rated Current", "default_a": 1.15, "trip_injection_a": 0.3},
        "F9.00": {"name": "Slave Address", "setting": 1},
        "F9.01": {"name": "Baud Rate", "setting": 3, "desc": "9600 bps"},
        "F9.02": {"name": "Data Format", "setting": 0, "desc": "8-N-1"},
    },
    "fault_codes": {
        0: "Normal Operation (No Active Fault)",
        2: "Acceleration Overcurrent (Err02)",
        3: "Deceleration Overcurrent (Err03)",
        6: "Deceleration Overvoltage (Err06)",
        11: "Motor Thermal Overload (Err11)",
    },
    "dc_bus_overvoltage_threshold_v": 700.0,
}


def get_oem_spec(asset_id: str = "P-301A") -> Any:
    """Retrieve OEM specifications for the specified asset."""
    if asset_id == "P-301A":
        return OEM_PUMP_SPEC
    if asset_id in ("VFD_VM_01", "VFD"):
        return WECON_VM_VFD_SPEC
    raise ValueError(f"Unknown asset_id: {asset_id}. Currently supported: P-301A, VFD_VM_01")


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

