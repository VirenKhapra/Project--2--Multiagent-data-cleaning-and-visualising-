# Requirements Document

## Introduction

This feature hardens the FinFlow Agent Service pipeline so it stays focused on cleaning and filtering today, while strictly following a format that can safely add a visualization agent later without rewriting or breaking existing agents. The hardening preserves the existing `PlanIntent → compile_intent_to_plan() → ExecutionPlan → PlanStep[] → ExecutionEngine → AgentResult` orchestration format and the `success | partial | failed` `AgentResult` envelope, and adds three safety layers on top of it: a schema-flexible dataframe profiler that never leaks raw rows to the LLM, a column resolver with a confidence threshold that prevents silent low-confidence filtering, and a future-agent-compatible plan validator that rejects unknown agents, broken `input_from` chains, and disabled future agents like the visualization agent. The LLM contract is tightened so the LLM may only output a `PlanIntent`, never a `PlanStep` or `ExecutionPlan`. The Reporting Agent is reduced to a pure writer that emits one Excel file with deterministic audit sheets and never performs cleaning, filtering, calculation, or visualization itself.

## Glossary

- **FinFlow_Agent_Service**: The overall service that ingests a user instruction and an uploaded data file, plans an execution, runs agents, and returns an output artifact.
- **Orchestrator**: The component that prompts the LLM for a `PlanIntent`, validates the LLM response, invokes the compiler, and routes the resulting `ExecutionPlan` to the engine.
- **DataFrame_Profiler**: A schema-flexible component that produces a sanitized `DataFrameProfile` of an uploaded dataframe for use by the LLM and the column resolver. It never returns full rows.
- **Column_Resolver**: A component that maps an LLM-requested field name to an actual dataframe column with a confidence score in `[0.0, 1.0]`.
- **Compiler**: The deterministic function `compile_intent_to_plan` that turns a validated `PlanIntent` into an `ExecutionPlan`.
- **Plan_Validator**: The function `validate_plan` that rejects malformed `ExecutionPlan` objects before the engine runs them.
- **Execution_Engine**: The component that walks the validated DAG in topological order, validates each step's `params` against the agent's Pydantic params model, and routes the correct dataframe to each agent via `input_from`.
- **Ingestion_Agent / Cleaning_Agent / Filter_Agent / Reporting_Agent / Visualization_Agent**: The five pipeline agents. The visualization agent is scaffolded but disabled by default.
- **PlanIntent**: A Pydantic model representing the LLM's stated intent. It contains flags such as `needs_cleaning`, `needs_filtering`, `needs_visualization`, the matching `*_plan` fields, and reporting hints. It MUST NOT contain a top-level `steps` key.
- **ExecutionPlan**: A Pydantic model containing an ordered list of `PlanStep` objects produced by the compiler.
- **PlanStep**: A Pydantic model with fields `step_id`, `agent`, `params`, `depends_on`, `input_from`, and `output_key`.
- **AgentResult**: The envelope returned by every agent, with `status ∈ {success, partial, failed}`, `error_message`, `data`, `summary`, `metrics`, `operations_applied`, `warnings`, and `artifacts`.
- **ColumnResolution**: A Pydantic model with `requested_field`, `matched_column`, `semantic_type`, `confidence ∈ [0.0, 1.0]`, and `reason`.
- **DataFrameProfile**: A Pydantic model containing `row_count`, `column_count`, a list of `ColumnProfile` entries (each capped at 3 sample values), `duplicate_row_count`, and `warnings`.
- **CONFIDENCE_THRESHOLD**: A constant `0.75` below which the column resolver's match cannot drive an unattended filter.
- **ENABLE_VISUALIZATION**: An environment flag that defaults to `false`. While `false`, the visualization agent is treated as a disabled future agent.
- **LOW_CONFIDENCE_POLICY**: An environment flag with values `warn | fail | quarantine` (default `fail`) that controls the `Filter_Agent` response when a column resolution has `confidence < 0.75`.
- **Audit_Sheet_Writer**: The reporting helper that writes one Excel file with the deterministic audit sheets `cleaned_data`, optional `filtered_data`, `audit_log`, `warnings`, and `column_mapping`.
- **VisualizationDisabledError**: The controlled error raised by the compiler when a `PlanIntent` requests visualization while `ENABLE_VISUALIZATION` is `false`.
- **filter_prep**: A non-destructive preparation mode of the `Cleaning_Agent` (configured as `{"mode": "filter_prep", "operations": [...]}`) that the `Compiler` inserts before the `Filter_Agent` when `intent.needs_filtering` is `true` and `intent.needs_cleaning` is `false`. The mode is restricted to safe, structural normalization operations only — `trim_whitespace`, `normalize_column_names`, `normalize_empty_strings`, `safe_numeric_conversion`, `safe_currency_conversion`, `safe_date_detection`, and `categorical_value_normalization` — and never performs destructive cleaning. Its output dataframe is published under the canonical `output_key` `df_filter_prepared`.
- **df_filter_prepared**: The canonical `output_key` produced by a `filter_prep` step. Holds a non-destructively normalized dataframe that the `Filter_Agent` consumes via `input_from` when no full cleaning step ran.

