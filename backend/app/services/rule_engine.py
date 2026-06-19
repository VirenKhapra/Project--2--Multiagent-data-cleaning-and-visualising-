from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.services.json_safety import make_json_safe


def build_validation_warnings(frame: pd.DataFrame, constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
    for constraint in constraints:
        column = str(constraint.get("column", "")).strip()
        rule = str(constraint.get("rule", "")).strip()
        if not rule:
            continue

        if column == "*" and rule == "forbidden_substring":
            forbidden_value = _normalize_text_fragment(str(constraint.get("value", "")).strip())
            if not forbidden_value:
                continue
            for candidate_column in frame.columns:
                values = frame[candidate_column].dropna().astype(str)
                normalized_values = values.map(_normalize_text_fragment)
                invalid = values[normalized_values.str.contains(re.escape(forbidden_value), regex=True)]
                if invalid.empty:
                    continue
                warnings.append(
                    _warning_payload(
                        column=str(candidate_column),
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
            continue

        if column not in frame.columns:
            continue

        series = frame[column]
        if rule == "required":
            invalid = series[series.isna() | series.astype(str).str.strip().eq("")]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "error")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "unique":
            values = series.dropna().astype(str).str.strip()
            values = values[values != ""]
            invalid = values[values.duplicated(keep=False)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "error")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.drop_duplicates().head(3).tolist(),
                    )
                )
        elif rule == "non_negative":
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = numeric[numeric < 0]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(invalid.notna().sum()),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "numeric_range":
            min_value = _coerce_number(constraint.get("min_value"))
            max_value = _coerce_number(constraint.get("max_value"))
            if min_value is None and max_value is None:
                continue
            values = series.dropna()
            numeric = pd.to_numeric(values, errors="coerce")
            invalid_mask = numeric.isna()
            if min_value is not None:
                invalid_mask = invalid_mask | (numeric < min_value)
            if max_value is not None:
                invalid_mask = invalid_mask | (numeric > max_value)
            invalid = values[invalid_mask]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "percentage_range":
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = numeric[(numeric < 0) | (numeric > 100)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(invalid.notna().sum()),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "date_not_future":
            parsed = pd.to_datetime(series, errors="coerce")
            invalid = parsed[parsed > now_utc]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(invalid.notna().sum()),
                        sample_values=[value.isoformat() for value in invalid.head(3).tolist()],
                    )
                )
        elif rule == "date_range":
            min_date = _coerce_timestamp(constraint.get("min_date"))
            max_date = _coerce_timestamp(constraint.get("max_date"))
            if min_date is None and max_date is None:
                continue
            values = series.dropna()
            parsed = pd.to_datetime(values, errors="coerce")
            invalid_mask = parsed.isna()
            if min_date is not None:
                invalid_mask = invalid_mask | (parsed < min_date)
            if max_date is not None:
                invalid_mask = invalid_mask | (parsed > max_date)
            invalid = values[invalid_mask]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "starts_with":
            expected_prefix = str(constraint.get("value", "")).strip()
            if not expected_prefix:
                continue
            values = series.dropna().astype(str)
            invalid = values[~values.str.startswith(expected_prefix)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "ends_with":
            expected_suffix = str(constraint.get("value", "")).strip()
            if not expected_suffix:
                continue
            values = series.dropna().astype(str)
            invalid = values[~values.str.endswith(expected_suffix)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "contains":
            expected_value = _normalize_text_fragment(str(constraint.get("value", "")).strip())
            if not expected_value:
                continue
            values = series.dropna().astype(str)
            normalized_values = values.map(_normalize_text_fragment)
            invalid = values[~normalized_values.str.contains(re.escape(expected_value), regex=True)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "regex_match":
            pattern = str(constraint.get("pattern", "")).strip()
            if not pattern:
                continue
            values = series.dropna().astype(str)
            invalid = values[~values.str.match(pattern, na=False)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "allowed_values":
            allowed_values = {
                str(value).strip().upper()
                for value in constraint.get("allowed_values", [])
                if str(value).strip()
            }
            if not allowed_values:
                continue
            values = series.dropna().astype(str)
            invalid = values[~values.str.upper().isin(allowed_values)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "not_allowed_values":
            blocked_values = {
                str(value).strip().upper()
                for value in constraint.get("not_allowed_values", [])
                if str(value).strip()
            }
            if not blocked_values:
                continue
            values = series.dropna().astype(str)
            invalid = values[values.str.upper().isin(blocked_values)]
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "error")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "length_range":
            min_length = constraint.get("min_length")
            max_length = constraint.get("max_length")
            values = series.dropna().astype(str)
            lengths = values.str.len()
            invalid = values
            if min_length is not None:
                invalid = invalid[lengths < int(min_length)]
            if max_length is not None:
                invalid = pd.concat([invalid, values[lengths > int(max_length)]]).drop_duplicates()
            if not invalid.empty:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "warning")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=int(len(invalid)),
                        sample_values=invalid.head(3).tolist(),
                    )
                )
        elif rule == "cross_field_compare":
            compare_column = str(constraint.get("compare_column", "")).strip()
            operator = str(constraint.get("operator", "")).strip()
            if compare_column not in frame.columns or operator not in {"<", "<=", ">", ">=", "==", "!="}:
                continue
            invalid = _invalid_cross_field_values(frame, column, compare_column, operator)
            if invalid:
                warnings.append(
                    _warning_payload(
                        column=column,
                        rule=rule,
                        severity=str(constraint.get("severity", "error")),
                        reason=str(constraint.get("reason", "")),
                        invalid_count=len(invalid),
                        sample_values=invalid[:3],
                    )
                )
    return warnings


def _warning_payload(
    *,
    column: str,
    rule: str,
    severity: str,
    reason: str,
    invalid_count: int,
    sample_values: list[Any],
) -> dict[str, Any]:
    return {
        "column": column,
        "rule": rule,
        "severity": severity,
        "reason": reason,
        "invalid_count": invalid_count,
        "sample_values": make_json_safe(sample_values),
    }


def _normalize_text_fragment(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _coerce_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    try:
        parsed = pd.Timestamp(value)
        if parsed.tzinfo is not None:
            parsed = parsed.tz_convert("UTC").tz_localize(None)
        return parsed
    except Exception:
        return None


def _invalid_cross_field_values(
    frame: pd.DataFrame,
    column: str,
    compare_column: str,
    operator: str,
) -> list[dict[str, Any]]:
    left_raw = frame[column]
    right_raw = frame[compare_column]
    left = pd.to_numeric(left_raw, errors="coerce")
    right = pd.to_numeric(right_raw, errors="coerce")
    comparable = left_raw.notna() & right_raw.notna() & left.notna() & right.notna()
    if operator == "<":
        valid = left < right
    elif operator == "<=":
        valid = left <= right
    elif operator == ">":
        valid = left > right
    elif operator == ">=":
        valid = left >= right
    elif operator == "==":
        valid = left == right
    else:
        valid = left != right
    invalid_mask = comparable & ~valid
    invalid_rows = frame.loc[invalid_mask, [column, compare_column]]
    return invalid_rows.to_dict(orient="records")
