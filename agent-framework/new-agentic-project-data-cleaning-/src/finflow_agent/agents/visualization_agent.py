"""Visualization agent scaffolding.

The visualization agent is intentionally disabled in this version. Per the
agent-pipeline-hardening spec (Component 4 / Visualization scaffolding), only
the Pydantic param model is wired so the agent registry keeps a uniform shape
alongside the cleaning, filter, and reporting agents. The agent class itself
remains a placeholder whose ``execute`` returns a controlled ``failed``
``AgentResult`` and never produces a chart.

Real wiring of the enable flag (``ENABLE_VISUALIZATION``) happens in a later
task (see tasks 1.1 and 13.1). This module deliberately avoids reading any
environment variable so it can be safely imported by ``bootstrap.py`` today.
"""

from pydantic import BaseModel

from finflow_agent.registry import registry, AgentSpec
from finflow_agent.state import AgentResult
from finflow_agent.operations.schemas import VisualizationOperationPlan


# Canonical disabled-message used by the compiler, validator, and orchestrator
# when visualization is requested while the agent is disabled.
VISUALIZATION_DISABLED_MESSAGE = (
    "visualization_agent is not enabled in this version"
)


class VisualizationAgentParams(BaseModel):
    """Pydantic param model for the visualization agent.

    The model is registered alongside the agent so the engine's per-step param
    re-validation (Requirement 4.1, Requirement 10.6) treats the visualization
    step uniformly with the other agents. The agent itself is disabled, so this
    model is only ever consumed by the validator path.
    """

    plan: VisualizationOperationPlan


@registry.register
class VisualizationAgent:
    """Disabled placeholder agent.

    Keeping the registration ensures the plan validator does not surface
    ``"Unknown agent: visualization_agent"`` for plans that legitimately
    reference the slot (e.g., when a future enable flag flips on). Today,
    ``execute`` always returns a controlled ``failed`` ``AgentResult`` with the
    canonical message; no chart is ever produced.
    """

    spec = AgentSpec(
        name="visualization_agent",
        description=(
            "Disabled visualization agent placeholder. Returns a controlled "
            "failed AgentResult; never renders a chart."
        ),
        stage="visualize",
        accepts=["dataframe"],
        produces=["chart_spec"],
        params_schema={
            "plan": {"type": "object"}
        },
    )
    # Pydantic params model picked up by the registry so the validator and
    # engine can re-validate `step.params` uniformly with the other agents
    # (Requirement 10.6 / design Component 4). The agent itself is disabled
    # by default; this binding only governs the validator path.
    params_model = VisualizationAgentParams

    def execute(self, params: dict, input_data: dict) -> AgentResult:
        return AgentResult(
            status="failed",
            error_message=VISUALIZATION_DISABLED_MESSAGE,
        )