## Requirements

### Requirement 1: LLM Contract and Orchestration

**User Story:** As a platform engineer, I want the LLM to only emit a `PlanIntent`, so that the pipeline cannot be coerced into running an arbitrary, unvalidated `ExecutionPlan` constructed by the LLM.

#### Acceptance Criteria

1. WHEN the LLM response contains a top-level `steps` key, THE Orchestrator SHALL reject the response and return a quarantine result without constructing an `ExecutionPlan`.
2. WHEN the LLM response is shaped as a `PlanIntent`, THE Orchestrator SHALL validate the response with `PlanIntent.model_validate` before invoking the compiler.
3. WHEN the Orchestrator builds the prompt for the LLM, THE Orchestrator SHALL include the `DataFrameProfile` and SHALL NOT include any full dataframe row in the prompt body.
4. WHEN the Orchestrator receives a validated `PlanIntent` with `is_quarantined = True`, THE Orchestrator SHALL return a quarantine result containing `quarantine_reason` and SHALL NOT invoke the compiler.
5. THE Orchestrator SHALL produce, for every successful planning call, an `ExecutionPlan` constructed exclusively by `compile_intent_to_plan` from the validated `PlanIntent`.

### Requirement 2: Deterministic Compiler

**User Story:** As a platform engineer, I want a deterministic compiler that turns a `PlanIntent` into a fixed-shape `ExecutionPlan`, so that the executable plan is predictable, the filter agent always receives a normalized dataframe, and a future visualization step can be inserted without changing existing agents.

#### Acceptance Criteria

