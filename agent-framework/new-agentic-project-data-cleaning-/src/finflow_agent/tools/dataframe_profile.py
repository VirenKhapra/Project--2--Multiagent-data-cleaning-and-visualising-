"""DataFrame profiler for the FinFlow Agent Service.

Produces a small, sanitized profile of an uploaded dataframe for use by the
LLM and the column resolver. The profile NEVER includes a full dataframe
row; per-column samples are sanitized, capped at three entries, and any
stringified value is truncated to 64 characters.

This module implements design Component 1 of the agent-pipeline-hardening
spec and corresponds to acceptance criteria 6.1 - 6.8.
"""

from __future__ import annotations

import math
import re
from typing import Any, List, Literal, Tuple

import pandas as pd
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Public Pydantic models
# ---------------------------------------------------------------------------

SemanticGuess = Literal[
    "date",
    "currency",
    "numeric",
    "categorical",
    "boolean",
    "string",
    "unknown",
]


class ColumnProfile(BaseModel):
    """Sanitized profile of a single dataframe column."""

    original_name: str
    normalized_name: str
    dtype: str
    null_count: int = Field(ge=0)
    sample_values: List[Any] = Field(default_factory=list, max_length=3)
    semantic_guess: SemanticGuess = "unknown"
    confidence: float = Field(ge=0.0, le=1.0)


class DataFrameProfile(BaseModel):
    """Sanitized, schema-flexible profile of a dataframe.

    Never contains a full row. Per-column ``sample_values`` are capped at 3.
    """

    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    columns: List[ColumnProfile]
    duplicate_row_count: int = Field(ge=0)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_SAMPLE_STR_LEN: int = 64
_MAX_SAMPLES_PER_COLUMN: int = 3
_MEMORY_WARNING_BYTES: int = 50_000_000  # >50 MB

_DATE_NAME_HINTS: Tuple[str, ...] = (
    "date",
    "time",
    "timestamp",
    "dob",
    "birthday",
    "birth_date",
    "created",
    "modified",
    "updated",
    "_at",
)

_CURRENCY_NAME_HINTS: Tuple[str, ...] = (
    "price",
    "amount",
    "cost",
    "revenue",
    "total",
    "fee",
    "salary",
    "income",
    "balance",
    "currency",
    "usd",
    "eur",
    "gbp",
)

_CURRENCY_SYMBOLS: Tuple[str, ...] = ("$", "€", "£", "¥", "₹")


def _normalize_name(name: Any) -> str:
    """Lowercase, collapse whitespace and dashes, drop other special characters.

    Deterministic: identical inputs always map to the identical normalized name.
    """
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def sanitize_value(value: Any) -> Any:
    """Coerce a sample value to a JSON-safe scalar.

    - ``None`` and non-finite floats (NaN, +/- inf) become ``None``.
    - ``bool``, finite ``int``/``float`` are returned as-is.
    - Strings have ASCII control characters (other than ``\\t``/``\\n``) stripped
      and are truncated to at most 64 characters.
    - Anything else is coerced via ``str(...)`` and then sanitized as a string.
    """
    if value is None:
        return None
    # NaN / inf check (must come before the broader numeric branch because
    # bool is a subclass of int, but NaN is only ever a float).
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value
    else:
        s = str(value)
    # Strip ASCII control characters but preserve tab/newline for readability.
    s = "".join(ch for ch in s if ch in ("\t", "\n") or ord(ch) >= 32)
    if len(s) > _MAX_SAMPLE_STR_LEN:
        s = s[:_MAX_SAMPLE_STR_LEN]
    return s


