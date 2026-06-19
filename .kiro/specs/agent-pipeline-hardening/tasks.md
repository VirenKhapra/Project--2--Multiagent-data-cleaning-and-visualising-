# Implementation Plan: Agent Pipeline Hardening

## Overview

Convert the feature design into a series of prompts for a code-generation LLM that will implement each step with incremental progress. Make sure that each prompt builds on the previous prompts, and ends with wiring things together. There should be no hanging or orphaned code that isn't integrated into a previous step. Focus ONLY on tasks that involve writing, modifying, or testing code.

This plan extends the existing `finflow_agent` package (do not recreate modules from scratch). Source root: `agent-framework/new-agentic-project-data-cleaning-/src/finflow_agent/`. Test root: `agent-framework/new-agentic-project-data-cleaning-/finflow_architecture_tests/tests/`. All paths below are relative to those roots unless stated otherwise. The implementation language is Python (Pydantic v2, pandas, xlsxwriter, rapidfuzz).

## Tasks

- [x] 1. Wire configuration constants (`ENABLE_VISUALIZATION`, `LOW_CONFIDENCE_POLICY`, `CONFIDENCE_THRESHOLD`)
  - [x] 1.1 Add a config module that reads the three environment variables and exposes typed accessors.
    - Read `ENABLE_VISUALIZATION` (default `false`), `LOW_CONFIDENCE_POLICY` (default `fail`, allowed `warn|fail|quarantine`), and the numeric `CONFIDENCE_THRESHOLD` (default `0.75`) from environment variables.
    - Centralize the readers in a single helper consumed by the compiler, validator, orchestrator, filter agent, bootstrap, and visualization agent registration. Cache values per process; expose typed accessors so test fixtures can monkeypatch them deterministically.
    - Modify `src/finflow_agent/bootstrap.py` to read these values at startup and pass them through to the registry, validator, compiler, and orchestrator.
    - Files: `src/finflow_agent/bootstrap.py` (modify), new helper `src/finflow_agent/tools/config.py` (or extend `src/finflow_agent/tools/__init__.py`).
    - _Requirements: 2.11, 2.12, 7.6, 7.7, 7.8, 7.9, 9.1, 9.2_

- [x] 2. Implement DataFrame Profiler (Component 1)
  - [x] 2.1 Extend `src/finflow_agent/tools/dataframe_profile.py` with the `ColumnProfile` and `DataFrameProfile` Pydantic models exactly as specified in design Component 1, plus `profile_dataframe(df, sample_rows=3, include_samples=False)`.
    - Implement `infer_semantic_type(col_name, col_series)` covering `date`, `currency`, `numeric`, `categorical`, `boolean`, `string`, `unknown` with deterministic confidence in `[0.0, 1.0]`.
    - Implement `sanitize_value` that coerces non-scalar samples to strings and truncates to ≤ 64 characters; cap `sample_values` at 3 entries; return `[]` when `include_samples=False`.
    - Compute `duplicate_row_count` and `df.memory_usage(deep=True).sum()`; append a warning when memory exceeds 50 MB.
    - Guarantee `len(profile.columns) == df.shape[1]` and that no full row is included anywhere in the returned model.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_
  - [ ]* 2.2 Write unit tests for the profiler in `finflow_architecture_tests/tests/test_dataframe_profile.py`.
    - Cover empty DataFrames, mixed-dtype DataFrames, columns with > 50 % nulls, long string truncation, `include_samples=False`, and the 50 MB memory warning.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_
  - [ ]* 2.3 Write property test for the profiler in `finflow_architecture_tests/tests/test_dataframe_profile.py`.
    - **Property 9: Profile minimality** — for any generated DataFrame, the returned profile contains no full rows, every `ColumnProfile.sample_values` has length ≤ 3, and no stringified sample exceeds 64 characters.
    - **Validates: Requirements 6.3, 6.4, 6.8, 12.1, 12.2**