1. WHEN `compile_intent_to_plan` is called with a valid `PlanIntent`, THE Compiler SHALL emit an `ExecutionPlan` whose first step uses the `ingestion_agent` and whose last step uses the `reporting_agent`.
2. WHERE `intent.needs_cleaning` is `true` and `intent.cleaning_plan` is not `None`, THE Compiler SHALL insert a `cleaning_agent` step between ingest and report.
3. WHERE `intent.needs_filtering` is `true` and `intent.filter_plan` is not `None`, THE Compiler SHALL insert a `filter_agent` step that receives a normalized dataframe input, placed after the most recent normalization step (the `cleaning_agent` step when present, otherwise the `filter_prep` step) and before the reporting step.
4. THE Compiler SHALL NOT set a `filter_agent` step's `input_from` to reference the raw ingestion output `df_ingested` or any other unnormalized dataframe `output_key`.
5. WHERE `intent.needs_cleaning` is `true` and `intent.needs_filtering` is `true`, THE Compiler SHALL produce the canonical pipeline order `ingest → clean → filter → report`, with the `filter_agent` step's `input_from` referencing the `cleaning_agent` step's `df_cleaned` output.
6. IF `intent.needs_cleaning` is `false` and `intent.needs_filtering` is `true` and `intent.filter_plan` is not `None`, THEN THE Compiler SHALL insert a non-destructive `filter_prep` preparation step before the `filter_agent` step, producing the canonical pipeline order `ingest → filter_prep → filter → report`.
7. WHERE THE Compiler inserts a `filter_prep` step, THE Compiler SHALL realize that step as a `cleaning_agent` invocation whose params equal `{"mode": "filter_prep", "operations": ["trim_whitespace", "normalize_column_names", "normalize_empty_strings", "safe_numeric_conversion", "safe_currency_conversion", "safe_date_detection", "categorical_value_normalization"]}` and whose `output_key` is `df_filter_prepared`.
8. THE `filter_prep` step SHALL NOT drop rows with partial missing values, impute missing values, remove non-exact duplicates, drop columns containing any null values, rewrite low-confidence values, or apply business-specific transformations.
9. IF `intent.needs_cleaning` is `false`, THEN THE Compiler SHALL NOT enable any destructive or high-impact cleaning operation in the `filter_prep` step beyond the safe operations enumerated in clause 2.7.
10. THE `filter_agent` step's `input_from` SHALL reference exactly one of `df_cleaned` (when the `cleaning_agent` step ran) or `df_filter_prepared` (when the `filter_prep` step ran), and SHALL NOT reference `df_ingested`.
11. WHERE `intent.needs_visualization` is `true`, `intent.visualization_plan` is not `None`, and `ENABLE_VISUALIZATION` is `true`, THE Compiler SHALL insert a `visualization_agent` step after the `filter_agent` step (when present) and before reporting.
12. IF `intent.needs_visualization` is `true` and `ENABLE_VISUALIZATION` is `false`, THEN THE Compiler SHALL raise `VisualizationDisabledError` with the message `"Visualization was requested, but visualization_agent is not enabled in this version"`.
13. IF `intent.needs_X` is `true` and `intent.X_plan` is `None` for any `X ∈ {cleaning, filtering, visualization, calculation}`, THEN THE Compiler SHALL raise a `ValueError` that names the missing field.
14. THE Compiler SHALL set `output_key` values from the canonical set `{df_ingested, df_cleaned, df_filter_prepared, df_filtered, df_visualized, report_output}` and SHALL NOT emit any other `output_key` value.
15. THE Compiler SHALL set each step's `input_from` to reference the most recent dataframe `output_key` produced by an earlier step.
16. WHERE THE Compiler inserts a `filter_prep` step, THE Compiler SHALL emit, for that step, an entry tagged as an internal preparation step that the `Audit_Sheet_Writer` records in the `audit_log` sheet defined in Requirement 8.
17. WHERE a `filter_prep` step ran and `intent.needs_cleaning` was `false`, THE Reporting_Agent's user-facing summary SHALL state that data was normalized for filtering and SHALL NOT claim that full cleaning was performed (per Requirement 8).

### Requirement 3: Plan Validator

**User Story:** As a platform engineer, I want the plan validator to reject every malformed `ExecutionPlan` before execution, so that no invalid plan ever touches pandas or an agent.

#### Acceptance Criteria

1. WHEN `validate_plan` is called with an `ExecutionPlan` containing duplicate `step_id` values, THE Plan_Validator SHALL return `(False, error)` with an error message that names the duplicated `step_id`.
2. WHEN `validate_plan` is called with an `ExecutionPlan` containing a step whose `agent` is not registered, THE Plan_Validator SHALL return `(False, error)` with an error message of the form `"Unknown agent: <name>"`.
3. WHEN `validate_plan` is called with an `ExecutionPlan` containing a `depends_on` entry that references a `step_id` not present in the plan, THE Plan_Validator SHALL return `(False, error)` that names both the dependent step and the unknown dependency.
4. WHEN `validate_plan` is called with an `ExecutionPlan` containing an `input_from` key that is not produced by a strictly earlier step in topological order, THE Plan_Validator SHALL return `(False, error)` that names the dependent step and the missing key.
5. WHEN `validate_plan` is called with an `ExecutionPlan` whose dependency graph contains a cycle, THE Plan_Validator SHALL return `(False, error)` indicating a cycle was detected.
6. WHEN `validate_plan` is called with an `ExecutionPlan` whose stage ordering is not monotonic across `ingest → transform → analyze → visualize → deliver`, THE Plan_Validator SHALL return `(False, error)` that names the offending step.
7. IF a step's `agent` is `visualization_agent` while `ENABLE_VISUALIZATION` is `false`, THEN THE Plan_Validator SHALL return `(False, error)` with the message `"visualization_agent is not enabled in this version"`.
8. WHEN `validate_plan` is called with an `ExecutionPlan` containing a step whose `params` does not validate against the agent's registered Pydantic param model, THE Plan_Validator SHALL return `(False, error)` that names the offending `step_id` and includes the Pydantic error message.
9. WHEN `validate_plan` is called with a fully-conforming `ExecutionPlan`, THE Plan_Validator SHALL return `(True, "")` and SHALL NOT mutate the plan.

