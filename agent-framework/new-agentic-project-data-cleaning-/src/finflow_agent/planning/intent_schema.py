from typing import Literal, Optional
from pydantic import BaseModel
from finflow_agent.operations.schemas import (
    CleaningOperationPlan,
    FilterOperationPlan,
    CalculationOperationPlan,
    VisualizationOperationPlan
)

class PlanIntent(BaseModel):
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    needs_cleaning: bool = False
    needs_filtering: bool = False
    needs_calculation: bool = False
    needs_visualization: bool = False
    output_format: Literal["xlsx", "csv", "json", "txt"] = "xlsx"

    cleaning_plan: Optional[CleaningOperationPlan] = None
    filter_plan: Optional[FilterOperationPlan] = None
    calculation_plan: Optional[CalculationOperationPlan] = None
    visualization_plan: Optional[VisualizationOperationPlan] = None
    reporting_title: Optional[str] = None
    sheet_name: Optional[str] = None
