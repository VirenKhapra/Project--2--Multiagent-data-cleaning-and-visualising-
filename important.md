You are a senior software engineer and agentic AI architect working on the FinFlow repository.

Your task is to inspect the existing repository, read the uploaded/available architecture documents, and implement the next long-term-safe version of the FinFlow agent layer. Do not make superficial patches. Do not rewrite the whole system unnecessarily. Preserve the current architecture unless a file is clearly obsolete according to the architecture documents.

You must work carefully, incrementally, and with no unsupported assumptions.

============================================================
PRIMARY GOAL
============

FinFlow is a finance workflow console where a user uploads a file, writes a natural language instruction, chooses an output format, and receives a downloadable artifact.

The current system already has major plumbing in place:

* React frontend
* FastAPI backend
* PostgreSQL
* Redis / ARQ dispatch
* Agent service
* LangGraph-style DAG engine
* Orchestrator
* Registered agents
* Backend callback
* Download endpoint
* Single submission status model
* Audit logging foundation

The missing part is the agent execution layer.

Current agents are mostly deterministic skeletons. They do not yet produce rich telemetry, operation plans, safe tool execution, or useful frontend milestone summaries.

You must evolve the system toward a safe agentic workflow, but you must NOT introduce unsafe autonomous execution.

The correct direction is:

Orchestrator creates DAG
↓
Engine validates DAG
↓
Each agent receives upstream state
↓
Agent produces or receives a structured operation plan
↓
Operation plan is validated
↓
Safe deterministic executor applies transformations
↓
Agent returns AgentResult with data + summary + metrics + warnings + operations_applied
↓
Backend callback stores rich summary
↓
Frontend milestone UI receives useful agent summaries

Do NOT implement unrestricted Python REPL execution as the default path.

============================================================
NON-NEGOTIABLE ARCHITECTURAL RULES
==================================

Follow these rules strictly:

1. Keep LangGraph / deterministic DAG architecture.
2. Do NOT use LangChain AgentExecutor.
3. Do NOT use initialize_agent.
4. Do NOT add ReAct loops for normal production execution.
5. Do NOT allow agents to decide the next DAG step.
6. The Orchestrator plans upfront.
7. The execution engine validates before execution.
8. The engine must keep cycle detection.
9. The engine must keep stage ordering validation.
10. PipelineState must remain in-memory.
11. PipelineState.data must be keyed by step_id, not agent name.
12. Intermediate dataframe outputs must not be written to PostgreSQL as permanent records.
13. PostgreSQL stores final status, output path, summary JSON, audit logs, and final structured records only.
14. partial must map to failed at submission level.
15. unsupported domain or unsupported capability must become quarantined.
16. Ingestion Agent is the only file-format-aware agent.
17. Cleaning Agent owns normalization.
18. Filter Agent owns row and column selection.
19. Calculation Agent owns math/statistical operations.
20. Visualization Agent owns chart plans/objects.
21. Reporting Agent owns final display formatting.
22. PNG is internal only, not a user-facing output format.
23. User downloads must go through backend endpoint, not directly from agent container.
24. Do not add new agents casually. Agent cap is 15 maximum.
25. Do not add semantic retrieval for agent selection.
26. Do not allow LLM-generated raw pandas code to execute in the normal path.
27. If an advanced Python REPL mode is added later, it must be disabled by default and admin-only. For this task, do not implement that mode unless already scaffolded and explicitly safe.

============================================================
IMPORTANT CLARIFICATION POLICY
==============================

Do not assume missing file names, missing directories, or missing behavior.

Before editing, inspect the repository.

If a required file path from this prompt does not exist, search for its equivalent.

If no equivalent exists, create the file only if it clearly belongs in the current architecture.

If there are conflicting files or duplicate agentic_file.md versions, inspect both and choose the newest/current project copy. Do not silently ignore conflicts.

If you cannot determine the correct file, stop and ask for clarification.

If the user said “executive file,” interpret that only as “the project progress/tracking file” if a progress.md file exists. If progress.md exists, update progress.md. If no progress.md exists, stop and ask which file should track progress.

============================================================
MANDATORY PROGRESS TRACKING RULE
================================