### Requirement 4: Execution Engine and Agent Contract

**User Story:** As a platform engineer, I want the execution engine to enforce the agent contract on every step, so that each agent receives exactly one validated dataframe and validated params.

#### Acceptance Criteria

1. WHEN the Execution_Engine processes a step, THE Execution_Engine SHALL re-validate the step's `params` against the agent's registered Pydantic param model before invoking `agent.execute`.
2. IF the per-step param re-validation fails, THEN THE Execution_Engine SHALL return a failed callback that names the offending `step_id` and SHALL NOT invoke `agent.execute`.
3. WHEN the Execution_Engine prepares `input_data` for a step, THE Execution_Engine SHALL resolve `input_dataframe` exclusively from the dataframe produced by the upstream step referenced in the step's `input_from`.
4. WHILE the Execution_Engine is walking the DAG, THE Execution_Engine SHALL execute steps in topological order and SHALL NOT execute any step before all of its `depends_on` predecessors have produced a `success` `AgentResult`.
5. IF an agent returns an `AgentResult` with `status ∈ {failed, partial}`, THEN THE Execution_Engine SHALL stop the DAG walk and return a failed callback that names the failed `step_id`.
6. THE Execution_Engine SHALL store, for each successful step, an envelope under the key `step.output_key` (or `step.step_id` when `output_key` is `None`) and SHALL NOT store envelopes under any other key.
7. THE Execution_Engine SHALL NOT pass any state-data key to an agent that is not referenced by that step's `input_from`.

### Requirement 5: Agent Result Envelope

**User Story:** As a platform engineer, I want every agent to return a strictly typed `AgentResult` envelope, so that downstream consumers can rely on a closed status set.

#### Acceptance Criteria

1. THE Ingestion_Agent, Cleaning_Agent, Filter_Agent, and Reporting_Agent SHALL return an `AgentResult` whose `status` is exactly one of `success`, `partial`, or `failed`.
2. WHEN an agent encounters a precondition violation (such as a missing `input_dataframe` or invalid params), THE agent SHALL return `AgentResult(status="failed", error_message=...)` with a non-empty `error_message`.
3. WHEN an agent applies an operation, THE agent SHALL append a record describing that operation to `AgentResult.operations_applied`.
4. WHERE an agent produces a non-fatal anomaly (such as a low-confidence column match), THE agent SHALL append a human-readable string to `AgentResult.warnings`.
5. THE Filter_Agent SHALL receive its dataframe exclusively from `input_data["input_dataframe"]` and SHALL NOT read any other key from the engine state.

### Requirement 6: DataFrame Profiler

**User Story:** As a security-conscious operator, I want a sanitized profile of the uploaded dataframe to be the only summary ever sent to the LLM, so that raw spreadsheet rows never leave the service.

#### Acceptance Criteria

1. THE DataFrame_Profiler SHALL accept any `pd.DataFrame` and SHALL return a `DataFrameProfile` regardless of the dataframe's column names or dtypes.
2. WHEN `profile_dataframe` is called, THE DataFrame_Profiler SHALL produce one `ColumnProfile` per column with `original_name`, `normalized_name`, `dtype`, `null_count`, `sample_values`, `semantic_guess`, and `confidence ∈ [0.0, 1.0]`.
3. THE DataFrame_Profiler SHALL cap `sample_values` at three entries per column.
4. THE DataFrame_Profiler SHALL coerce non-scalar sample values to strings and SHALL truncate any stringified sample value to at most 64 characters.
5. WHEN `include_samples` is `false`, THE DataFrame_Profiler SHALL produce empty `sample_values` for every column.
6. THE DataFrame_Profiler SHALL classify each column's `semantic_guess` as one of `date`, `currency`, `numeric`, `categorical`, `boolean`, `string`, or `unknown`.
7. WHEN the dataframe's deep memory usage exceeds 50 MB, THE DataFrame_Profiler SHALL append a warning to `DataFrameProfile.warnings` indicating the size threshold was exceeded.
8. THE DataFrame_Profiler SHALL NOT include any full dataframe row in the returned `DataFrameProfile`.

### Requirement 7: Column Resolver and Confidence Threshold

**User Story:** As a data steward, I want the column resolver to gate filter operations behind a confidence threshold, so that an LLM-requested field name cannot silently filter on a wrong column.

