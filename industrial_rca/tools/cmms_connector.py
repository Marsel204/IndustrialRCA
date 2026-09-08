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
            "P-301A": [
                {
                    "order_id": "WM-2026-0812",
                    "type": "PM02",
                    "description": "Routine quarterly laser shaft alignment & vibration check",
                    "completed_date": "2026-08-12",
                    "technician": "J. Martinez (Reliability Specialist)",
                    "findings": "Coupling alignment within tolerance (radial offset 0.02 mm). Vibration baseline 1.75 mm/s RMS.",
                },
                {
                    "order_id": "WM-2026-0822",
                    "type": "PM03",
                    "description": "Lube oil condition sampling & spectroscopic analysis",
                    "completed_date": "2026-08-22",
                    "technician": "Lube Lab Intertek",
                    "findings": "Oil cleanliness ISO 16/14/11. Water content < 35 ppm. Wear metals Fe < 5 ppm, Cu < 2 ppm. Viscosity 45.8 cSt @ 40C (Target 46.0). Normal.",
                },
            ],
            "STR-301A": [
                {
                    "order_id": "WM-2026-0817",
                    "type": "PM02",
                    "description": "Bi-weekly manual flush & inspection of dual strainer baskets",
                    "completed_date": "2026-08-17",
                    "technician": "D. Vance (Operations)",
                    "findings": "Basket A had minor algae coating; cleaned and re-seated. Clean dP restored to 0.11 bar.",
                },
                {
                    "order_id": "WM-2026-0831",
                    "type": "PM02",
                    "description": "Scheduled bi-weekly flush (Due 2026-08-31)",
                    "completed_date": None,
                    "status": "OVERDUE (Delayed by operations due to high steam demand)",
                    "findings": "MAINTENANCE DEFERRED by Shift Supervisor.",
                }
            ],
            "M-301A": [
                {
                    "order_id": "WM-2026-0720",
                    "type": "PM02",
                    "description": "Annual motor insulation resistance megger test & stator surge test",
                    "completed_date": "2026-07-20",
                    "technician": "E. Zhao (Electrical Eng)",
                    "findings": "Phase-to-ground IR > 250 M-Ohm. Stator resistance balance 0.12%. Motor health excellent.",
                }
            ],
        }

    def query_maintenance_history(self, asset_id: str) -> List[Dict[str, Any]]:
        """Query past work orders and maintenance logs for an asset."""
        return self._maintenance_history.get(asset_id, [])

    def query_lube_oil_analysis(self, asset_id: str = "P-301A") -> Dict[str, Any]:
        """Query latest laboratory oil analysis."""
        return {
            "asset_id": asset_id,
            "sample_date": "2026-08-22",
            "oil_grade": "ISO VG 46 Turbine Oil",
            "water_ppm": 32,
            "viscosity_40c_cst": 45.8,
            "particle_count_iso4406": "16/14/11",
            "wear_metals_ppm": {"iron_fe": 4.1, "copper_cu": 1.2, "lead_pb": 0.3},
            "status": "HEALTHY",
            "assessment": "No indication of pre-existing lubricant breakdown, particulate contamination, or water ingress.",
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
                "work_center": "MECH-01",
                "duration_hours": 2.0,
                "description": "Lock-Out/Tag-Out (LOTO) and De-pressurization",
                "details": f"Electrically isolate motor M-301A (switchgear cubicle 3.3kV breaker racked out). Close suction & discharge isolation valves. Lock, tag, and verify zero pressure at drain ports.",
            },
            {
                "operation_number": "0020",
                "work_center": "MECH-01",
                "duration_hours": 4.0,
                "description": "Clean, Inspect & Replace Suction Strainer STR-301A Basket",
                "details": "Unbolt strainer bonnet, remove fouled basket. Document marine fouling debris photos for RCA file. Install replacement 316SS 20-mesh basket, torque cover bolts to OEM spec with new fluorocarbon gasket.",
            },
            {
                "operation_number": "0030",
                "work_center": "RELIAB-01",
                "duration_hours": 3.5,
                "description": "Impeller Eye Cavitation Boroscope Inspection",
                "details": "Insert video boroscope via suction nozzle to inspect first-stage impeller leading edges for cavitation pitting erosion or vane chipping. Verify shaft free rotation by hand.",
            },
            {
                "operation_number": "0040",
                "work_center": "LUBE-01",
                "duration_hours": 3.0,
                "description": "Drive-End Hydrodynamic Bearing Inspection & Lube Flush",
                "details": "Open DE bearing housing. Measure bearing sleeve radial clearance with plastigage (limit < 0.09 mm). Drain contaminated/thermally stressed oil, flush sump, refill with 40L fresh ISO VG 46.",
            },
            {
                "operation_number": "0050",
                "work_center": "OPS-01",
                "duration_hours": 2.5,
                "description": "Priming, Venting, Baseline Commissioning & Vibration Sign-off",
                "details": "Line up suction, flood pump casing, vent non-condensables. Restart under no-load, transfer flow. Verify baseline suction pressure > 2.3 bar, strainer dP < 0.15 bar, vibration RMS < 2.0 mm/s.",
            },
        ]

        bill_of_materials = [
            {"material_id": "MAT-90214-GKT", "description": "Fluorocarbon Strainer Cover Gasket 12-inch", "quantity": 2, "unit": "EA"},
            {"material_id": "MAT-88201-BKT", "description": "316SS 20-Mesh Replacement Basket for STR-301A", "quantity": 1, "unit": "EA"},
            {"material_id": "MAT-77102-OIL", "description": "Shell Turbo T 46 Turbine Lubricating Oil", "quantity": 40, "unit": "L"},
            {"material_id": "MAT-55120-SLV", "description": "Drive-End Sleeve Bearing Insert 85mm ID", "quantity": 1, "unit": "EA (Reserve)"},
        ]

        return {
            "sap_work_order": {
                "order_number": order_num,
                "order_type": "PM01",
                "order_category": "Corrective Maintenance",
                "notification_number": notification_num,
                "functional_location": "FLOC: PLNT-B03-FW300-P301A",
                "equipment_id": "10049201",
                "equipment_name": f"{asset_id} High-Pressure Boiler Feed Pump A",
                "planning_plant": "1000 (Baytown Complex)",
                "planner_group": "M03 (Boiler Feed Machinery)",
                "cost_center": "CC-PWR-300",
                "created_on": timestamp_now,
                "priority": priority,
                "breakdown_indicator": "X (True)",
                "system_status": "CRTD REL (Created & Released)",
                "failure_mode_iso14224": failure_mode,
                "incident_reference": incident_id,
                "short_text": f"RCA Remediation: {asset_id} Cavitation & Bearing Overheat Restoration",
                "long_text": (
                    f"Root Cause: {root_cause_summary}\n"
                    f"Action Required: Clean upstream strainer STR-301A, inspect impeller for cavitation pitting, "
                    f"flush bearing lubricant, and re-commission under vibration surveillance."
                ),
                "operations": operations,
                "materials_required": bill_of_materials,
                "total_estimated_hours": sum(op["duration_hours"] for op in operations),
            }
        }