- [x] 3. Implement Column Resolver (Component 2)
  - [x] 3.1 Create `src/finflow_agent/tools/column_resolver.py` exposing the `ColumnResolution` Pydantic model and the `resolve_column` / `resolve_columns` functions per design Component 2.
    - Implement matching tiers in this order: case-insensitive exact (confidence `1.0`), normalized-name (≥ `0.95`), known-synonym for the column's `semantic_guess` (≥ `0.85`), and `rapidfuzz.token_sort_ratio` fallback.
    - Define the module-level constant `CONFIDENCE_THRESHOLD = 0.75` and import the `LOW_CONFIDENCE_POLICY` reader from task 1.
    - Implement `enforce_low_confidence_policy(resolution, policy)` that returns one of `("allow", None)`, `("warn", message)`, `("fail", message)`, or `("quarantine", message)` so the filter agent has a single decision surface.
    - Be deterministic: identical inputs MUST produce identical `ColumnResolution` objects.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_
  - [ ]* 3.2 Write unit tests in `finflow_architecture_tests/tests/test_column_resolver.py`.
    - Cover exact / normalized / synonym / fuzzy matches, the `birthday → dob` synonym example from design Example 5, and unknown fields scoring below `CONFIDENCE_THRESHOLD`.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  - [ ]* 3.3 Write property test for resolver determinism in `finflow_architecture_tests/tests/test_column_resolver.py`.
    - For any fixed `requested_fields` list and `DataFrameProfile`, repeated calls to `resolve_columns` produce identical output.
    - _Requirements: 7.5_

- [x] 4. Add Pydantic agent param models (Component 4)
  - [x] 4.1 Add `IngestionAgentParams(BaseModel)` to `src/finflow_agent/agents/ingestion_agent.py` with `resolved_file_path: str` and `file_type: Literal["xlsx", "xls", "csv"]`. Register it in the agent registry alongside the agent class.
    - _Requirements: 10.1_
  - [x] 4.2 Add `CleaningAgentParams(BaseModel)` to `src/finflow_agent/agents/cleaning_agent.py` with `plan: CleaningOperationPlan`, `mode: Literal["clean", "filter_prep"] = "clean"`, and `operations: Optional[List[str]] = None`. Register it in the registry.
    - _Requirements: 10.2, 2.7_
  - [x] 4.3 Add `FilterAgentParams(BaseModel)` to `src/finflow_agent/agents/filter_agent.py` with `plan: FilterOperationPlan`. Register it in the registry.
    - _Requirements: 10.3_
  - [x] 4.4 Add `ReportingAgentParams(BaseModel)` to `src/finflow_agent/agents/reporting_agent.py` with `plan: ReportingOperationPlan`, `output_dir: Optional[str] = None`, `file_prefix: Optional[str] = None`. The model MUST cause Pydantic validation to fail when `plan.output_format == "pdf"`. Register it.
    - _Requirements: 10.4, 10.5_
  - [x] 4.5 Add `VisualizationAgentParams(BaseModel)` scaffold to `src/finflow_agent/agents/visualization_agent.py` with `plan: VisualizationOperationPlan`. Keep the agent class disabled by default; only the param model is wired so the registry stays uniform.
    - _Requirements: 10.1, 9.1_
  - [ ]* 4.6 Write unit tests in `finflow_architecture_tests/tests/test_agent_params.py`.
    - Reject unsupported `file_type` for `IngestionAgentParams`, require `CleaningOperationPlan` for `CleaningAgentParams`, accept the new `mode` literal and `operations` list, require `FilterOperationPlan` for `FilterAgentParams`, and reject `output_format="pdf"` for `ReportingAgentParams`.
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 5. Implement `filter_prep` mode in the Cleaning Agent (Component 7)
  - [x] 5.1 Update `src/finflow_agent/agents/cleaning_agent.py` so `execute(params, input_data)` dispatches on `params.mode`.
    - When `params.mode == "filter_prep"`, run only the seven safe operations from `params.operations` (`trim_whitespace`, `normalize_column_names`, `normalize_empty_strings`, `safe_numeric_conversion`, `safe_currency_conversion`, `safe_date_detection`, `categorical_value_normalization`) and refuse any operation outside that list with `AgentResult(status="failed", error_message=...)`.
    - When `params.mode == "filter_prep"`, append `{"origin": "filter_prep"}` to every entry in `AgentResult.operations_applied` so the audit writer can identify the entries.
    - When `params.mode == "filter_prep"`, the agent MUST NOT drop rows with partial nulls, impute missing values, remove non-exact duplicates, drop columns containing nulls, rewrite low-confidence values, or apply business-specific transformations.
    - Continue returning the same `AgentResult` envelope shape (`status` ∈ `{success, partial, failed}`).
    - _Requirements: 2.7, 2.8, 2.9, 5.1, 5.2, 5.3, 5.4_
  - [x] 5.2 Update `src/finflow_agent/operations/cleaning_handlers.py` to expose a `SAFE_FILTER_PREP_OPERATIONS` whitelist constant and to ensure each safe operation handler is non-destructive.
    - Add a guard helper `assert_safe_for_filter_prep(operation)` that raises a controlled error when invoked with any non-whitelisted operation.
    - _Requirements: 2.7, 2.8, 2.9_
  - [ ]* 5.3 Write unit tests for `filter_prep` in `finflow_architecture_tests/tests/test_cleaning_agent_filter_prep.py`.
    - Verify each of the seven safe operations runs, that the seven forbidden destructive operations are rejected, and that every entry in `operations_applied` carries the `{"origin": "filter_prep"}` marker.
    - _Requirements: 2.7, 2.8, 2.9, 5.3_