def infer_semantic_type(
    col_name: Any,
    col_series: pd.Series,
) -> Tuple[SemanticGuess, float]:
    """Classify *col_series* as one of the supported semantic types.

    Returns a ``(semantic_guess, confidence)`` tuple. ``confidence`` is in
    ``[0.0, 1.0]`` and the function is deterministic: the same inputs always
    produce the same output.
    """
    name_lower = str(col_name).strip().lower()

    # 1. Boolean dtype is unambiguous.
    if pd.api.types.is_bool_dtype(col_series):
        return ("boolean", 1.0)

    # 2. Native datetime dtype is unambiguous.
    if pd.api.types.is_datetime64_any_dtype(col_series):
        return ("date", 1.0)

    is_numeric = pd.api.types.is_numeric_dtype(col_series)
    is_string_like = (
        pd.api.types.is_string_dtype(col_series)
        or pd.api.types.is_object_dtype(col_series)
    )

    # 3. Date hint in column name.
    if any(hint in name_lower for hint in _DATE_NAME_HINTS):
        if is_string_like:
            non_null = col_series.dropna().head(20)
            if len(non_null) > 0:
                try:
                    parsed = pd.to_datetime(non_null, errors="coerce")
                    parse_rate = parsed.notna().sum() / len(non_null)
                    if parse_rate >= 0.6:
                        return ("date", 0.9)
                except Exception:  # pragma: no cover - defensive
                    pass
        return ("date", 0.7)

    # 4. Currency hint in column name.
    if any(hint in name_lower for hint in _CURRENCY_NAME_HINTS):
        if is_numeric:
            return ("currency", 0.9)
        if is_string_like:
            non_null = col_series.dropna().astype(str).head(20)
            if len(non_null) > 0:
                hits = sum(
                    any(sym in v for sym in _CURRENCY_SYMBOLS) for v in non_null
                )
                if hits / len(non_null) >= 0.5:
                    return ("currency", 0.85)
        return ("currency", 0.7)

    # 5. Currency by content (no name hint).
    if is_string_like:
        non_null = col_series.dropna().astype(str).head(20)
        if len(non_null) > 0:
            hits = sum(any(sym in v for sym in _CURRENCY_SYMBOLS) for v in non_null)
            if hits / len(non_null) >= 0.7:
                return ("currency", 0.8)

    # 6. Numeric without currency cues.
    if is_numeric:
        return ("numeric", 0.85)

    # 7. Categorical vs string for object/string columns.
    if is_string_like:
        non_null_count = int(col_series.notna().sum())
        if non_null_count == 0:
            return ("string", 0.5)
        nunique = int(col_series.nunique(dropna=True))
        if (
            nunique <= 20
            and non_null_count >= 5
            and (nunique / non_null_count) <= 0.5
        ):
            return ("categorical", 0.75)
        return ("string", 0.6)

    return ("unknown", 0.0)


# ---------------------------------------------------------------------------
# Public profiler
# ---------------------------------------------------------------------------

def profile_dataframe(
    df: pd.DataFrame,
    sample_rows: int = 3,
    include_samples: bool = False,
) -> DataFrameProfile:
    """Produce a sanitized :class:`DataFrameProfile` of *df*.

    The returned profile is schema-flexible: it works for any dataframe
    regardless of column names or dtypes.

    Guarantees (acceptance criteria 6.1 - 6.8):

    * ``len(profile.columns) == df.shape[1]``
    * ``profile.row_count == df.shape[0]``
    * Every ``ColumnProfile.sample_values`` has length ``<= 3``.
    * Every stringified sample value has length ``<= 64`` characters.
    * No full dataframe row appears anywhere in the returned model.
    * When ``include_samples`` is ``False``, every column's ``sample_values``
      is the empty list.
    * A warning is appended when ``df.memory_usage(deep=True).sum() > 50 MB``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("profile_dataframe requires a pandas DataFrame")
    sample_rows_int = int(sample_rows)
    if not (0 <= sample_rows_int <= 5):
        raise ValueError("sample_rows must be in [0, 5]")

    column_profiles: List[ColumnProfile] = []
    warnings: List[str] = []

    for col_name in df.columns:
        col_series = df[col_name]
        original_name = str(col_name)

        # Sample collection: NEVER include full rows; only per-column values.
        if include_samples and sample_rows_int > 0:
            raw_samples = col_series.dropna().head(sample_rows_int).tolist()
            sanitized: List[Any] = [
                sanitize_value(v) for v in raw_samples
            ][:_MAX_SAMPLES_PER_COLUMN]
        else:
            sanitized = []

        semantic_guess, confidence = infer_semantic_type(original_name, col_series)

        column_profiles.append(
            ColumnProfile(
                original_name=original_name,
                normalized_name=_normalize_name(original_name),
                dtype=str(col_series.dtype),
                null_count=int(col_series.isnull().sum()),
                sample_values=sanitized,
                semantic_guess=semantic_guess,
                confidence=float(confidence),
            )
        )

    duplicate_row_count = int(df.duplicated().sum())
    memory_bytes = int(df.memory_usage(deep=True).sum())

    if memory_bytes > _MEMORY_WARNING_BYTES:
        warnings.append(
            f"DataFrame exceeds 50MB (deep memory: {memory_bytes} bytes). "
            "Consider sampling."
        )

    return DataFrameProfile(
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        columns=column_profiles,
        duplicate_row_count=duplicate_row_count,
        warnings=warnings,
    )


__all__ = [
    "ColumnProfile",
    "DataFrameProfile",
    "SemanticGuess",
    "infer_semantic_type",
    "sanitize_value",
    "profile_dataframe",
]