You must update progress.md as an implementation ledger.

After every 5 meaningful changes, append a short entry to progress.md.

A meaningful change means one of these:

* New file created
* Existing file refactored
* Schema added
* Executor added
* Agent changed
* Test added
* API/callback behavior changed
* Frontend mapping changed
* Requirements/dependency changed
* Bug fixed

The progress entry must include:

* Date/time if easily available
* Change batch number
* Files touched
* What changed
* Why it changed
* Whether tests were added or updated
* Any risk or follow-up

Do not spam progress.md after every tiny line edit. Update after every 5 meaningful changes.

Example progress entry format:

## Implementation Batch 1 — Operation Plan Foundation

Files touched:

* src/finflow_agent/state.py
* src/finflow_agent/operations/schemas.py
* src/finflow_agent/operations/validators.py
* src/finflow_agent/tools/dataframe_profile.py
* tests/test_operation_schemas.py

Changes:

* Added typed operation plan schemas.
* Added dataframe profiling utility.
* Added validation layer for supported operations.
* Expanded tests for valid/invalid operations.

Why:

* Agents need to become prompt-aware and auditable without executing arbitrary LLM Python code.

Tests:

* Added unit tests for schema validation and dataframe profiling.

Risks / follow-up:

* Existing agent return envelopes may need compatibility adjustment.

============================================================
REQUIRED TOOLING AND LIBRARIES
==============================

Before adding dependencies, inspect existing pyproject.toml, requirements.txt, package.json, Dockerfiles, and compose files. Do not duplicate dependencies. Add only what is missing and actually used.

Python backend / agent service tools that may be needed:

Core data:

* pandas
* numpy
* openpyxl
* xlsxwriter
* pydantic
* python-dateutil
* pytz or zoneinfo from standard library
* decimal from standard library
* csv from standard library
* json from standard library
* pathlib from standard library
* tempfile from standard library
* hashlib from standard library
* mimetypes from standard library
* uuid from standard library

File ingestion:

* pandas.read_csv
* pandas.read_excel
* pandas.read_json
* openpyxl for xlsx
* pypdf or PyPDF2 for PDF text extraction, depending on existing dependency
* json standard library
* csv standard library

Data cleaning:

* pandas DataFrame operations
* pandas dtype conversion
* pandas.to_datetime
* pandas.to_numeric
* decimal.Decimal for precise finance formatting where needed
* regex via re standard library
* numpy for numerical operations

Data validation:

* pydantic BaseModel
* pydantic Field
* Literal / Enum types
* jsonschema only if already present or clearly needed
* custom validators preferred over loose dicts

Charts and reports:

* openpyxl charts as default
* xlsxwriter as fallback for advanced Excel charts
* reportlab for PDF output if already used or needed
* matplotlib only if needed for PDF chart image generation; do not introduce unless required
* io.BytesIO standard library
* base64 only if needed for chart embedding

API / service:

* FastAPI
* SQLAlchemy / SQLModel depending on current repo
* asyncpg
* arq
* redis
* httpx for callbacks if already used
* uvicorn

LLM:

* Groq client or langchain-groq if existing architecture already uses it
* langchain-core only for prompts, output parsers, structured output, and low-level utilities
* Do not use AgentExecutor
* Do not use initialize_agent
* Do not use create_react_agent as default
* Do not use PythonAstREPLTool as default

Testing:

* pytest
* pytest-asyncio if async tests exist
* tempfile
* pathlib
* pandas testing helpers
* snapshot-style JSON fixtures if helpful

Frontend:

* React
* Existing API client
* Existing milestone/stepper components
* Do not rewrite UI framework
* Only adjust mapping to consume richer agent summaries if needed

============================================================
REQUIRED FILES / MODULES TO SEARCH FOR FIRST
============================================

Search the repository for these paths or equivalents:

Agent service:

* src/finflow_agent/orchestrator.py
* src/finflow_agent/engine.py
* src/finflow_agent/state.py
* src/finflow_agent/registry.py
* src/finflow_agent/agents/ingestion_agent.py
* src/finflow_agent/agents/cleaning_agent.py
* src/finflow_agent/agents/filter_agent.py
* src/finflow_agent/agents/calculation_agent.py
* src/finflow_agent/agents/visualization_agent.py
* src/finflow_agent/agents/reporting_agent.py
* src/finflow_agent/tools/output.py
* src/finflow_agent/llm.py
* src/finflow_agent/api.py