- [x] 6. Wire Column Resolver into the Filter Agent
  - [x] 6.1 Update `src/finflow_agent/agents/filter_agent.py` so it:
    - Reads its dataframe exclusively from `input_data["input_dataframe"]` and returns `AgentResult(status="failed", error_message="input_dataframe is required. No input dataframe provided.")` when it is `None`.
    - Builds a `DataFrameProfile` of the incoming dataframe and calls `resolve_columns` for every requested field referenced by `params.plan.conditions`.
    - For each `ColumnResolution` with `confidence < CONFIDENCE_THRESHOLD`, applies `LOW_CONFIDENCE_POLICY`: `warn` (append warning + skip the condition), `fail` (return `AgentResult(status="failed", error_message=...)` naming requested field, matched column, and confidence), or `quarantine` (return an `AgentResult` that signals quarantine to the orchestrator and does not apply the condition).
    - Appends each `ColumnResolution` to `AgentResult.artifacts["column_mapping"]` so the audit writer can publish the `column_mapping` sheet.
    - Translates filter conditions to deterministic boolean masks; MUST NOT pass any LLM-supplied string to `pandas.DataFrame.query` or any other code-evaluation surface.
    - _Requirements: 5.5, 7.6, 7.7, 7.8, 7.9, 11.4, 11.5, 12.4_
  - [ ]* 6.2 Write unit tests in `finflow_architecture_tests/tests/test_filter_agent_resolver.py`.
    - Cover the three `LOW_CONFIDENCE_POLICY` branches, the `input_dataframe is required` precondition failure, and the `column_mapping` artifact contents.
    - _Requirements: 5.5, 7.6, 7.7, 7.8, 7.9, 11.4, 11.5_
  - [ ]* 6.3 Write property test for confidence-threshold safety in `finflow_architecture_tests/tests/test_filter_agent_resolver.py`.
    - **Property 8: Confidence threshold** — for any generated profile and filter condition, when the resolved confidence is `< 0.75`, the filter agent never silently applies the condition.
    - **Validates: Requirements 7.6, 7.7, 7.8, 7.9**

- [x] 7. Update the Compiler (Component 6)
  - [x] 7.1 Update `src/finflow_agent/planning/compiler.py` to implement `compile_intent_to_plan` per design Component 6 and the `compile_intent_to_plan` algorithm.
    - Always emit `ingestion_agent` first and `reporting_agent` last.
    - Emit a `cleaning_agent` step with `params.mode == "clean"` and `output_key == "df_cleaned"` when `intent.needs_cleaning and intent.cleaning_plan is not None`.
    - Insert a `filter_prep` step (a `cleaning_agent` invocation with `params == {"mode": "filter_prep", "operations": [trim_whitespace, normalize_column_names, normalize_empty_strings, safe_numeric_conversion, safe_currency_conversion, safe_date_detection, categorical_value_normalization]}` and `output_key == "df_filter_prepared"`) when `intent.needs_filtering and intent.filter_plan is not None and not intent.needs_cleaning`.
    - Wire the `filter_agent` step's `input_from` to `["df_cleaned"]` (when full cleaning ran) or `["df_filter_prepared"]` (when filter_prep ran). It MUST never reference `["df_ingested"]`.
    - Insert a `visualization_agent` step only when `intent.needs_visualization and intent.visualization_plan is not None and ENABLE_VISUALIZATION`.
    - Restrict every emitted `output_key` to the canonical set `{df_ingested, df_cleaned, df_filter_prepared, df_filtered, df_visualized, report_output}`.
    - Define and raise `VisualizationDisabledError("Visualization was requested, but visualization_agent is not enabled in this version")` when `intent.needs_visualization` is true but `ENABLE_VISUALIZATION` is false.
    - Raise `ValueError` naming the missing field whenever `intent.needs_X` is true and `intent.X_plan` is `None` for any `X ∈ {cleaning, filtering, calculation, visualization}`.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14, 2.15, 2.16, 2.17, 9.2_
  - [ ]* 7.2 Write unit tests in `finflow_architecture_tests/tests/test_compiler.py`.
    - Cover clean-only, clean+filter, filter-only (verifies `filter_prep` insertion), `needs_X` without `X_plan` raising `ValueError`, and `needs_visualization` with `ENABLE_VISUALIZATION=false` raising `VisualizationDisabledError`.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.10, 2.13, 2.14, 9.2_
  - [ ]* 7.3 Write property test for compiler shape stability in `finflow_architecture_tests/tests/test_compiler.py`.
    - **Property 3: Compiler shape stability** — for any valid `PlanIntent`, the compiled plan starts with `ingestion_agent`, ends with `reporting_agent`, every `output_key` is from the canonical set, every `filter_agent` step's `input_from` is `["df_cleaned"]` or `["df_filter_prepared"]` (never `["df_ingested"]`), and a `filter_prep` step is present iff `needs_filtering and not needs_cleaning`.
    - **Validates: Requirements 2.1, 2.5, 2.6, 2.10, 2.14, 2.15**

