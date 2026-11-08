from industrial_rca.data.telemetry_generator import generate_fault_scenario
from industrial_rca.graph.workflow import create_rca_graph
from industrial_rca.main import run_fault_investigation


def test_cli_handles_log_reset_and_an_inconclusive_run():
    result = run_fault_investigation(
        create_rca_graph(),
        generate_fault_scenario(duration_sec=300),
        thread_id="cli-boundary",
        use_deepseek=False,
    )
    assert result["pipeline_status"] == "INCONCLUSIVE"
    assert result.get("sap_work_order") is None