Backend:

* backend/app/models.py
* backend/app/schemas.py
* backend/app/api/uploads.py
* backend/app/api/agent.py
* backend/app/services/agent_dispatcher.py
* backend/app/services/submission_results.py
* backend/app/services/websocket_manager.py
* backend/app/services/audit.py

Frontend:

* frontend/src/api/finflow.js
* frontend/src/components/ProgressMilestones.jsx
* frontend/src/pages/SubmissionsPage.jsx
* frontend/src/pages/Dashboard.jsx
* frontend/src/pages/UploadCenter.jsx
* frontend/src/hooks/useLiveJobRefresh.js

Project tracking:

* progress.md
* agentic_file.md
* README.md
* requirements.txt
* pyproject.toml
* docker-compose.yml or compose.yaml

If actual paths differ, adapt to the repository’s current layout and mention the path mapping in progress.md.

============================================================
HIGH-LEVEL IMPLEMENTATION OBJECTIVE
===================================

Refactor the agent layer into a safe operation-plan architecture.

Do not make agents free-running autonomous agents.

Do not make LLMs directly mutate DataFrames.

Instead:

* Agents may use LLMs later to produce structured JSON operation plans.
* For now, implement the safe architecture so both deterministic params and future LLM JSON can flow through the same validators and executors.
* The actual execution must be deterministic Python code using whitelisted operations.

This avoids future patching because every future LLM enhancement will use the same operation plan schemas and safe executors.

============================================================
IMPLEMENTATION PHASES
=====================

Implement in this order.

## PHASE 1 — Inspect current repo and document baseline

1. Inspect all relevant files.
2. Identify current agent signatures.
3. Identify AgentResult model location.
4. Identify PipelineState model location.
5. Identify how engine dispatches agents.
6. Identify how callback summary is created.
7. Identify how frontend consumes summary / agentSummaries.
8. Do not edit yet until you understand the flow.
9. Update progress.md with baseline findings if progress.md exists.

## PHASE 2 — Expand AgentResult safely

Find the AgentResult model.

If AgentResult currently has:

* status
* error_message
* data

Extend it backward-compatibly to include:

* summary: str | None = None
* metrics: dict[str, Any] = {}
* operations_applied: list[dict[str, Any]] = []
* warnings: list[str] = []
* artifacts: dict[str, Any] = {}

Use safe default factories for mutable fields.

Do not break existing code that only reads status/data/error_message.

Expected model shape:

class AgentResult(BaseModel):
status: Literal["success", "partial", "failed"]
error_message: str | None = None
data: Any = None
summary: str | None = None
metrics: dict[str, Any] = Field(default_factory=dict)
operations_applied: list[dict[str, Any]] = Field(default_factory=list)
warnings: list[str] = Field(default_factory=list)
artifacts: dict[str, Any] = Field(default_factory=dict)

If Pydantic v1 is used, use compatible syntax.

If Python version does not support dict[str, Any], use Dict[str, Any].

Update engine/callback serialization to preserve these fields.

## PHASE 3 — Add Operation Plan foundation

Create a package, unless an equivalent already exists:

src/finflow_agent/operations/

Files:

* **init**.py
* schemas.py
* validators.py
* executor.py
* cleaning_ops.py
* filter_ops.py
* calculation_ops.py
* visualization_ops.py
* reporting_ops.py

If the repo layout differs, place this package beside the agents and engine.

Operation schemas must be strict. Prefer Pydantic models.

Create these plan models:

1. CleaningOperationPlan
2. FilterOperationPlan
3. CalculationOperationPlan
4. VisualizationOperationPlan
5. ReportingOperationPlan

Each plan should include:

* operations or charts where applicable
* rationale: optional string
* warnings: list[str]
* confidence: optional float between 0 and 1 if easy to validate

Do not allow arbitrary code strings.

Do not allow pandas query strings.

