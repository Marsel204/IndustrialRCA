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
]


def get_oem_spec(asset_id: str = "P-301A") -> EquipmentSpec:
    """Retrieve OEM specifications for the specified asset."""
    if asset_id == "P-301A":
        return OEM_PUMP_SPEC
    raise ValueError(f"Unknown asset_id: {asset_id}. Currently supported: P-301A")


def get_fmea_entry(hypothesis_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve FMEA matrix entry for a hypothesis ID."""
    for entry in FMEA_KNOWLEDGE_BASE:
        if entry["hypothesis_id"] == hypothesis_id:
            return entry
    return None
