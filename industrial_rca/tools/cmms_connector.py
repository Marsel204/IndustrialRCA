"""
CMMS (Computerized Maintenance Management System) Connector.
Provides mock integration with Enterprise EAM/CMMS (SAP PM / IBM Maximo).
Exposes maintenance history, oil analysis logs, and generates SAP PM01 Corrective Work Orders.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import random


class CMMSConnector:
    """Mock Enterprise CMMS Connector for SAP PM / IBM Maximo integration."""

    def __init__(self):
        self._maintenance_history = {
            "VFD_VM_01": [
                {
                    "order_id": "WM-2026-0901",
                    "type": "PM02",
                    "description": "Routine quarterly inverter terminal torque check & parameter backup",
                    "completed_date": "2026-09-01",
                    "technician": "A. Chen (Automation Engineer)",
                    "findings": "Control terminals tight. DC bus nominal 182V. Parameter backup completed (F0.17=5.0s, F0.18=5.0s, F0.10=40.0Hz).",
                },
                {
                    "order_id": "WM-2026-0910",
                    "type": "PM02",
                    "description": "Dynamic braking circuit inspection on terminals P+ and PB",
                    "completed_date": "2026-09-10",
                    "technician": "M. Al-Hassan (Electrical Tech)",
                    "findings": "External braking resistor not fitted; internal chopper disabled. Verified safe for steady 40 Hz run.",
                },
            ],
            "IND_MOTOR_01": [
                {
                    "order_id": "WM-2026-0820",
                    "type": "PM02",
                    "description": "Annual 3-phase motor insulation resistance megger test (500V DC)",
                    "completed_date": "2026-08-20",
                    "technician": "E. Zhao (Electrical Eng)",
                    "findings": "Phase-to-ground IR > 300 M-Ohm. Stator winding resistance balance 0.15%. Shaft free rotation normal.",
                }
            ],
            "STR-301A": [
                {
                    "order_id": "WM-2026-0831",
                    "type": "PM02",
                    "description": "Scheduled bi-weekly flush (Due 2026-08-31)",
                    "completed_date": None,
                    "status": "OVERDUE",
                    "findings": "MAINTENANCE DEFERRED",
                }
            ],
            "P-301A": [],
        }

    def query_maintenance_history(self, asset_id: str) -> List[Dict[str, Any]]:
        """Query past work orders and maintenance logs for an asset."""
        return self._maintenance_history.get(asset_id, self._maintenance_history.get("VFD_VM_01", []))

    def query_lube_oil_analysis(self, asset_id: str = "VFD_VM_01") -> Dict[str, Any]:
        """Query motor bearing lubrication / electrical health check."""
        return {
            "asset_id": asset_id,
            "sample_date": "2026-09-01",
            "megger_ir_mohm": 320.0,
            "phase_resistance_unbalance_pct": 0.12,
            "dc_bus_esr_status": "NORMAL",
            "status": "HEALTHY",
            "assessment": "No pre-existing electrical winding degradation, phase imbalance, or DC capacitor degradation detected.",
        }

    def generate_sap_pm01_work_order(
        self,
        asset_id: str,
        incident_id: str,
        failure_mode: str,
        root_cause_summary: str,
        corrective_actions: List[str],
        priority: str = "1 - Emergency / Immediate Outage",
    ) -> Dict[str, Any]:
        """
        Emits a structured SAP PM01 Corrective Maintenance Work Order compliant with SAP S/4HANA PM schema.
        """
        order_num = f"4009{random.randint(20000, 99999)}"
        notification_num = f"1008{random.randint(10000, 99999)}"
        timestamp_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

        operations = [
            {
                "operation_number": "0010",
                "work_center": "ELEC-01",
                "duration_hours": 1.0,
                "description": "Lock-Out/Tag-Out (LOTO) & DC Bus Safe Discharge Verification",
                "details": f"Open main circuit breaker CB_01. Measure DC link voltage on terminals + and - with calibrated DMM; verify V_dc < 24.0V before servicing.",
            },
            {
                "operation_number": "0020",
                "work_center": "ELEC-01",
                "duration_hours": 2.0,
                "description": "Dynamic Braking Resistor Inspection & Installation (P+/PB)",
                "details": "Inspect braking transistor chopper. Install 70-Ohm 150W ceramic dynamic braking resistor across terminals P+ and PB to dissipate regenerative decel energy.",
            },
            {
                "operation_number": "0030",
                "work_center": "AUTO-01",
                "duration_hours": 1.5,
                "description": "Inverter & PLC Parameter Reprogramming",
                "details": "Program deceleration ramp parameter F0.18 to controlled 5.0s (prevent rapid stop current spike). Set max frequency clamp F0.10 <= 40.00 Hz and enable DC overvoltage stall prevention F3.08.",
            },
            {
                "operation_number": "0040",
                "work_center": "ELEC-01",
                "duration_hours": 1.5,
                "description": "Induction Motor Megger & Phase Balance Testing",
                "details": "Perform 500V DC megger test on motor phases U, V, W to PE (>50 M-Ohm required). Measure phase-to-phase resistance balance (<1% unbalance).",
            },
            {
                "operation_number": "0050",
                "work_center": "OPS-01",
                "duration_hours": 1.5,
                "description": "Step-Speed Commissioning & Decel Load Sign-Off",
                "details": "Energize drive, step speed across 10 Hz, 25 Hz, 40 Hz. Verify DC bus voltage remains within 170.0V - 190.0V envelope during controlled stop without trip.",
            },
        ]

        bill_of_materials = [
            {"material_id": "MAT-VFD-BRK70", "description": "70-Ohm 150W Wirewound Dynamic Braking Resistor Unit", "quantity": 1, "unit": "EA"},
            {"material_id": "MAT-CBL-4C25", "description": "4-Core 2.5mm2 Shielded VFD Inverter Motor Cable", "quantity": 5, "unit": "M"},
            {"material_id": "MAT-BRK-MCCB16", "description": "16A 2-Pole Molded Case Circuit Breaker (MCCB)", "quantity": 1, "unit": "EA"},
            {"material_id": "MAT-COMM-RS485", "description": "Shielded Twisted Pair RS-485 Modbus RTU Comm Cable", "quantity": 2, "unit": "M"},
        ]

        return {
            "sap_work_order": {
                "order_number": order_num,
                "order_type": "PM01",
                "order_category": "Corrective Maintenance",
                "notification_number": notification_num,
                "functional_location": "FLOC: PLNT-B01-VFD-BENCH01",
                "equipment_id": "10049201",
                "equipment_name": f"{asset_id} Wecon VM Series Inverter & Motor Bench",
                "planning_plant": "1000 (Electrical Test Lab)",
                "planner_group": "E01 (Power Electronics & Drives)",
                "cost_center": "CC-ELEC-01",
                "created_on": timestamp_now,
                "priority": priority,
                "breakdown_indicator": "X (True)",
                "system_status": "CRTD REL (Created & Released)",
                "failure_mode_iso14224": failure_mode,
                "incident_reference": incident_id,
                "short_text": f"RCA Remediation: {asset_id} Drive Trip Recovery & Parameter Optimization",
                "long_text": (
                    f"Root Cause: {root_cause_summary}\n"
                    f"Action Required: Install dynamic braking resistor on terminals P+/PB, adjust parameter F0.18 "
                    f"to controlled ramp, clamp max frequency F0.10 <= 40.0 Hz, and verify under step-speed commissioning."
                ),
                "operations": operations,
                "materials_required": bill_of_materials,
                "total_estimated_hours": sum(op["duration_hours"] for op in operations),
            }
        }