Do not allow SQL strings.

Do not allow shell commands.

## PHASE 4 — Define allowed cleaning operations

Implement safe cleaning operations.

Allowed cleaning operation types:

* trim_whitespace
* normalize_column_names
* drop_duplicates
* fill_nulls
* drop_nulls
* normalize_date
* normalize_currency
* normalize_number
* normalize_text_case
* replace_values
* strip_currency_symbols
* remove_commas_from_numbers
* coerce_column_type
* remove_empty_rows
* remove_empty_columns
* rename_columns
* reorder_columns

Each operation must have a strict schema.

Examples:

TrimWhitespaceOperation:

* type = "trim_whitespace"
* columns: list[str] | "**all_string_columns**"

NormalizeColumnNamesOperation:

* type = "normalize_column_names"
* style: "snake_case" | "lowercase" | "preserve"

DropDuplicatesOperation:

* type = "drop_duplicates"
* subset: list[str] | None
* keep: "first" | "last"

FillNullsOperation:

* type = "fill_nulls"
* columns: list[str]
* strategy: "zero" | "empty_string" | "mean" | "median" | "mode" | "constant"
* value: optional scalar for constant

DropNullsOperation:

* type = "drop_nulls"
* columns: list[str] | None
* how: "any" | "all"

NormalizeDateOperation:

* type = "normalize_date"
* column: str
* target_format: "YYYY-MM-DD"
* dayfirst: bool | None
* errors: "raise" | "coerce"

NormalizeCurrencyOperation:

* type = "normalize_currency"
* column: str
* precision: int = 2
* strip_symbols: bool = true
* negative_parentheses: bool = true

NormalizeNumberOperation:

* type = "normalize_number"
* column: str
* precision: int | None
* remove_commas: bool = true

NormalizeTextCaseOperation:

* type = "normalize_text_case"
* columns: list[str]
* case: "lower" | "upper" | "title"

ReplaceValuesOperation:

* type = "replace_values"
* column: str
* mapping: dict[str, Any]

CoerceColumnTypeOperation:

* type = "coerce_column_type"
* column: str
* target_type: "string" | "integer" | "float" | "decimal" | "date" | "boolean"
* errors: "raise" | "coerce"

## PHASE 5 — Define allowed filter operations

Implement FilterOperationPlan.

Allowed filter operators:

* eq
* neq
* gt
* gte
* lt
* lte
* contains
* not_contains
* starts_with
* ends_with
* between
* in
* not_in
* is_null
* is_not_null

Filter plan fields:

* conditions: list[FilterCondition]
* logic: "AND" | "OR"
* select_columns: list[str] | None
* sort_by: list[SortSpec] | None
* limit: int | None

FilterCondition:

* column: str
* operator: allowed operator
* value: Any | None
* value_to: Any | None for between
* case_sensitive: bool = false for text operators

SortSpec:

* column: str
* direction: "asc" | "desc"

Validation:

* All referenced columns must exist.
* between requires value and value_to.
* in/not_in requires list value.
* is_null/is_not_null must not require value.
* limit must be positive.

## PHASE 6 — Define allowed calculation operations

Implement CalculationOperationPlan.

Allowed calculation operation types:

* sum
* mean
* median
* min
* max
* count
* count_distinct
* variance
* standard_deviation
* group_sum
* group_mean
* group_count
* running_total
* percentage_change
* difference
* ratio
* custom_formula_whitelisted

Do not allow arbitrary formulas in phase 1.

For custom_formula_whitelisted, only implement if existing requirements clearly need it. If implemented, support only a whitelist of formula names and arguments, not raw Python expressions.

CalculationOperation fields:

* type
* column
* group_by
* output_column
* date_column
* period
* precision

Validation:

* Numeric operations require numeric-compatible columns.
* group operations require group_by columns to exist.
* percentage_change requires date column and value column.
* running_total requires value column and optional sort/date column.

## PHASE 7 — Define allowed visualization operations

Implement VisualizationOperationPlan.

Allowed chart types:

* bar
* line
* pie
* scatter
* area
* stacked_bar

ChartSpec fields:

* type
* x
* y
* series
* title
* x_axis_title
* y_axis_title
* source_step_id optional
* max_categories optional
* sort optional

Validation:

* x column exists.
* y column exists and is numeric-compatible where required.
* pie chart should have category and value.
* Do not generate a standalone PNG output for the user.
* PNG can be used only as internal intermediate if PDF generation requires it.

Rendering:

* openpyxl is default for XLSX charts.
* xlsxwriter fallback can be used if openpyxl cannot render requested chart.
* Keep renderer separate from planner.

## PHASE 8 — Define reporting operation plan

Implement ReportingOperationPlan.

Supported output formats:

* xlsx
* csv
* json
* txt
* pdf

Do not silently default unsupported formats to xlsx.

Plan fields:

* output_format
* include_summary: bool
* include_raw_data: bool
* include_cleaning_log: bool
* include_charts: bool
* title: str | None
* currency_columns: list[str]
* date_columns: list[str]
* number_precision: int | None
* sheet_name: str | None

Validation:

* output_format must be supported.
* PDF writer must handle missing charts gracefully.
* CSV cannot embed charts.
* JSON should output structured records and metadata.
* TXT should output readable summary and optionally tabular text.

## PHASE 9 — Add DataFrame profiling tool

Create:

src/finflow_agent/tools/dataframe_profile.py

Implement a function like:

profile_dataframe(df: pd.DataFrame, sample_rows: int = 5) -> dict

It should return:

* row_count
* column_count
* columns
* dtypes
* null_counts
* duplicate_row_count
* sample_records
* likely_date_columns
* likely_currency_columns
* likely_numeric_columns
* likely_categorical_columns
* memory_usage
* warnings

Do not include huge data samples in prompts or logs.

Limit sample_records to a small number.

Make sure values are JSON serializable.

## PHASE 10 — Add safe dataframe operation executor

Create:

src/finflow_agent/tools/safe_dataframe_ops.py

or use:

src/finflow_agent/operations/executor.py

Implement functions:

* execute_cleaning_plan(df, plan) -> ExecutionOutput
* execute_filter_plan(df, plan) -> ExecutionOutput
* execute_calculation_plan(df, plan) -> ExecutionOutput
* execute_visualization_plan(df_or_result, plan) -> ExecutionOutput
* execute_reporting_plan(state, plan) -> ExecutionOutput

ExecutionOutput should include:

* data
* metrics
* operations_applied
* warnings
* summary
* artifacts

All operations must be deterministic and auditable.

Each operation should add an operation_applied entry:

{
"type": "normalize_currency",
"column": "amount",
"input_rows": 1200,
"output_rows": 1200,
"changed_values": 1187
}

If exact changed count is expensive, include best available metric.

Do not mutate original DataFrame in place unless that is already the repo convention. Prefer df.copy().

## PHASE 11 — Refactor Ingestion Agent

Ingestion Agent should remain mostly deterministic.

Responsibilities:

* Read supported file types.
* Reject unsupported file types clearly.
* Produce DataFrame or structured text.
* Produce profile metadata.
* Return rich AgentResult.

Supported input formats:

* .xlsx
* .xls if dependency exists
* .csv
* .tsv
* .json
* .txt
* .pdf if parser dependency exists

Unsupported:

* images .png .jpg .jpeg .webp should be rejected/quarantined according to existing engine/status behavior.
* Do not silently OCR.

AgentResult summary example:

"Parsed CSV with 1,240 rows and 9 columns. Detected 2 likely date columns, 1 likely currency column, and 14 duplicate rows."

Metrics:

* file_type
* row_count
* column_count
* duplicate_row_count
* parse_duration_ms if easy
* likely_date_columns
* likely_currency_columns
* warnings

Data:

* The parsed dataframe or existing state reference format.

## PHASE 12 — Refactor Cleaning Agent

Cleaning Agent must not be a static one-size-fits-all script.

It should:

1. Receive upstream DataFrame and profile.
2. Build a CleaningOperationPlan.
3. Validate the plan.
4. Execute the plan using safe executor.
5. Return AgentResult with data, summary, metrics, operations_applied, warnings.

For now, the CleaningOperationPlan may be generated deterministically from:

* Orchestrator params
* data profile
* default safe cleaning policy

Do not require LLM for this phase.

Default cleaning policy:

* trim whitespace in string columns
* remove fully empty rows
* remove fully empty columns
* normalize column names only if existing behavior expects it; otherwise preserve names and record warning
* drop exact duplicate rows only if architecture requires this as default
* normalize dates only for likely date columns
* normalize currency only for likely currency columns
* coerce numeric only for likely numeric/currency columns

Important:

* Be careful not to destroy user data.
* If a column has ambiguous date parsing, warn and either coerce safely or fail depending on existing policy.
* If any operation produces partial/unsafe output, return failed or warning according to existing submission failure contract.

## PHASE 13 — Refactor Filter Agent

Filter Agent should:

1. Receive cleaned DataFrame.
2. Build FilterOperationPlan from Orchestrator params.
3. Validate referenced columns.
4. Execute safe filter operations.
5. Return rich AgentResult.

If no filter criteria exist, Orchestrator should normally omit Filter Agent. But if Filter Agent is called with no conditions/projection, it should safely pass through the data and state summary:

"No filter criteria were provided. Passed through 1,240 rows unchanged."

Do not use pandas query strings from user or LLM.

## PHASE 14 — Refactor Calculation Agent

Calculation Agent should:

1. Receive filtered or cleaned DataFrame.
2. Build CalculationOperationPlan from Orchestrator params.
3. Validate operations.
4. Execute deterministic calculations.
5. Return result table/series with rich AgentResult.

If no calculation is requested but agent is called, either:

* pass through with warning, or
* fail plan validation, depending on current engine semantics.

Prefer fail loudly if a calculation step exists but has no valid calculation operations.

## PHASE 15 — Refactor Visualization Agent

Visualization Agent should:

1. Receive upstream DataFrame or calculation result.
2. Build VisualizationOperationPlan.
3. Validate chart specs.
4. Generate chart metadata or chart objects suitable for reporting.
5. Return rich AgentResult.

Do not make PNG a user-facing output.

Do not write final files here.

Visualization Agent creates chart objects or chart specs for Reporting Agent.

## PHASE 16 — Refactor Reporting Agent

Reporting Agent needs major implementation.

It must:

1. Receive all relevant upstream outputs from PipelineState.
2. Build ReportingOperationPlan from output_format and params.
3. Validate output format.
4. Write final artifact into OUTPUT_DIR.
5. Apply display formatting only here.
6. Embed charts if present and format supports them.
7. Return final output path in AgentResult.artifacts and/or data.

Supported output formats:

* XLSX
* CSV
* JSON
* TXT
* PDF

XLSX formatting requirements:

* freeze header row if useful
* bold headers
* auto column width
* date display formatting
* currency display formatting
* number precision formatting
* summary sheet if include_summary true
* data sheet
* charts sheet if charts exist

CSV requirements:

* final tabular output only
* no charts
* no formatting
* use utf-8

JSON requirements:

* metadata
* records
* summary
* operations_applied if useful

TXT requirements:

* readable summary
* optional table preview

PDF requirements:

* title
* summary
* table
* charts if available
* handle large tables with preview or pagination
* do not crash on missing charts

If unsupported output format requested:

* return AgentResult failed with clear error
* do not silently use XLSX

## PHASE 17 — Update Orchestrator robustness

Do not rewrite Orchestrator completely unless necessary.

Add or improve:

* structured output parsing
* retry-on-invalid-JSON once or twice
* validation before engine execution
* clear quarantine/fail result for unsupported domain/capability
* explicit instruction not to hallucinate agent names
* output only registered agent names
* output only valid stages and params

If Orchestrator already has this, only strengthen tests.

The Orchestrator should pass user instruction and relevant params to agents through PlanStep.params.

## PHASE 18 — Update engine summary aggregation

Engine should collect per-step AgentResult telemetry.

The final callback summary should include:

* steps_run
* step_statuses
* duration_ms
* agent_summaries
* step_metrics
* operations_applied_by_step
* warnings_by_step
* failed_step_id if any
* error_message if any

Example:

{
"steps_run": ["step_1", "step_2", "step_3"],
"step_statuses": {
"step_1": "success",
"step_2": "success",
"step_3": "success"
},
"agent_summaries": [
{
"step_id": "step_1",
"agent": "ingestion_agent",
"status": "success",
"summary": "Parsed CSV with 1,240 rows and 9 columns.",
"metrics": {...},
"warnings": []
}
],
"operations_applied_by_step": {
"step_2": [...]
},
"duration_ms": 4200
}

Keep old summary fields if frontend/backend rely on them.

## PHASE 19 — Update backend callback persistence if needed

Inspect backend agent callback route.

Ensure it persists:

* status
* output_path
* summary JSON blob
* audit log entries per step if existing design supports it

Do not create a new status model.

Do not reintroduce agent_status or review_status.

Ensure failed/quarantined states are handled clearly.

## PHASE 20 — Update frontend mapping if needed

Frontend should consume rich summary.

Find current mapping in frontend/src/api/finflow.js or equivalent.

Make sure milestone stepper can use:

* summary.agent_summaries
* step_id
* agent
* status
* summary
* warnings
* metrics

If agent_summaries missing, preserve fallback behavior.

Do not break existing UI.

## PHASE 21 — Add tests

Add tests for operation plan architecture.

Required unit tests:

1. CleaningOperationPlan accepts valid operations.
2. CleaningOperationPlan rejects invalid operation type.
3. FilterOperationPlan validates column references.
4. Filter executor applies eq/gt/between/contains/in.
5. Calculation executor applies sum/mean/group_sum/running_total.
6. DataFrame profile detects row_count, nulls, duplicates, likely numeric/currency/date columns.
7. Reporting plan rejects unsupported format.
8. AgentResult serializes new fields.
9. Engine summary includes agent_summaries.
10. Existing minimal DAG still runs.

Add integration-style test if current test setup allows:

* create sample CSV
* run ingestion → cleaning → filter → calculation → reporting
* verify output file exists
* verify summary has steps and agent summaries

Do not require real Groq API calls in tests. Mock LLM calls.

## PHASE 22 — Dependency updates

Only update requirements if imports require it.

Before adding dependency:

1. Search current dependency files.
2. Check if already present.
3. Add minimal necessary package.
4. Do not add langchain-experimental unless you are explicitly implementing disabled advanced mode, which this task should not do.
5. Do not add huge dependencies unnecessarily.

Likely allowed dependencies if missing and used:

* pandas
* numpy
* openpyxl
* xlsxwriter
* pydantic
* reportlab
* pypdf or PyPDF2
* pytest
* pytest-asyncio

Do not add:

* langchain-experimental for PythonAstREPLTool in normal path
* unstructured unless already used
* OCR dependencies
* browser automation dependencies
* vector database dependencies

============================================================
EXACT SAFE OPERATION PLAN EXAMPLES
==================================

Cleaning example:

{
"operations": [
{
"type": "trim_whitespace",
"columns": "**all_string_columns**"
},
{
"type": "drop_duplicates",
"subset": null,
"keep": "first"
},
{
"type": "normalize_date",
"column": "date",
"target_format": "YYYY-MM-DD",
"dayfirst": null,
"errors": "coerce"
},
{
"type": "normalize_currency",
"column": "amount",
"precision": 2,
"strip_symbols": true,
"negative_parentheses": true
}
],
"rationale": "Clean structure and normalize finance fields before filtering or calculation.",
"warnings": []
}

Filter example:

{
"conditions": [
{
"column": "merchant",
"operator": "contains",
"value": "paypal",
"case_sensitive": false
},
{
"column": "amount",
"operator": "gt",
"value": 5000
}
],
"logic": "AND",
"select_columns": ["date", "merchant", "amount"],
"sort_by": [
{
"column": "date",
"direction": "desc"
}
],
"limit": null,
"warnings": []
}

Calculation example:

{
"operations": [
{
"type": "group_sum",
"group_by": ["merchant"],
"column": "amount",
"output_column": "total_amount",
"precision": 2
}
],
"rationale": "User requested total amount grouped by merchant.",
"warnings": []
}

Visualization example:

{
"charts": [
{
"type": "bar",
"x": "merchant",
"y": "total_amount",
"title": "Total Amount by Merchant",
"x_axis_title": "Merchant",
"y_axis_title": "Total Amount"
}
],
"warnings": []
}

Reporting example:

{
"output_format": "xlsx",
"include_summary": true,
"include_raw_data": false,
"include_cleaning_log": true,
"include_charts": true,
"title": "FinFlow Processed Report",
"currency_columns": ["amount", "total_amount"],
"date_columns": ["date"],
"number_precision": 2,
"sheet_name": "Processed Data"
}

============================================================
CODING RULES
============

1. Use type hints.
2. Use Pydantic models for schemas.
3. Use explicit enums/literals for operation types.
4. Avoid broad except clauses unless re-raising meaningful AgentResult errors.
5. Avoid hidden global mutable state.
6. Avoid writing intermediate files unless necessary.
7. Keep DataFrame operations deterministic.
8. Keep audit data JSON serializable.
9. Make summaries human-readable.
10. Make error messages user-safe and developer-useful.
11. Do not log full sensitive financial datasets.
12. Limit preview/sample rows.
13. Never include API keys in logs.
14. Do not use network calls in tests.
15. Do not use live Groq calls in tests.
16. Use temporary directories for output tests.
17. Preserve existing public API unless migration is necessary.
18. Preserve existing frontend behavior with fallback mapping.
19. Do not over-engineer with vector search, plugin systems, or autonomous agent loops.
20. Prefer small well-named files over giant agent files.

============================================================
SECURITY RULES
==============

Never allow these in operation plans:

* raw Python code
* pandas eval strings
* pandas query strings from users
* shell commands
* SQL strings
* file paths outside allowed upload/output directories
* network URLs
* arbitrary imports
* arbitrary function names
* LLM-generated regex that can cause catastrophic backtracking without validation
* direct filesystem writes from Cleaning/Filter/Calculation agents
* output path chosen directly by user

Path handling:

* Use pathlib.
* Resolve output path.
* Ensure output path is inside OUTPUT_DIR.
* Generate filenames server-side.
* Avoid path traversal.

Data handling:

* Do not persist intermediate DataFrames permanently.
* Do not log full datasets.
* Log counts, columns, metrics, warnings, and operation names.
* Store final records only through existing final-output mechanism.

============================================================
EXPECTED FINAL RESULT
=====================

After implementation, the repo should have:

1. Extended AgentResult telemetry.
2. Operation plan schemas.
3. DataFrame profiling utility.
4. Safe operation validators.
5. Safe deterministic executors.
6. Refactored agents using operation plans.
7. Rich agent summaries.
8. Reporting Agent with real formatting/output behavior.
9. Engine/callback summary aggregation.
10. Frontend milestone compatibility.
11. Tests for schemas/executors/summary.
12. progress.md updated after each batch of 5 meaningful changes.

The final architecture should still be:

Deterministic LangGraph DAG
+
LLM-capable Orchestrator
+
LLM-assisted future-ready agents
+
Validated operation plans
+
Safe deterministic tool execution
+
Rich audit trail

Not:

Autonomous agents running arbitrary code.

============================================================
DELIVERABLE FORMAT
==================

When finished, provide:

1. Summary of files changed.
2. Explanation of the new operation-plan architecture.
3. List of tests added/updated.
4. Commands run.
5. Any tests that failed and why.
6. Any assumptions made.
7. Any questions/blockers.
8. Whether progress.md was updated and how many batches were logged.

Do not claim success unless tests actually ran or you clearly state they were not run.

============================================================
FIRST ACTIONS TO TAKE NOW
=========================

Start by running repository inspection commands equivalent to:

* list files
* find agent service files
* find AgentResult definition
* find PipelineState definition
* find existing tests
* find dependency files
* find progress.md
* inspect frontend summary mapping

Then implement Phase 1 onward.

Remember:

Do not use AgentExecutor.
Do not use initialize_agent.
Do not use unrestricted Python REPL.
Do not let agents choose DAG routing.
Do not silently default unsupported output formats.
Do not write intermediate data permanently.
Do update progress.md after every 5 meaningful changes.