- [x] 8. Update the Plan Validator (Component 3)
  - [x] 8.1 Update `src/finflow_agent/planning/validators.py` so `validate_plan(plan)` performs every check from design Component 3 and the `validate_plan` algorithm.
    - Reject duplicate `step_id`, unknown agents (message `"Unknown agent: <name>"`), broken `depends_on`, broken `input_from` (`"Step <id> input_from '<key>' not produced earlier"`), cycles in the dependency graph, and stage-ordering violations across `ingest → transform → analyze → visualize → deliver`.
    - Reject any step whose `agent == "visualization_agent"` while `ENABLE_VISUALIZATION=false` with the exact message `"visualization_agent is not enabled in this version"`.
    - Re-validate every step's `params` against the registered Pydantic param model; surface the Pydantic error message and the offending `step_id` on failure.
    - On success, return `(True, "")` without mutating the plan.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 9.1, 11.2, 11.3_
  - [ ]* 8.2 Write unit tests in `finflow_architecture_tests/tests/test_plan_validator.py`.
    - One assertion per validator branch (duplicate ids, unknown agent, missing dep, missing input_from key, cycle, stage ordering, invalid params, disabled visualization, accepted-valid clean+filter+report).
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_
  - [ ]* 8.3 Write property test for validator soundness in `finflow_architecture_tests/tests/test_plan_validator.py`.
    - **Property 4: Validator soundness** — for any generated `ExecutionPlan`, when `validate_plan` returns `(True, "")`, all six structural invariants hold (unique ids, every `input_from` produced earlier, no cycles, monotonic stage ordering, all agents registered, every params dict validates against its model).
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 3.9**
  - [ ]* 8.4 Write property test for validator completeness in `finflow_architecture_tests/tests/test_plan_validator.py`.
    - **Property 5: Validator completeness on failure** — for any generated malformed `ExecutionPlan`, `validate_plan` returns `(False, error)` where `error` names at least one violated rule and one offending step.
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8_

- [ ] 9. Update the Execution Engine
  - [ ] 9.1 Update `src/finflow_agent/execution/engine.py` so `execute(plan)` defensively re-validates per-step params and walks the DAG in topological order.
    - For every step, call `param_model.model_validate(step.params)` before instantiating the agent; on `ValidationError`, return a failed callback that names the offending `step_id` and includes the Pydantic error, and never invoke `agent.execute`.
    - Build `input_data` exclusively from `step.input_from`. The first dataframe-typed key resolves to `input_data["input_dataframe"]`. The engine MUST NOT pass any state-data key not referenced by `input_from`.
    - Stop the DAG walk on the first `AgentResult.status` value of `failed` or `partial` and return a failed callback naming the failed `step_id`.
    - On success, store the agent envelope under `step.output_key` (or `step.step_id` when `output_key` is `None`) and never under any other key.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.2, 10.6, 11.4_
  - [ ]* 9.2 Write unit tests in `finflow_architecture_tests/tests/test_execution_engine.py`.
    - Cover param re-validation failure, single-source `input_dataframe` resolution, topological ordering with `depends_on`, stop-on-`failed`, stop-on-`partial`, and `output_key` storage.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  - [ ]* 9.3 Write property test for single-source dataframe in `finflow_architecture_tests/tests/test_execution_engine.py`.
    - **Property 6: Single-source dataframe** — for any executed step, the agent receives exactly one `input_dataframe`, and that dataframe is the one produced by the upstream step referenced by `input_from`. Agents never read `state.data` directly.
    - **Validates: Requirements 4.3, 4.7, 5.5**
  - [ ]* 9.4 Write property test for param model gating in `finflow_architecture_tests/tests/test_execution_engine.py`.
    - **Property 7: Param model gating** — for every executed step, `param_model.model_validate(step.params)` succeeds before `agent.execute` is invoked; on validation failure the engine returns a failed callback and the agent's `execute` method is never called.
    - **Validates: Requirements 4.1, 4.2, 10.6**

