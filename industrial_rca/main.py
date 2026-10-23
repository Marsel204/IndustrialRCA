"""Terminal entry point for evidence-driven RCA and explicitly simulated datasets."""

import argparse
import json
from uuid import uuid4

from langgraph.types import Command, Overwrite
from rich.console import Console
from rich.prompt import Prompt

from industrial_rca.data.telemetry_generator import (
    TelemetryStore,
    generate_fault_scenario,
    generate_normal_scenario,
)
from industrial_rca.graph.workflow import create_rca_graph
from industrial_rca.tools.deepseek_client import DeepSeekClient

console = Console()


def print_final_artifacts(values):
    """Print reviewed local drafts; no external ERP records are created."""
    for key in ("incident_report_8d", "sap_work_order"):
        artifact = values.get(key)
        if artifact:
            console.print_json(json.dumps(artifact))
    console.print(
        "Local drafts only. No SAP submission or equipment action was performed."
    )


def run_baseline_verification(graph, dataset, thread_id="baseline"):
    dataset_id = TelemetryStore.register(dataset)
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"dataset_id": dataset_id}, config)
    values = graph.get_state(config).values
    console.print(
        f"Simulated baseline: {values['pipeline_status']}; {len(values.get('tag_profiles', {}))} observed channels"
    )
    return values


def run_fault_investigation(
    graph,
    dataset,
    thread_id=None,
    auto_decision=None,
    use_deepseek=True,
    deepseek_model=None,
):
    dataset_id = TelemetryStore.register(dataset)
    config = {
        "configurable": {"thread_id": thread_id or f"cli-{uuid4().hex}"},
        "recursion_limit": 100,
    }
    console.print(
        "Investigating a simulated dataset. Conclusions do not establish real hardware condition."
    )
    for event in graph.stream(
        {
            "dataset_id": dataset_id,
            "use_deepseek": use_deepseek,
            "deepseek_model": deepseek_model,
        },
        config,
    ):
        for name, update in event.items():
            if isinstance(update, dict):
                logs = update.get("execution_logs", [])
                if isinstance(logs, Overwrite):
                    logs = logs.value
                for log in logs:
                    if isinstance(log, str):
                        console.print(log, markup=False)
    snapshot = graph.get_state(config)
    if not snapshot.tasks or not snapshot.tasks[0].interrupts:
        console.print(snapshot.values.get("pipeline_status", "INCONCLUSIVE"))
        for gap in snapshot.values.get("missing_evidence", []):
            console.print(f"Evidence needed: {gap}", markup=False)
        return snapshot.values
    console.print_json(json.dumps(snapshot.tasks[0].interrupts[0].value))
    action = auto_decision or Prompt.ask(
        "Review decision", choices=["approve", "reject", "override"], default="reject"
    )
    reviewer = (
        "CLI explicit simulation approval"
        if auto_decision
        else Prompt.ask("Reviewer name")
    )
    override = Prompt.ask("Override statement") if action == "override" else None
    graph.invoke(
        Command(
            resume={
                "action": action,
                "reviewer": reviewer,
                "notes": "Reviewed simulated investigation in CLI",
                "override_root_cause": override,
            }
        ),
        config,
    )
    values = graph.get_state(config).values
    print_final_artifacts(values)
    return values


def main():
    parser = argparse.ArgumentParser(
        description="Industrial RCA evidence-driven agent prototype"
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Explicitly approve local simulation drafts",
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Review with a custom root cause statement",
    )
    parser.add_argument(
        "--reject", action="store_true", help="Reject the model's proposed diagnosis"
    )
    parser.add_argument(
        "--use-deepseek",
        action="store_true",
        default=True,
        help="Use the configured provider (default)",
    )
    parser.add_argument(
        "--no-deepseek",
        dest="use_deepseek",
        action="store_false",
        help="Disable model investigation",
    )
    parser.add_argument(
        "--deepseek-model",
        default=None,
        help="Provider model; defaults to DEEPSEEK_MODEL",
    )
    parser.add_argument(
        "--test-deepseek",
        action="store_true",
        help="Test provider connectivity and exit",
    )
    parser.add_argument(
        "--server", action="store_true", help="Start the FastAPI server"
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.server:
        import uvicorn

        uvicorn.run("industrial_rca.api:api_app", host="0.0.0.0", port=args.port)
        return
    client = DeepSeekClient(default_model=args.deepseek_model)
    if args.test_deepseek:
        console.print_json(json.dumps(client.test_connection()))
        return
    graph = create_rca_graph(decision_client=client)
    run_baseline_verification(graph, generate_normal_scenario())
    decision = (
        "reject"
        if args.reject
        else "override"
        if args.override
        else "approve"
        if args.auto_approve
        else None
    )
    run_fault_investigation(
        graph,
        generate_fault_scenario(),
        auto_decision=decision,
        use_deepseek=args.use_deepseek,
        deepseek_model=args.deepseek_model,
    )


if __name__ == "__main__":
    main()