#### Acceptance Criteria

1. WHEN `resolve_column` is called with a requested field whose lowercased value matches an existing column's lowercased `original_name`, THE Column_Resolver SHALL return a `ColumnResolution` with `confidence = 1.0` and a `reason` indicating an exact case-insensitive match.
2. WHEN `resolve_column` is called with a requested field that matches a column's `normalized_name`, THE Column_Resolver SHALL return a `ColumnResolution` with `confidence ≥ 0.95`.
3. WHEN `resolve_column` is called with a requested field that matches a known synonym for a column's `semantic_guess`, THE Column_Resolver SHALL return a `ColumnResolution` with `confidence ≥ 0.85`.
4. WHEN `resolve_column` is called with a requested field that has no exact, normalized, or synonym match, THE Column_Resolver SHALL return a `ColumnResolution` whose `confidence` equals the fuzzy token-set similarity in `[0.0, 1.0]`.
5. WHEN `resolve_columns` is called with a fixed `requested_fields` list and a fixed `DataFrameProfile`, THE Column_Resolver SHALL produce the same list of `ColumnResolution` objects on every invocation.
6. IF the Filter_Agent receives a `ColumnResolution` with `confidence < 0.75` for any condition, THEN THE Filter_Agent SHALL NOT silently apply that condition and SHALL respond according to `LOW_CONFIDENCE_POLICY`.
7. WHERE `LOW_CONFIDENCE_POLICY = "warn"`, THE Filter_Agent SHALL append a warning to `AgentResult.warnings`, skip the offending condition, and continue processing the remaining conditions.
8. WHERE `LOW_CONFIDENCE_POLICY = "fail"`, THE Filter_Agent SHALL return `AgentResult(status="failed", error_message=...)` whose `error_message` names the offending requested field, the matched column, and the confidence value.
9. WHERE `LOW_CONFIDENCE_POLICY = "quarantine"`, THE Filter_Agent SHALL return an `AgentResult` that signals quarantine to the orchestrator and SHALL NOT apply the offending condition.

### Requirement 8: Reporting and Audit Sheets

**User Story:** As a reviewer, I want the reporting agent to produce one Excel file with deterministic audit sheets, so that the cleaned data, filtered data, applied operations, warnings, and column mappings are all visible to a human reviewer.

#### Acceptance Criteria

1. WHEN the Reporting_Agent runs, THE Audit_Sheet_Writer SHALL write a single `.xlsx` file at `<output_dir>/<file_prefix>.xlsx`.
2. THE Audit_Sheet_Writer SHALL always include a `cleaned_data` sheet as the first sheet of the output Excel file.
3. WHERE `payload.filtered_data` is not `None`, THE Audit_Sheet_Writer SHALL include a `filtered_data` sheet in the output Excel file.
4. WHERE `payload.filtered_data` is `None`, THE Audit_Sheet_Writer SHALL NOT include a `filtered_data` sheet in the output Excel file.
5. THE Audit_Sheet_Writer SHALL always include `audit_log`, `warnings`, and `column_mapping` sheets, even when their underlying lists are empty.
6. THE Reporting_Agent SHALL NOT modify any dataframe values when producing the output file and SHALL NOT perform cleaning, filtering, calculation, or visualization.
7. THE Audit_Sheet_Writer SHALL return a dictionary containing `output_file_path` and `sheets_written`.
8. THE Audit_Sheet_Writer SHALL resolve the output path through a path-safety helper that rejects absolute paths and parent-directory traversal segments.
9. WHERE the Compiler inserted a `filter_prep` step (per Requirement 2.16), THE Audit_Sheet_Writer SHALL include a row in the `audit_log` sheet that records the `filter_prep` insertion as an internal preparation step and identifies it as a non-destructive normalization.
10. WHERE a `filter_prep` step ran and `intent.needs_cleaning` was `false`, THE Reporting_Agent SHALL produce a user-facing summary stating `"Data was normalized for filtering."` and SHALL NOT produce a summary that claims full cleaning was performed.

### Requirement 9: Visualization Scaffolding

**User Story:** As a future-feature owner, I want the visualization agent to be scaffolded but disabled by default, so that visualization can be added later without rewriting existing agents and without ever producing a fake chart today.

#### Acceptance Criteria