- [ ] 10. Checkpoint - Ensure all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement the Reporting Agent and Audit Sheet Writer (Component 5)
  - [x] 11.1 Implement `write_excel_with_audit_sheets(payload, plan, output_dir, file_prefix)` and the `AuditSheetPayload` model in `src/finflow_agent/operations/reporting_handlers.py` per design Component 5.
    - Always write a `cleaned_data` sheet first, write `filtered_data` only when `payload.filtered_data is not None`, and always write `audit_log`, `warnings`, and `column_mapping` sheets (even when empty, with headers only).
    - Detect entries in `payload.audit_log` carrying `{"origin": "filter_prep"}` and record them in the `audit_log` sheet as an internal non-destructive normalization step.
    - Resolve every output path through `src/finflow_agent/storage/path_safety.py` (or `tools/path_safety.py`) so absolute paths and `..` traversal segments are rejected before any file is written.
    - Apply formatting (bold, frozen header rows, autofit columns) without rendering any chart.
    - Return `{"output_file_path": ..., "sheets_written": [...]}`.
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.7, 8.8, 8.9, 9.5_
  - [ ] 11.2 Update `src/finflow_agent/agents/reporting_agent.py` to delegate to the audit writer.
    - The agent MUST NOT modify any dataframe values and MUST NOT perform cleaning, filtering, calculation, or visualization.
    - When the `audit_log` payload contains any entry with `{"origin": "filter_prep"}` and the upstream `PlanIntent.needs_cleaning` was `false`, set `AgentResult.summary` to exactly `"Data was normalized for filtering."` and never claim that full cleaning was performed.
    - Pass the upstream `column_mapping` from the filter step's artifacts (task 6.1) into the audit payload.
    - _Requirements: 5.1, 5.2, 5.3, 8.6, 8.10, 9.5_
  - [ ]* 11.3 Write unit tests in `finflow_architecture_tests/tests/test_audit_sheet_writer.py`.
    - Verify `cleaned_data`, `audit_log`, `warnings`, `column_mapping` are always written; verify `filtered_data` is present only when supplied; verify the path-safety helper rejects absolute paths and `..` segments; verify no cleaning or filtering occurs inside the writer.
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_
  - [ ]* 11.4 Write property test for reporting purity in `finflow_architecture_tests/tests/test_audit_sheet_writer.py`.
    - **Property 11: Reporting purity** — for any payload, the resulting Excel file contains only the deterministic audit sheets (`cleaned_data`, optional `filtered_data`, `audit_log`, `warnings`, `column_mapping`) and the writer does not modify any dataframe values.
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

