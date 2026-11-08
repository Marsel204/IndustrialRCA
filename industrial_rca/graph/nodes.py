"""Ingestion, anomaly screening, human review and local artifact boundaries.

Diagnostic choices and causal explanations are produced by the agent runtime,
not by fault-code-specific branches in this module.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from langgraph.types import Overwrite, interrupt

from industrial_rca.config import EQUIPMENT_ID, OPERATIONAL_LIMITS
from industrial_rca.data.telemetry_generator import TelemetryDataset, TelemetryStore
from industrial_rca.graph.debugger import debug_node
from industrial_rca.graph.state import RCAState
from industrial_rca.tools.cmms_connector import CMMSConnector
from industrial_rca.tools.telemetry_analytics import StatisticalProfiler
from industrial_rca.tools.topology_tracer import AssetTopologyTracer


def utc_now():
    return datetime.now(UTC).isoformat()


@debug_node("ingest_telemetry_event")
def ingest_telemetry_event(state: RCAState) -> dict[str, Any]:
    dataset_id = state.get("dataset_id")
    if not dataset_id:
        dataset = state.get("telemetry_dataset")
        if not isinstance(dataset, TelemetryDataset):
            raise ValueError("A dataset_id or telemetry_dataset is required")
        dataset_id = TelemetryStore.register(dataset)
    dataset = TelemetryStore.get(dataset_id)
    metadata = dict(dataset.metadata)
    asset_id = metadata.get("asset_id") or state.get("asset_id") or EQUIPMENT_ID
    fault_code = int(metadata.get("fault_code") or 0)
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.scenario_name,
        "asset_id": asset_id,
        "incident_id": metadata.get("incident_id")
        or (state.get("incident_id") if not state.get("agent_dataset_id") else None)
        or f"INC-{uuid4().hex}",
        "agent_dataset_id": dataset_id,
        "trip_metadata": {**metadata, "asset_id": asset_id, "fault_code": fault_code},
        "fault_code": fault_code,
        "has_active_trip": fault_code > 0,
        "pipeline_status": "INGESTED",
        "tag_profiles": {},
        "detected_anomalies": [],
        "hypotheses_to_test": [],
        "hypothesis_results": [],
        "winning_hypothesis": None,
        "falsification_summary": [],
        "fmea_classification": {},
        "causal_chain_5_whys": [],
        "root_cause_asset": "",
        "root_cause_description": "",
        "missing_evidence": [],
        "human_review_required": False,
        "human_review_payload": None,
        "human_review_decision": None,
        "incident_report_8d": None,
        "sap_work_order": None,
        "deepseek_evaluation": None,
        "agent_messages": [],
        "agent_observations": [],
        "agent_pending_calls": [],
        "agent_iterations": 0,
        "agent_done": False,
        "investigation_trace": [],
        "agent_diagnosis": None,
        "execution_logs": Overwrite(
            [
                f"[INGESTION] Registered incident for {asset_id}; source={metadata.get('source_type', 'unspecified')}."
            ]
        ),
    }


@debug_node("detect_anomalies")
def detect_anomalies(state: RCAState) -> dict[str, Any]:
    frame = TelemetryStore.get(state["dataset_id"]).df_1hz
    profiles, anomalies, gaps = {}, [], []
    active = bool(state.get("fault_code"))
    for tag in frame.columns:
        if tag in {"timestamp", "timestamp_sec", "status", "asset_id"}:
            continue
        values = pd.to_numeric(frame[tag], errors="coerce").to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) != len(values):
            gaps.append(
                f"{tag}: {len(values) - len(finite)} missing or invalid readings"
            )
        if not len(finite):
            continue
        profile = {
            **StatisticalProfiler.profile(finite),
            "sample_count": len(finite),
            "missing_count": len(values) - len(finite),
        }
        profiles[tag] = profile
        limits = OPERATIONAL_LIMITS.get(tag, {})
        checks = [
            (key, value)
            for key, value in limits.items()
            if key in {"alarm_high", "trip_high", "trip_min", "alarm_low", "trip_low"}
        ]
        for key, threshold in checks:
            low = key.endswith("low")
            value = profile["min" if low else "max"]
            breached = value <= threshold if low else value >= threshold
            if breached:
                anomalies.append(
                    {
                        "tag": tag,
                        "description": f"Observed {value:g}; configured {key}={threshold:g}",
                        "timestamp_sec": None,
                        "threshold": threshold,
                        "observed_value": value,
                    }
                )
                active = True
        if tag == "fault_code" and profile["max"] > 0:
            active = True
    if frame.empty:
        gaps.append("No telemetry samples were supplied")
    elif not any(tag != "fault_code" for tag in profiles):
        gaps.append("No measured sensor channels were supplied")
    # Missing data is unknown, not evidence of healthy operation.
    active = active or bool(gaps)
    return {
        "tag_profiles": profiles,
        "detected_anomalies": anomalies,
        "missing_evidence": gaps,
        "has_active_trip": active,
        "pipeline_status": "ANOMALIES_DETECTED" if active else "NORMAL_STABLE",
        "execution_logs": [
            f"[SCREENING] {len(anomalies)} configured limit breaches; {len(gaps)} data gaps."
        ],
    }


def aggregate_hypotheses(state: RCAState) -> dict[str, Any]:
    """Compatibility helper: never promote a refuted or inconclusive candidate."""
    results = state.get("hypothesis_results", [])
    supported = [
        item for item in results if item.get("status") in {"CONFIRMED", "SUPPORTED"}
    ]
    winner = max(supported, key=lambda item: item.get("confidence", 0), default=None)
    return {
        "winning_hypothesis": winner,
        "pipeline_status": "HYPOTHESES_AGGREGATED" if winner else "INCONCLUSIVE",
    }


@debug_node("human_review")
def human_review(state: RCAState) -> dict[str, Any]:
    winner = state["winning_hypothesis"]
    payload = {
        "incident_id": state["incident_id"],
        "asset_id": state["asset_id"],
        "asset_name": state["asset_id"],
        "winning_hypothesis": winner["name"],
        "confidence_pct": winner["confidence"] * 100,
        "confidence_basis": "Model assessment, not a calibrated probability",
        "iso14224_failure_mechanism": state.get("fmea_classification", {}).get(
            "failure_mechanism", "Unclassified"
        ),
        "root_cause_asset": state["root_cause_asset"],
        "root_cause_summary": state["root_cause_description"],
        "falsification_summary": state.get("falsification_summary", []),
        "causal_chain_5_whys": state.get("causal_chain_5_whys", []),
        "proposed_actions": winner["proposed_actions"],
        "missing_evidence": state.get("missing_evidence", []),
        "investigation_trace": state.get("investigation_trace", []),
        "cmms_overdue_work_order": "Not verified",
    }
    decision = interrupt(payload)
    decision = decision if isinstance(decision, dict) else {}
    action = str(decision.get("action", "reject")).lower().strip()
    reviewer = str(decision.get("reviewer") or "").strip()
    override = str(decision.get("override_root_cause") or "").strip()
    valid = action in {"approve", "approved", "override"} and bool(reviewer)
    if action == "override" and not override:
        valid = False
    if not valid:
        action = "reject"
    return {
        "human_review_required": True,
        "human_review_payload": payload,
        "human_review_decision": {
            **decision,
            "action": action,
            "reviewer": reviewer,
            "date": utc_now(),
        },
        "root_cause_description": override
        if action == "override"
        else state["root_cause_description"],
        "pipeline_status": "APPROVED" if valid else "REJECTED",
        "execution_logs": [
            f"[HUMAN_REVIEW] {action.upper()} by {reviewer or 'unnamed reviewer'}"
        ],
    }


@debug_node("generate_maintenance_artifacts")
def generate_maintenance_artifacts(state: RCAState) -> dict[str, Any]:
    decision = state.get("human_review_decision") or {}
    if decision.get("action") not in {
        "approve",
        "approved",
        "override",
    } or not decision.get("reviewer"):
        raise ValueError(
            "Explicit human approval is required before generating artifacts"
        )
    winner = state["winning_hypothesis"]
    actions = winner.get("proposed_actions", [])
    asset_id = state["asset_id"]
    equipment = AssetTopologyTracer().get_equipment(asset_id) or {}
    fmea = state.get("fmea_classification", {})
    report = {
        "report_type": "8D Incident Investigation Report (Draft)",
        "incident_id": state["incident_id"],
        "asset_id": asset_id,
        "asset_name": equipment.get("name", asset_id),
        "classification": "Reviewed diagnostic assessment",
        "d1_team": {"lead": decision["reviewer"]},
        "d2_problem_description": {
            "what": f"Reported incident for {asset_id}; fault code {state.get('fault_code', 'unavailable')}",
            "when": state.get("trip_metadata", {}).get("trip_time_str", "Not supplied"),
            "where": asset_id,
            "how_much": "Impact not independently verified",
            "operational_impact": "Not supplied",
        },
        "d3_interim_containment_actions": [],
        "d4_root_cause_analysis": {
            "iso_14224_code": fmea.get("iso_code"),
            "failure_mechanism": fmea.get("failure_mechanism"),
            "root_cause_asset": state["root_cause_asset"],
            "root_cause_statement": state["root_cause_description"],
            "falsification_matrix": state.get("falsification_summary", []),
            "five_whys_trace": state.get("causal_chain_5_whys", []),
            "evidence": state.get("agent_observations", []),
            "missing_evidence": state.get("missing_evidence", []),
            "deepseek_ai_evaluation": state.get("deepseek_evaluation"),
        },
        "ai_diagnostic_engine": (state.get("deepseek_evaluation") or {}).get(
            "model", "Unspecified"
        ),
        "d5_permanent_corrective_actions": actions,
        "d6_implementation_and_validation": {
            "validation_method": "Engineer must define and verify an implementation protocol",
            "acceptance_criteria": "Not yet specified",
        },
        "d7_systemic_prevention": [],
        "d8_sign_off": {
            "reliability_manager_approval": decision["action"],
            "reviewed_by": decision["reviewer"],
            "review_notes": decision.get("notes", ""),
            "date": decision["date"],
        },
    }
    order = CMMSConnector().generate_sap_pm01_work_order(
        asset_id=asset_id,
        incident_id=state["incident_id"],
        failure_mode=winner["name"],
        root_cause_summary=state["root_cause_description"],
        corrective_actions=actions,
    )["sap_work_order"]
    return {
        "incident_report_8d": report,
        "sap_work_order": order,
        "pipeline_status": "COMPLETED",
        "execution_logs": [
            "[ARTIFACTS] Created reviewed local 8D and PM01 drafts; no external release."
        ],
    }


@debug_node("handle_rejection")
def handle_rejection(state: RCAState) -> dict[str, Any]:
    return {
        "pipeline_status": "REJECTED",
        "incident_report_8d": None,
        "sap_work_order": None,
        "execution_logs": ["[REVIEW] Rejected; no maintenance artifacts generated."],
    }
