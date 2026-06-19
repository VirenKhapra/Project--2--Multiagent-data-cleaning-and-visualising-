import pytest


def test_orchestrator_rejects_legacy_steps_response(monkeypatch, bootstrap_agents, tmp_path):
    from finflow_agent.planning.orchestrator import Orchestrator

    def fake_llm_response(*args, **kwargs):
        return {
            "steps": [
                {
                    "step_id": "ingest",
                    "agent": "ingestion_agent",
                    "params": {
                        "resolved_file_path": str(tmp_path / "input.csv"),
                        "file_type": "csv",
                    },
                    "depends_on": [],
                    "input_from": [],
                    "output_key": "df_ingested",
                }
            ]
        }

    import finflow_agent.orchestrator as root_orchestrator
    monkeypatch.setattr(root_orchestrator, "call_groq_json", fake_llm_response)

    result = Orchestrator().build_plan(
        instruction="make a csv report",
        file_path=str(tmp_path / "input.csv"),
        file_name="input.csv",
        output_format="csv",
    )

    assert isinstance(result, dict)
    assert result["status"] == "quarantined"
    assert "steps" in result["reason"].lower() or "planintent" in result["reason"].lower()


@pytest.mark.parametrize(
    "field_name, flag_name, expected_error",
    [
        ("cleaning_plan", "needs_cleaning", "cleaning_plan"),
        ("filter_plan", "needs_filtering", "filter_plan"),
        ("calculation_plan", "needs_calculation", "calculation_plan"),
        ("visualization_plan", "needs_visualization", "visualization_plan"),
    ],
)
def test_compiler_rejects_missing_requested_stage_plan(
    field_name,
    flag_name,
    expected_error,
    bootstrap_agents,
    tmp_path,
):
    from finflow_agent.planning.intent_schema import PlanIntent
    from finflow_agent.planning.compiler import compile_intent_to_plan

    kwargs = {
        "output_format": "xlsx",
        flag_name: True,
        field_name: None,
    }

    intent = PlanIntent(**kwargs)

    with pytest.raises(ValueError, match=expected_error):
        compile_intent_to_plan(
            intent=intent,
            resolved_file_path=str(tmp_path / "input.csv"),
            file_type="csv",
            output_dir=str(tmp_path / "outputs"),
            file_prefix="test",
        )


def test_validate_plan_rejects_missing_input_from(bootstrap_agents):
    from finflow_agent.state import ExecutionPlan, PlanStep
    from finflow_agent.planning.validators import validate_plan

    plan = ExecutionPlan(
        steps=[
            PlanStep(
                step_id="ingest",
                agent="ingestion_agent",
                params={"resolved_file_path": "x.csv", "file_type": "csv"},
                depends_on=[],
                input_from=[],
                output_key="df_ingested",
            ),
            PlanStep(
                step_id="report",
                agent="reporting_agent",
                params={
                    "plan": {"output_format": "xlsx"},
                    "output_dir": "outputs",
                    "file_prefix": "test",
                },
                depends_on=["ingest"],
                input_from=["df_missing"],
                output_key="report_output",
            ),
        ]
    )

    is_valid, error = validate_plan(plan)
    assert not is_valid
    assert "input_from" in error
    assert "df_missing" in error