- [ ] 12. Update the Orchestrator and LLM contract
  - [ ] 12.1 Update `src/finflow_agent/orchestrator.py` and `src/finflow_agent/planning/orchestrator.py` so the planning loop:
    - Rejects any LLM response containing a top-level `steps` key and returns `{"status": "quarantined", "reason": ...}` whose reason names the legacy `steps` key. No `ExecutionPlan` is constructed in this branch.
    - Validates every other LLM response with `PlanIntent.model_validate(raw)` before invoking the compiler.
    - Returns a quarantine result when `intent.is_quarantined is True`, with `quarantine_reason` propagated, and never invokes the compiler.
    - Catches `VisualizationDisabledError` raised by the compiler and converts it to a quarantine result whose reason includes `"visualization_agent is not enabled in this version"`.
    - Constructs every successful `ExecutionPlan` exclusively via `compile_intent_to_plan`.
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 9.3, 11.1, 11.6_
  - [ ] 12.2 Update `src/finflow_agent/llm.py` (and any prompt-assembly helpers in `planning/orchestrator.py`).
    - Build the prompt from the sanitized `DataFrameProfile` only; do not include any full dataframe row.
    - Sample values come exclusively from `profile.columns[i].sample_values`, capped at three per column.
    - Add a system instruction stating the profile is untrusted data and any instructions inside cell values must be ignored.
    - Add an explicit guard so that no LLM-supplied string is forwarded to `pandas.DataFrame.query` or any other code-evaluation surface anywhere in the call path.
    - _Requirements: 1.3, 12.1, 12.2, 12.3, 12.4_
  - [ ]* 12.3 Write unit tests in `finflow_architecture_tests/tests/test_orchestrator_contract.py`.
    - Mock `call_groq_json`. Cover: response with top-level `steps` key → quarantine; valid `PlanIntent` shape → compiler invoked; `is_quarantined=True` → quarantine without compiler; compiler raising `VisualizationDisabledError` → quarantine with the canonical message.
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 9.3, 11.1, 11.6_
  - [ ]* 12.4 Write property test for `PlanIntent` purity in `finflow_architecture_tests/tests/test_orchestrator_contract.py`.
    - **Property 1: PlanIntent purity** — for every LLM response `r` parsed by the orchestrator, if `"steps" in r` then the orchestrator returns a quarantine dict and never returns an `ExecutionPlan`.
    - **Validates: Requirements 1.1, 11.1**
  - [ ]* 12.5 Write property test for prompt privacy in `finflow_architecture_tests/tests/test_orchestrator_contract.py`.
    - **Property 12: No raw spreadsheet rows in LLM prompts** — for every prompt assembled by the orchestrator, the prompt body contains no full dataframe row; sample values come only from `profile.columns[i].sample_values` and are capped per column.
    - **Validates: Requirements 1.3, 12.1, 12.2_

