"""Bounded adaptive investigation with checkpointed tools and human review."""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from industrial_rca.agent.contracts import InvestigationBudget
from industrial_rca.agent.runtime import InvestigationRuntime
from industrial_rca.graph.nodes import (
    detect_anomalies,
    generate_maintenance_artifacts,
    handle_rejection,
    human_review,
    ingest_telemetry_event,
)
from industrial_rca.graph.state import RCAState
from industrial_rca.tools.deepseek_client import DeepSeekClient


def route_after_detection(state):
    return "initialize_investigation" if state.get("has_active_trip") else END


def route_after_review(state):
    decision = state.get("human_review_decision") or {}
    return (
        "generate_maintenance_artifacts"
        if decision.get("action") in {"approve", "approved", "override"}
        else "handle_rejection"
    )


def route_after_decision(state):
    return END if state.get("agent_done") else "execute_tools"


def route_after_tools(state):
    if not state.get("agent_done"):
        return "decide_next_action"
    return "human_review" if state.get("winning_hypothesis") else END


def create_rca_graph(
    checkpointer: Any = None, *, decision_client=None, max_agent_iterations=8
):
    runtime = InvestigationRuntime(
        decision_client if decision_client is not None else DeepSeekClient(),
        InvestigationBudget(max_iterations=max_agent_iterations),
    )
    builder = StateGraph(RCAState)
    for name, node in {
        "ingest_telemetry_event": ingest_telemetry_event,
        "detect_anomalies": detect_anomalies,
        "initialize_investigation": runtime.initialize,
        "decide_next_action": runtime.decide,
        "execute_tools": runtime.execute,
        "human_review": human_review,
        "generate_maintenance_artifacts": generate_maintenance_artifacts,
        "handle_rejection": handle_rejection,
    }.items():
        builder.add_node(name, node)
    builder.add_edge(START, "ingest_telemetry_event")
    builder.add_edge("ingest_telemetry_event", "detect_anomalies")
    builder.add_conditional_edges(
        "detect_anomalies", route_after_detection, ["initialize_investigation", END]
    )
    builder.add_conditional_edges(
        "initialize_investigation",
        lambda state: END if state.get("agent_done") else "decide_next_action",
        ["decide_next_action", END],
    )
    builder.add_conditional_edges(
        "decide_next_action", route_after_decision, ["execute_tools", END]
    )
    builder.add_conditional_edges(
        "execute_tools", route_after_tools, ["decide_next_action", "human_review", END]
    )
    builder.add_conditional_edges(
        "human_review",
        route_after_review,
        ["generate_maintenance_artifacts", "handle_rejection"],
    )
    builder.add_edge("generate_maintenance_artifacts", END)
    builder.add_edge("handle_rejection", END)
    return builder.compile(
        checkpointer=checkpointer if checkpointer is not None else MemorySaver()
    )


rca_pipeline = create_rca_graph()
