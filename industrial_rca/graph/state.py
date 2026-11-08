"""
State Definitions for LangGraph Root Cause Analysis Workflow.
Defines incident state and the audit-log reducer for the adaptive investigation.
"""

import operator
from typing import Annotated, Any, TypedDict


class RCAState(TypedDict, total=False):
    """Global state of the Root Cause Analysis LangGraph pipeline."""

    # Ingestion & Context
    asset_id: str
    incident_id: str
    dataset_name: str
    dataset_id: str  # In-memory TelemetryStore reference key
    trip_metadata: dict[str, Any]

    # Anomaly Detection Output
    detected_anomalies: list[dict[str, Any]]
    tag_profiles: dict[str, dict[str, Any]]
    has_active_trip: bool
    fault_code: int

    # Hypotheses to Test
    hypotheses_to_test: list[dict[str, Any]]

    # Model hypotheses and their collected evidence
    hypothesis_results: list[dict[str, Any]]

    # Aggregated Diagnosis
    winning_hypothesis: dict[str, Any] | None
    falsification_summary: list[dict[str, Any]]
    fmea_classification: dict[str, Any]

    # 5-Whys Causal Deep-Dive
    causal_chain_5_whys: list[dict[str, Any]]
    root_cause_asset: str
    root_cause_description: str

    # HITL Gate
    human_review_required: bool
    human_review_payload: dict[str, Any] | None
    human_review_decision: dict[str, Any] | None

    # DeepSeek AI Integration
    use_deepseek: bool
    deepseek_model: str
    deepseek_evaluation: dict[str, Any] | None

    # Maintenance Artifacts
    incident_report_8d: dict[str, Any] | None
    sap_work_order: dict[str, Any] | None

    # Pipeline Status & Audit Trail
    pipeline_status: str  # "INITIALIZED", "ANOMALY_DETECTED", "NORMAL_STABLE", "HYPOTHESIS_TESTED", "AWAITING_REVIEW", "APPROVED", "REJECTED", "COMPLETED"
    execution_logs: Annotated[list[str], operator.add]

    # Incident-scoped agent history is replaced atomically at each checkpoint.
    agent_dataset_id: str
    agent_messages: list[dict[str, Any]]
    agent_observations: list[dict[str, Any]]
    agent_pending_calls: list[dict[str, Any]]
    agent_iterations: int
    agent_started_at: float
    agent_done: bool
    agent_diagnosis: dict[str, Any] | None
    investigation_trace: list[dict[str, Any]]
    missing_evidence: list[str]