1. WHILE `ENABLE_VISUALIZATION` is `false`, THE Plan_Validator SHALL reject any `ExecutionPlan` that contains a `visualization_agent` step.
2. WHILE `ENABLE_VISUALIZATION` is `false`, THE Compiler SHALL raise `VisualizationDisabledError` for any `PlanIntent` with `needs_visualization = true`.
3. WHEN the Compiler raises `VisualizationDisabledError`, THE Orchestrator SHALL return a quarantine result whose reason includes the message `"visualization_agent is not enabled in this version"`.
4. THE Cleaning_Agent and Filter_Agent SHALL NOT generate, render, or embed any chart in any output artifact.
5. THE Reporting_Agent SHALL NOT generate, render, or embed any chart in the output Excel file.

### Requirement 10: Agent Param Models

**User Story:** As a platform engineer, I want every agent's `params` to be gated by a Pydantic model registered alongside the agent, so that no agent ever runs with malformed params.

#### Acceptance Criteria

1. THE Ingestion_Agent SHALL declare an `IngestionAgentParams` Pydantic model that requires a `resolved_file_path` string and a `file_type` value of `xlsx`, `xls`, or `csv`.
2. THE Cleaning_Agent SHALL declare a `CleaningAgentParams` Pydantic model whose `plan` field is a `CleaningOperationPlan`.
3. THE Filter_Agent SHALL declare a `FilterAgentParams` Pydantic model whose `plan` field is a `FilterOperationPlan`.
4. THE Reporting_Agent SHALL declare a `ReportingAgentParams` Pydantic model whose `plan` field is a `ReportingOperationPlan` and whose `plan.output_format` is one of `xlsx`, `csv`, `json`, or `txt`.
5. IF a `ReportingOperationPlan.output_format` is set to `pdf`, THEN THE Reporting_Agent's param model SHALL reject the value during Pydantic validation.
6. WHEN an agent's params dict fails validation against its registered Pydantic param model, THE Execution_Engine SHALL return a failed callback whose message includes the Pydantic error and SHALL NOT invoke `agent.execute`.

### Requirement 11: Error Handling and Quarantine

**User Story:** As an operator, I want every documented error scenario to produce a controlled, traceable response, so that no malformed input ever leaks into pandas or the output file.

#### Acceptance Criteria

1. IF the LLM emits a response with a top-level `steps` key, THEN THE Orchestrator SHALL return a quarantine result whose reason names the legacy `steps` key and SHALL NOT construct an `ExecutionPlan`.
2. IF the Plan_Validator rejects an `ExecutionPlan`, THEN THE Execution_Engine SHALL NOT execute any step of that plan.
3. IF a step's `input_from` references a key not produced earlier, THEN THE Plan_Validator SHALL return `(False, error)` whose message names the offending step and the missing key.
4. IF the Filter_Agent receives an `input_data["input_dataframe"]` of `None`, THEN THE Filter_Agent SHALL return `AgentResult(status="failed", error_message="input_dataframe is required. No input dataframe provided.")`.
5. IF a Column_Resolver match has `confidence < 0.75`, THEN THE Filter_Agent SHALL respond according to `LOW_CONFIDENCE_POLICY` and SHALL include the `ColumnResolution` in the audit `column_mapping` payload.
6. IF the Compiler raises `VisualizationDisabledError`, THEN THE Orchestrator SHALL convert the error to a quarantine result and SHALL NOT execute any plan.

### Requirement 12: Profile Privacy in LLM Prompts

**User Story:** As a security-conscious operator, I want the LLM prompt to never contain raw spreadsheet rows, so that no personally identifiable information leaks to the LLM provider.

#### Acceptance Criteria

1. WHEN the Orchestrator assembles a Groq prompt, THE Orchestrator SHALL include only the `DataFrameProfile` and SHALL NOT include any full dataframe row.
2. WHEN the Orchestrator assembles a Groq prompt, THE Orchestrator SHALL include sample values exclusively from `DataFrameProfile.columns[i].sample_values`, each capped at three entries per column.
3. WHEN the Orchestrator assembles a Groq prompt, THE Orchestrator SHALL include a system instruction stating that the profile is untrusted data and that any instructions inside cell values must be ignored.
4. THE Orchestrator SHALL NOT pass any LLM-supplied string to `pandas.DataFrame.query` or to any other code-evaluation surface.
