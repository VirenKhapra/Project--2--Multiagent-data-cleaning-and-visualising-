"""Focused, deterministic tests for `cleaning_agent`'s `filter_prep` mode and
`clean` mode dispatch.

These tests exercise the agent class directly (not through the engine) and run
purely against in-memory DataFrames. No real LLM is invoked: the `clean` path
tests either leave `GROQ_API_KEY` unset or rely on the agent's own
short-circuit behavior when `params.plan` is supplied.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from finflow_agent.agents.cleaning_agent import CleaningAgent, CleaningAgentParams
from finflow_agent.operations.schemas import (
    CleaningOperationPlan,
    NormalizeColumnNamesOperation,
    TrimWhitespaceOperation,
)


SAFE_OPS = [
    "trim_whitespace",
    "normalize_column_names",
    "normalize_empty_strings",
    "safe_numeric_conversion",
    "safe_currency_conversion",
    "safe_date_detection",
    "categorical_value_normalization",
]


def _build_mixed_df() -> pd.DataFrame:
    """Small DataFrame with mixed-case column names, leading/trailing
    whitespace in string values, and one numeric-looking string column.
    """
    return pd.DataFrame(
        {
            "First Name": ["  Alice  ", "Bob", " Carol", "Dan ", "Eve"],
            "Age": ["25", "30", "35", "40", "45"],
            "Status": [" Active ", " Inactive ", "Active ", " Active", "Inactive"],
        }
    )


# ---------------------------------------------------------------------------
# 1. filter_prep dispatch + non-destructive guarantees
# ---------------------------------------------------------------------------

def test_filter_prep_dispatches_when_mode_is_filter_prep(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = _build_mixed_df()

    result = CleaningAgent().execute(
        {"mode": "filter_prep", "operations": list(SAFE_OPS)},
        {"input_dataframe": df},
    )

    assert result.status == "success", result.error_message

    # Column names normalized to snake_case.
    assert list(result.data.columns) == ["first_name", "age", "status"]

    # No row drops.
    assert len(result.data) == len(df) == 5

    # No column drops.
    assert result.data.shape[1] == df.shape[1] == 3

    # String whitespace was trimmed in surviving string columns. The "age"
    # column has been promoted to numeric by `safe_numeric_conversion`, so
    # only inspect the columns that are still object/string dtype.
    for col in result.data.columns:
        series = result.data[col]
        if series.dtype == object or pd.api.types.is_string_dtype(series):
            for val in series.dropna():
                assert isinstance(val, str)
                assert val == val.strip(), (
                    f"Found leading/trailing whitespace in {col!r}: {val!r}"
                )


# ---------------------------------------------------------------------------
# 2. operations_applied marker + count
# ---------------------------------------------------------------------------

def test_filter_prep_stamps_origin_marker_on_every_operation(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = _build_mixed_df()

    result = CleaningAgent().execute(
        {"mode": "filter_prep", "operations": list(SAFE_OPS)},
        {"input_dataframe": df},
    )

    assert result.status == "success", result.error_message
    assert len(result.operations_applied) == 7

    for entry in result.operations_applied:
        assert entry["origin"] == "filter_prep", entry


# ---------------------------------------------------------------------------
# 3. unsafe-operation refusal (single op)
# ---------------------------------------------------------------------------

def test_filter_prep_refuses_unsafe_operation(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = _build_mixed_df()

    result = CleaningAgent().execute(
        {"mode": "filter_prep", "operations": ["drop_duplicates"]},
        {"input_dataframe": df},
    )

    assert result.status == "failed"
    assert result.error_message is not None
    assert "drop_duplicates" in result.error_message
    assert "filter_prep" in result.error_message


# ---------------------------------------------------------------------------
# 4. each destructive op individually
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "destructive_op",
    [
        "drop_duplicates",
        "fill_nulls",
        "drop_nulls",
        "remove_empty_rows",
        "remove_empty_columns",
        "rename_columns",
        "reorder_columns",
        "replace_values",
    ],
)
def test_filter_prep_refuses_each_destructive_op_individually(
    destructive_op, monkeypatch
):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = _build_mixed_df()

    result = CleaningAgent().execute(
        {"mode": "filter_prep", "operations": [destructive_op]},
        {"input_dataframe": df},
    )

    assert result.status == "failed", (
        f"Expected filter_prep to refuse {destructive_op!r} but got success"
    )
    assert result.error_message is not None
    assert destructive_op in result.error_message


# ---------------------------------------------------------------------------
# 5. partial nulls do not trigger row drops
# ---------------------------------------------------------------------------

def test_filter_prep_does_not_drop_rows_with_partial_nulls(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "label": ["a", None, "b", None, "c"],
        }
    )

    result = CleaningAgent().execute(
        {"mode": "filter_prep", "operations": list(SAFE_OPS)},
        {"input_dataframe": df},
    )

    assert result.status == "success", result.error_message
    assert len(result.data) == 5


# ---------------------------------------------------------------------------
# 6. NaN / missing values are NOT imputed
# ---------------------------------------------------------------------------

def test_filter_prep_does_not_impute_missing_values(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "value": [10.0, np.nan, 30.0],
            "name": ["alice", None, "bob"],
        }
    )

    result = CleaningAgent().execute(
        {"mode": "filter_prep", "operations": list(SAFE_OPS)},
        {"input_dataframe": df},
    )

    assert result.status == "success", result.error_message

    # Numeric NaN preserved (not 0, not mean=20.0).
    assert pd.isna(result.data["value"].iloc[1])
    assert result.data["value"].iloc[1] != 0
    # Non-null entries unchanged.
    assert result.data["value"].iloc[0] == 10.0
    assert result.data["value"].iloc[2] == 30.0

    # String-column null preserved (not "", not a placeholder).
    assert pd.isna(result.data["name"].iloc[1])


# ---------------------------------------------------------------------------
# 7. missing input_dataframe -> failed
# ---------------------------------------------------------------------------

def test_filter_prep_missing_input_dataframe_returns_failed(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = CleaningAgent().execute(
        {"mode": "filter_prep", "operations": ["trim_whitespace"]},
        {},
    )

    assert result.status == "failed"
    assert result.error_message is not None
    assert "input_dataframe" in result.error_message


# ---------------------------------------------------------------------------
# 8. missing operations -> failed (CleaningAgentParams contract)
# ---------------------------------------------------------------------------

def test_filter_prep_missing_operations_returns_failed(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = _build_mixed_df()

    # Validator-level rejection: filter_prep mode without operations is invalid.
    with pytest.raises(Exception):
        CleaningAgentParams.model_validate({"mode": "filter_prep"})

    # Agent-level rejection: same call shape via the runtime path returns a
    # failed envelope rather than crashing.
    result = CleaningAgent().execute(
        {"mode": "filter_prep"},
        {"input_dataframe": df},
    )

    assert result.status == "failed"
    assert result.error_message is not None


# ---------------------------------------------------------------------------
# 9. clean mode does NOT carry the filter_prep marker
# ---------------------------------------------------------------------------

def test_clean_mode_does_not_carry_filter_prep_marker(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    df = _build_mixed_df()

    plan = CleaningOperationPlan(
        operations=[TrimWhitespaceOperation(columns="__all_string_columns__")]
    )

    result = CleaningAgent().execute(
        {"mode": "clean", "plan": plan.model_dump()},
        {"input_dataframe": df},
    )

    assert result.status == "success", result.error_message
    assert len(result.operations_applied) >= 1
    for entry in result.operations_applied:
        assert entry.get("origin") != "filter_prep", entry


# ---------------------------------------------------------------------------
# 10. clean mode with compiler-emitted params bypasses the LLM path
# ---------------------------------------------------------------------------

def test_clean_mode_with_compiler_emitted_params_bypasses_llm_path(monkeypatch):
    """With GROQ_API_KEY set, the LLM branch could fire — but a supplied
    `params.plan` must short-circuit it. The clean path should run the
    deterministic executor only, with no langchain-groq import attempt.
    """
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")

    # Sentinel: if the agent ever reaches the LLM branch, it imports
    # `get_chat_groq` from `finflow_agent.llm`. Patch it to blow up so
    # accidental invocation is loud rather than silent.
    import finflow_agent.agents.cleaning_agent as cleaning_agent_module

    def _explode(*args, **kwargs):  # pragma: no cover - guard rail
        raise AssertionError(
            "LLM path was invoked despite params.plan being supplied"
        )

    monkeypatch.setattr(cleaning_agent_module, "get_chat_groq", _explode)

    df = _build_mixed_df()
    plan = CleaningOperationPlan(
        operations=[
            TrimWhitespaceOperation(columns="__all_string_columns__"),
            NormalizeColumnNamesOperation(style="snake_case"),
        ]
    )

    result = CleaningAgent().execute(
        {"mode": "clean", "plan": plan.model_dump()},
        {"input_dataframe": df},
    )

    assert result.status == "success", result.error_message
    # Deterministic plan ran end-to-end.
    assert len(result.operations_applied) == 2
    # And no filter_prep marker leaked into the clean path.
    for entry in result.operations_applied:
        assert entry.get("origin") != "filter_prep", entry
