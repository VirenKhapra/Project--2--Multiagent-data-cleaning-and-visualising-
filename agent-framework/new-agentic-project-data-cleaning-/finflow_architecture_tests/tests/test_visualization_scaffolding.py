"""End-to-end tests for the disabled-by-default visualization agent scaffold.

Exercises the four layers (agent class, compiler, validator, orchestrator)
to make sure the visualization slot is registered, the canonical disabled
message flows through every layer, and flipping ``ENABLE_VISUALIZATION``
opens the gate cleanly.

Requirements: 9.1, 9.2, 9.3, 11.6.
"""

from pathlib import Path
from typing import Optional

import pytest

from finflow_agent.agents.visualization_agent import (
    VISUALIZATION_DISABLED_MESSAGE,
    VisualizationAgent,
    VisualizationAgentParams,
)
from finflow_agent.planning.compiler import (
    VisualizationDisabledError,
    compile_intent_to_plan,
)
from finflow_agent.planning.intent_schema import PlanIntent
from finflow_agent.planning.orchestrator import Orchestrator
from finflow_agent.planning.validators import validate_plan
from finflow_agent.registry import registry
from finflow_agent.state import ExecutionPlan, PlanStep
from finflow_agent.tools.config import (
    get_enable_visualization,
    reset_config_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_visualization_flag(monkeypatch, *, enabled: bool) -> None:
    """Flip ``ENABLE_VISUALIZATION`` and re-bootstrap the registry.

    The conftest ``bootstrap_agents`` fixture only runs once per test, so any
    test that wants to flip the flag mid-test must:

    1. Monkeypatch the env var so the typed accessor reads the new value.
    2. Reset the config cache so ``get_enable_visualization`` re-reads env.
    3. Re-invoke ``bootstrap_agents`` so the visualization spec's
       ``enabled`` flag is re-synchronized with the (cached) config value.

    Wrapping it here keeps each test focused on the assertions.
    """
    from finflow_agent.bootstrap import bootstrap_agents as bootstrap

    monkeypatch.setenv("ENABLE_VISUALIZATION", "true" if enabled else "false")
    reset_config_cache()
    bootstrap()


def _valid_visualization_plan_dict() -> dict:
    """Return a minimal, schema-valid ``visualization_plan`` payload."""
    return {
        "charts": [
            {
                "type": "bar",
                "x": "col_a",
                "y": "col_b",
                "title": "Test",
            }
        ]
    }


def _make_plan_intent(*, needs_visualization: bool) -> PlanIntent:
    """Build a PlanIntent that asks for a visualization step."""
    kwargs = {
        "needs_visualization": needs_visualization,
        "output_format": "xlsx",
    }
    if needs_visualization:
        kwargs["visualization_plan"] = _valid_visualization_plan_dict()
    return PlanIntent(**kwargs)


def _hand_crafted_visualization_plan() -> ExecutionPlan:
    """A 3-step ExecutionPlan: ingest -> visualize -> report.

    Used by the validator tests. Every other validator check is satisfied
    so the disabled / enabled gate is the only deciding factor.
    """
    return ExecutionPlan(
        steps=[
            PlanStep(
                step_id="ingest",
                agent="ingestion_agent",
                params={
                    "resolved_file_path": "x.csv",
                    "file_type": "csv",
                },
                depends_on=[],
                input_from=[],
                output_key="df_ingested",
            ),
            PlanStep(
                step_id="visualize",
                agent="visualization_agent",
                params={"plan": _valid_visualization_plan_dict()},
                depends_on=["ingest"],
                input_from=["df_ingested"],
                output_key="df_visualized",
            ),
            PlanStep(
                step_id="report",
                agent="reporting_agent",
                params={
                    "plan": {"output_format": "xlsx"},
                    "output_dir": "outputs",
                    "file_prefix": "test",
                },
                depends_on=["visualize"],
                input_from=["df_visualized"],
                output_key="report_output",
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Auto-clear visualization config so each test starts from a known state.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_visualization_config(monkeypatch):
    """Strip ``ENABLE_VISUALIZATION`` and reset the config cache before/after.

    Without this the module-level cache from a previous test could leak in
    and silently invert the meaning of ``"flag unset = default false"``.
    """
    monkeypatch.delenv("ENABLE_VISUALIZATION", raising=False)
    reset_config_cache()
    yield
    reset_config_cache()


# ---------------------------------------------------------------------------
# 1. Agent registration with default-disabled flag
# ---------------------------------------------------------------------------


def test_visualization_agent_is_registered_but_disabled_by_default(bootstrap_agents):
    """The slot exists (no ``ValueError``) and ``enabled`` is False by default.

    This is what lets the validator return the canonical disabled message
    instead of ``"Unknown agent: visualization_agent"``.
    """
    spec = registry.get_spec("visualization_agent")
    assert spec is not None
    assert spec.enabled is False
    # Sanity: the typed config accessor agrees with the spec.
    assert get_enable_visualization() is False


# ---------------------------------------------------------------------------
# 2. Direct agent.execute() returns the canonical failed envelope
# ---------------------------------------------------------------------------


def test_visualization_agent_execute_returns_disabled_message():
    """Agent.execute({}, {}) must surface the canonical message."""
    result = VisualizationAgent().execute({}, {})

    assert result.status == "failed"
    assert result.error_message == "visualization_agent is not enabled in this version"
    # Defensive: the constant the rest of the system uses must match.
    assert result.error_message == VISUALIZATION_DISABLED_MESSAGE


# ---------------------------------------------------------------------------
# 3. Flag flip on -> spec.enabled becomes True
# ---------------------------------------------------------------------------


def test_visualization_enabled_when_flag_is_true(monkeypatch):
    _set_visualization_flag(monkeypatch, enabled=True)

    assert get_enable_visualization() is True
    assert registry.get_spec("visualization_agent").enabled is True


# ---------------------------------------------------------------------------
# 4. Compiler raises VisualizationDisabledError when flag is off
# ---------------------------------------------------------------------------


def test_compiler_raises_visualization_disabled_error_when_flag_off(
    monkeypatch, tmp_path
):
    _set_visualization_flag(monkeypatch, enabled=False)

    intent = _make_plan_intent(needs_visualization=True)

    with pytest.raises(VisualizationDisabledError) as excinfo:
        compile_intent_to_plan(
            intent=intent,
            resolved_file_path=str(tmp_path / "input.csv"),
            file_type="csv",
            output_dir=str(tmp_path / "outputs"),
            file_prefix="test",
        )

    assert "visualization_agent is not enabled in this version" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 5. Validator rejects a disabled visualization step
# ---------------------------------------------------------------------------


def test_validator_rejects_disabled_visualization_step(monkeypatch):
    _set_visualization_flag(monkeypatch, enabled=False)

    plan = _hand_crafted_visualization_plan()
    is_valid, error = validate_plan(plan)

    assert is_valid is False
    assert "visualization_agent is not enabled in this version" in error


# ---------------------------------------------------------------------------
# 6. Orchestrator quarantines a visualization request when disabled
# ---------------------------------------------------------------------------


def test_orchestrator_quarantines_visualization_request_when_disabled(
    monkeypatch, tmp_path
):
    _set_visualization_flag(monkeypatch, enabled=False)

    fake_plan_intent_dict = {
        "is_quarantined": False,
        "quarantine_reason": None,
        "needs_cleaning": False,
        "needs_filtering": False,
        "needs_calculation": False,
        "needs_visualization": True,
        "output_format": "xlsx",
        "cleaning_plan": None,
        "filter_plan": None,
        "calculation_plan": None,
        "visualization_plan": _valid_visualization_plan_dict(),
        "reporting_title": None,
        "sheet_name": None,
    }

    def fake_call_groq_json(*args, **kwargs):
        return fake_plan_intent_dict

    import finflow_agent.orchestrator as root_orchestrator

    monkeypatch.setattr(root_orchestrator, "call_groq_json", fake_call_groq_json)

    result = Orchestrator().build_plan(
        instruction="please make me a chart",
        file_path=str(tmp_path / "input.csv"),
        file_name="input.csv",
        output_format="xlsx",
    )

    assert isinstance(result, dict), (
        f"Expected a quarantine dict, got {type(result).__name__}: {result!r}"
    )
    assert result["status"] == "quarantined"
    assert "visualization_agent is not enabled in this version" in result["reason"]


# ---------------------------------------------------------------------------
# 7. Agent does not render charts and never imports chart libraries
# ---------------------------------------------------------------------------


def test_visualization_agent_does_not_render_chart(tmp_path):
    """Behavioral + static check: no chart is ever produced."""
    import pandas as pd

    df = pd.DataFrame({"col_a": [1, 2, 3], "col_b": [4, 5, 6]})

    # Snapshot the output dir before/after to make sure the agent does not
    # write any artifact when the disabled placeholder is invoked.
    output_dir = tmp_path / "render_check"
    output_dir.mkdir()
    files_before = sorted(output_dir.iterdir())

    result = VisualizationAgent().execute({}, {"input_dataframe": df})

    files_after = sorted(output_dir.iterdir())
    assert files_before == files_after, (
        "Visualization agent must not write any file; "
        f"found new entries: {set(files_after) - set(files_before)}"
    )
    assert result.status == "failed"
    assert result.error_message == VISUALIZATION_DISABLED_MESSAGE

    # Static check: no chart-rendering library is imported by the module
    # source, and no chart-API symbol appears anywhere in the file.
    import finflow_agent.agents.visualization_agent as viz_module

    source_path = Path(viz_module.__file__)
    source = source_path.read_text(encoding="utf-8")

    forbidden_imports = [
        "import matplotlib",
        "from matplotlib",
        "import plotly",
        "from plotly",
        "import seaborn",
        "from seaborn",
        "import xlsxwriter",
        "from xlsxwriter",
    ]
    for needle in forbidden_imports:
        assert needle not in source, (
            f"Visualization agent source must not contain '{needle}'; "
            f"chart rendering is disabled."
        )

    forbidden_symbols = [
        "add_chart",
        "insert_chart",
        "Figure",
        "pyplot",
        "savefig",
    ]
    for needle in forbidden_symbols:
        assert needle not in source, (
            f"Visualization agent source must not contain '{needle}'; "
            f"chart rendering is disabled."
        )

    # ``Chart`` is matched as a whole word so we do not trip on substrings
    # like ``ChartSpec`` that might legitimately be referenced via type
    # imports in future revisions.
    import re

    assert re.search(r"\bChart\b", source) is None, (
        "Visualization agent source must not reference a bare 'Chart' "
        "symbol; chart rendering is disabled."
    )


# ---------------------------------------------------------------------------
# 8. Compiler emits a visualize step when the flag is on
# ---------------------------------------------------------------------------


def test_compiler_emits_visualization_step_when_flag_enabled(monkeypatch, tmp_path):
    _set_visualization_flag(monkeypatch, enabled=True)

    intent = _make_plan_intent(needs_visualization=True)
    plan = compile_intent_to_plan(
        intent=intent,
        resolved_file_path=str(tmp_path / "input.csv"),
        file_type="csv",
        output_dir=str(tmp_path / "outputs"),
        file_prefix="test",
    )

    visualization_steps = [s for s in plan.steps if s.agent == "visualization_agent"]
    assert len(visualization_steps) == 1, (
        f"Expected exactly one visualization step, got {len(visualization_steps)} "
        f"in plan with steps {[s.agent for s in plan.steps]}"
    )

    viz_step = visualization_steps[0]
    assert viz_step.output_key == "df_visualized"

    # Visualization must precede the trailing reporting step.
    agents_in_order = [s.agent for s in plan.steps]
    viz_index = agents_in_order.index("visualization_agent")
    report_index = agents_in_order.index("reporting_agent")
    assert viz_index < report_index, (
        f"Visualization step must precede reporting; got order {agents_in_order}"
    )


# ---------------------------------------------------------------------------
# 9. Validator accepts the same plan when the flag is on
# ---------------------------------------------------------------------------


def test_validate_plan_accepts_visualization_when_enabled(monkeypatch):
    _set_visualization_flag(monkeypatch, enabled=True)

    plan = _hand_crafted_visualization_plan()
    is_valid, error = validate_plan(plan)

    assert is_valid is True, f"Validator rejected an enabled-visualization plan: {error}"
    assert error == ""


# ---------------------------------------------------------------------------
# 10. Visualization agent's Pydantic params model is registered alongside it
# ---------------------------------------------------------------------------


def test_visualization_agent_param_model_is_registered(bootstrap_agents):
    assert registry.has_params_model("visualization_agent") is True, (
        "Expected VisualizationAgentParams to be registered alongside the "
        "visualization_agent so the engine's per-step param re-validation "
        "treats it uniformly with the other agents."
    )
    assert registry.get_params_model("visualization_agent") is VisualizationAgentParams
