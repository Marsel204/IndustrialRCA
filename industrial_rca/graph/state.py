"""
State Definitions for LangGraph Root Cause Analysis Workflow.
Defines TypedDict schemas and reducers for parallel fan-out and sequential aggregation.
"""

from typing import Annotated, TypedDict, List, Dict, Any, Optional
import operator


class HypothesisWorkerInput(TypedDict):
    """Payload passed to parallel worker node via dynamic Send()."""
    hypothesis: Dict[str, Any]
    dataset_id: str
    asset_id: str
    trip_metadata: Dict[str, Any]


class HypothesisTestResult(TypedDict):
    """Individual hypothesis test outcome returned by parallel worker."""
    hypothesis_id: str
    name: str
    status: str  # "CONFIRMED", "REFUTED", "SECONDARY_SYMPTOM", "INCONCLUSIVE"
    confidence: float
    evidence: List[Dict[str, Any]]
    falsification_rationale: str
    metrics: Dict[str, Any]
    proposed_actions: List[str]


class RCAState(TypedDict, total=False):
    """Global state of the Root Cause Analysis LangGraph pipeline."""
    # Ingestion & Context
    asset_id: str
    incident_id: str
    dataset_name: str
    dataset_id: str  # In-memory TelemetryStore reference key
    trip_metadata: Dict[str, Any]

    # Anomaly Detection Output
    detected_anomalies: List[Dict[str, Any]]
    tag_profiles: Dict[str, Dict[str, Any]]
    has_active_trip: bool

    # Hypotheses to Test
    hypotheses_to_test: List[Dict[str, Any]]

    # Parallel Hypothesis Testing (Aggregated via operator.add reducer)
    hypothesis_results: Annotated[List[Dict[str, Any]], operator.add]

    # Aggregated Diagnosis
    winning_hypothesis: Optional[Dict[str, Any]]
    falsification_summary: List[Dict[str, Any]]
    fmea_classification: Dict[str, Any]

    # 5-Whys Causal Deep-Dive
    causal_chain_5_whys: List[Dict[str, Any]]
    root_cause_asset: str
    root_cause_description: str

    # HITL Gate
    human_review_required: bool
    human_review_payload: Optional[Dict[str, Any]]
    human_review_decision: Optional[Dict[str, Any]]

    # DeepSeek AI Integration
    use_deepseek: bool
    deepseek_model: str
    deepseek_evaluation: Optional[Dict[str, Any]]

    # Maintenance Artifacts
    incident_report_8d: Optional[Dict[str, Any]]
    sap_work_order: Optional[Dict[str, Any]]

    # Pipeline Status & Audit Trail
    pipeline_status: str  # "INITIALIZED", "ANOMALY_DETECTED", "NORMAL_STABLE", "HYPOTHESIS_TESTED", "AWAITING_REVIEW", "APPROVED", "REJECTED", "COMPLETED"
    execution_logs: Annotated[List[str], operator.add]