- [ ] 13. Visualization scaffolding
  - [x] 13.1 Update `src/finflow_agent/bootstrap.py` to register `visualization_agent` as disabled when `ENABLE_VISUALIZATION=false`. The registry entry MUST exist (so the validator's "unknown agent" error never fires for `visualization_agent`) but its `enabled` flag is `false` and the agent class refuses to run.
    - _Requirements: 9.1, 9.2_
  - [ ] 13.2 Audit `src/finflow_agent/agents/cleaning_agent.py`, `src/finflow_agent/agents/filter_agent.py`, and `src/finflow_agent/agents/reporting_agent.py` (and their handlers in `operations/`) to confirm none of them generate, render, or embed any chart in any output artifact. Add explicit guards or assertions where helpful.
    - _Requirements: 9.4, 9.5_
  - [ ]* 13.3 Write property test for visualization scaffolding safety in `finflow_architecture_tests/tests/test_visualization_scaffolding.py`.
    - **Property 10: Visualization scaffolding safety** — for any `PlanIntent` with `needs_visualization=True` while the visualization agent is disabled, no `ExecutionPlan` is executed; either the compiler raises `VisualizationDisabledError`, the orchestrator quarantines, or the validator rejects, and no chart is ever produced.
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 11.6**

- [ ] 14. AgentResult envelope
  - [ ]* 14.1 Write property test for `AgentResult` status closure in `finflow_architecture_tests/tests/test_agent_result_envelope.py`.
    - **Property 2: AgentResult status closure** — every `AgentResult` produced anywhere in the codebase has `status ∈ {"success", "partial", "failed"}`. Generate random tuples and verify `AgentResult.model_validate` accepts them only when `status` is in that set.
    - **Validates: Requirements 5.1**

- [ ] 15. Integration regression tests
  - [ ]* 15.1 Add the **Clean-only** integration test in `finflow_architecture_tests/tests/test_integration_pipeline.py`.
    - Instruction `"Clean this data"` + small CSV; assert plan is `[ingest, clean, report]`; assert the Excel file contains `cleaned_data`, `audit_log`, `warnings`, `column_mapping` sheets and does NOT contain a `filtered_data` sheet.
    - _Requirements: 2.1, 2.2, 8.1, 8.2, 8.4, 8.5_
  - [ ]* 15.2 Add the **Clean + filter** integration test in the same file.
    - Instruction `"Clean this data and show female age 45"`; assert plan is `[ingest, clean, filter, report]`; assert output contains both `cleaned_data` and `filtered_data` sheets; assert `column_mapping` lists `gender` and `age` resolutions with `confidence >= 0.75`.
    - _Requirements: 2.5, 7.1, 7.5, 8.2, 8.3_
  - [ ]* 15.3 Add the **Visualization disabled** integration test in the same file.
    - Instruction `"Clean this data and visualize genders between age 45 to 75"`; assert the orchestrator returns a quarantine result, no chart is in the output, and no exception leaks past the orchestrator.
    - _Requirements: 9.1, 9.2, 9.3, 11.6_
  - [ ]* 15.4 Add the **Unknown agent** integration test in the same file.
    - Hand-craft a plan with `agent="bogus_agent"`; assert `validate_plan` returns `(False, "Unknown agent: bogus_agent")` and the engine refuses to run the plan.
    - _Requirements: 3.2, 11.2_
  - [ ]* 15.5 Add the **Bad input_from** integration test in the same file.
    - Hand-craft a plan referencing `input_from=["df_missing"]`; assert the validator returns `(False, "...input_from 'df_missing'...")`.
    - _Requirements: 3.4, 11.3_
  - [ ]* 15.6 Add the **Filter agent reads input_dataframe only** integration test in the same file.
    - Monkeypatch the engine to populate unrelated keys in `state.data`; assert the filter agent uses only `input_data["input_dataframe"]` and ignores any random previous state.
    - _Requirements: 4.7, 5.5_
  - [ ]* 15.7 Add the **LLM cannot output direct steps** integration test in the same file.
    - Mock the LLM to return a top-level `steps` key; assert the orchestrator returns `{"status": "quarantined", ...}` and no `ExecutionPlan` is built.
    - _Requirements: 1.1, 11.1_
  - [ ]* 15.8 Add the **Filter-only end-to-end** integration test in the same file.
    - Instruction `"Show female age 45 in this data"` (no cleaning requested) + a small CSV with mixed-case columns and trailing whitespace.
    - Assert the compiled plan is exactly `[ingest, filter_prep, filter, report]`.
    - Assert the `filter_prep` step is a `cleaning_agent` invocation with `params.mode == "filter_prep"` and `output_key == "df_filter_prepared"`.
    - Assert the `filter_agent` step's `input_from == ["df_filter_prepared"]`.
    - Assert the produced Excel `audit_log` sheet contains a row marked as an internal non-destructive normalization for the `filter_prep` step.
    - Assert the reporting summary equals exactly `"Data was normalized for filtering."`.
    - _Requirements: 2.6, 2.7, 2.10, 2.16, 2.17, 8.9, 8.10_

- [ ] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP. Core implementation tasks (no `*`) are required.
- Each task references the specific requirement clauses it satisfies for traceability.
- Each property-based test sub-task is its own line, annotated with its property number from the design's Correctness Properties section and the requirement clauses it validates.
- Property tests are placed close to the implementation that produces the property so failures surface early.
- Integration tests cover the seven scenarios from the design's Integration Tests section plus the dedicated filter-only end-to-end scenario.
- `bootstrap.py` is touched by tasks 1 and 13; the dependency graph schedules them in different waves so they do not conflict. The same applies to `cleaning_agent.py` (tasks 4.2 then 5.1).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "4.1", "4.5"] },
    { "id": 1, "tasks": ["2.2", "2.3", "3.1", "4.2", "4.3", "4.4", "13.1"] },
    { "id": 2, "tasks": ["3.2", "3.3", "4.6", "5.1", "5.2", "6.1", "13.2"] },
    { "id": 3, "tasks": ["5.3", "6.2", "6.3", "7.1"] },
    { "id": 4, "tasks": ["7.2", "7.3", "8.1"] },
    { "id": 5, "tasks": ["8.2", "8.3", "8.4", "9.1"] },
    { "id": 6, "tasks": ["9.2", "9.3", "9.4", "11.1"] },
    { "id": 7, "tasks": ["11.2", "12.1", "12.2"] },
    { "id": 8, "tasks": ["11.3", "11.4", "12.3", "12.4", "12.5", "13.3", "14.1"] },
    { "id": 9, "tasks": ["15.1", "15.2", "15.3", "15.4", "15.5", "15.6", "15.7", "15.8"] }
  ]
}
```
