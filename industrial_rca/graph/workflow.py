"""
LangGraph Workflow Definition for the Industrial Root Cause Analysis (RCA) Pipeline.
Implements:
- Hybrid execution (sequential macro-flow, dynamic parallel fan-out via Send, sequential 5-Whys)
- State persistence via MemorySaver checkpointer
- Human-in-the-Loop (HITL) gate via interrupt()
"""

from typing import List, Dict, Any, Union
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, Command
from langgraph.checkpoint.memory import MemorySaver

from industrial_rca.graph.state import RCAState, HypothesisWorkerInput
from industrial_rca.graph.nodes import (
    ingest_telemetry_event,
    detect_anomalies,
    generate_hypotheses,
    test_hypothesis_worker,
    aggregate_hypotheses,
    causal_deep_dive_5_whys,
    human_review,
    generate_maintenance_artifacts,
    handle_rejection,
)


def route_after_detection(state: RCAState) -> str:
    """Routes to hypothesis generation if an active anomaly trip is detected, otherwise terminates."""
    if state.get("has_active_trip", False):
        return "generate_hypotheses"
    return END


def fan_out_hypotheses(state: RCAState) -> List[Send]:
    """
    Dynamic parallel fan-out using LangGraph's Send primitive.
    Dispatches each candidate hypothesis to an independent worker node.
    """
    hypotheses = state.get("hypotheses_to_test", [])
    dataset_id = state["dataset_id"]
    asset_id = state.get("asset_id", "P-301A")
    trip_metadata = state.get("trip_metadata", {})

    return [
        Send(
            "test_hypothesis_worker",
            {
                "hypothesis": h,
                "dataset_id": dataset_id,
                "asset_id": asset_id,
                "trip_metadata": trip_metadata,
            },
        )
        for h in hypotheses
    ]


def route_after_review(state: RCAState) -> str:
    """Routes to artifact emission if approved or overridden; otherwise handles rejection."""
    decision = state.get("human_review_decision", {})
    action = decision.get("action", "approve").lower()
    if action in ("approve", "override"):
        return "generate_maintenance_artifacts"
    return "handle_rejection"


def create_rca_graph(checkpointer: Any = None):
    """
    Constructs and compiles the stateful LangGraph RCA pipeline.
    """
    builder = StateGraph(RCAState)

    # Register Nodes
    builder.add_node("ingest_telemetry_event", ingest_telemetry_event)
    builder.add_node("detect_anomalies", detect_anomalies)
    builder.add_node("generate_hypotheses", generate_hypotheses)
    builder.add_node("test_hypothesis_worker", test_hypothesis_worker)
    builder.add_node("aggregate_hypotheses", aggregate_hypotheses)
    builder.add_node("causal_deep_dive_5_whys", causal_deep_dive_5_whys)
    builder.add_node("human_review", human_review)
    builder.add_node("generate_maintenance_artifacts", generate_maintenance_artifacts)
    builder.add_node("handle_rejection", handle_rejection)

    # Register Edges
    # 1. Entry point -> Anomaly Detection
    builder.add_edge(START, "ingest_telemetry_event")
    builder.add_edge("ingest_telemetry_event", "detect_anomalies")

    # 2. Anomaly Detection -> Conditional (Trip vs Healthy Baseline)
    builder.add_conditional_edges(
        "detect_anomalies",
        route_after_detection,
        ["generate_hypotheses", END],
    )

    # 3. Hypothesis Generation -> Dynamic Parallel Fan-out via Send()
    builder.add_conditional_edges(
        "generate_hypotheses",
        fan_out_hypotheses,
        ["test_hypothesis_worker"],
    )

    # 4. Parallel Workers -> Aggregation Join Node
    builder.add_edge("test_hypothesis_worker", "aggregate_hypotheses")

    # 5. Aggregation -> 5-Whys Causal Deep-Dive
    builder.add_edge("aggregate_hypotheses", "causal_deep_dive_5_whys")

    # 6. 5-Whys -> HITL Review Gate (Interrupt)
    builder.add_edge("causal_deep_dive_5_whys", "human_review")

    # 7. HITL Review -> Conditional (Approve/Override vs Reject)
    builder.add_conditional_edges(
        "human_review",
        route_after_review,
        ["generate_maintenance_artifacts", "handle_rejection"],
    )

    # 8. Terminal Edges
    builder.add_edge("generate_maintenance_artifacts", END)
    builder.add_edge("handle_rejection", END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=saver)


# Global default compiled graph
rca_pipeline = create_rca_graph()
