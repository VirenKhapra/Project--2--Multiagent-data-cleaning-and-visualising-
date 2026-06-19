import asyncio
import os
import sys
import json

# Add agent path
sys.path.insert(0, os.path.abspath(r"c:\Users\acer\Documents\agentic_Ai-main\agent-framework\new-agentic-project-data-cleaning-\src"))

from finflow_agent.orchestrator import Orchestrator
from finflow_agent.engine import ExecutionEngine
from finflow_agent.state import ExecutionPlan, PlanStep

def test_dag_traversal():
    import finflow_agent.agents.ingestion_agent
    import finflow_agent.agents.cleaning_agent
    import finflow_agent.agents.reporting_agent
    
    plan = ExecutionPlan(
        steps=[
            PlanStep(step_id="step1", agent="ingestion_agent", depends_on=[], params={"file_path": "dummy.csv", "file_type": "csv"}),
            PlanStep(step_id="step2", agent="cleaning_agent", depends_on=["step1"], params={}),
            PlanStep(step_id="step3", agent="reporting_agent", depends_on=["step2"], params={})
        ]
    )
    
    with open("dummy.csv", "w") as f:
        f.write("A,B\n1,2")
        
    engine = ExecutionEngine()
    
    import finflow_agent.registry
    from finflow_agent.state import PipelineState, AgentResult
    
    # Replace actual execution method to not make actual LLM calls
    for name in finflow_agent.registry.registry._agents:
        cls = finflow_agent.registry.registry.get_agent_class(name)
        cls.execute = lambda self, params, state: AgentResult(status="success", data=f"{name}_output", error_message="")

    
    result = engine.execute(plan)
    print("Execution Result:", json.dumps(result, indent=2))
    
    if result.get("status") == "complete":
        print("DAG Traversal successful!")
    else:
        print("DAG Traversal failed.")

if __name__ == "__main__":
    test_dag_traversal()
