from __future__ import annotations

import json
import os
import re
from typing import Any

from app.services.rule_types import SEMANTIC_HINTS, SUPPORTED_RULE_TYPES


def extract_prompt_constraints(
    source_columns: list[str],
    preview_rows: list[dict[str, Any]],
    instruction: str,
) -> list[dict[str, Any]]:
    llm_constraints = _extract_prompt_constraints_with_llm(source_columns, preview_rows, instruction)
    if llm_constraints:
        return llm_constraints
    return _extract_prompt_constraints_with_heuristics(source_columns, instruction)


def infer_semantic_constraints(
    source_columns: list[str],
    preview_rows: list[dict[str, Any]],
    instruction: str,
) -> list[dict[str, Any]]:
    allow_negative = False
    if instruction:
        if re.search(r'\b(?:unchanged|as\s+is|allow\s+negative|refunds?|keep\s+negative)\b', instruction.lower()):
            allow_negative = True

    llm_constraints = _infer_constraints_with_llm(source_columns, preview_rows, instruction)
    if llm_constraints:
        if allow_negative:
            llm_constraints = [c for c in llm_constraints if c.get("rule") != "non_negative"]
        return llm_constraints
    return _infer_constraints_with_heuristics(source_columns, instruction)


def merge_constraints(primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for group in (primary, fallback):
        for item in group:
            key = (str(item.get("column", "")), str(item.get("rule", "")))
            if not key[0] or not key[1] or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _infer_constraints_with_llm(
    source_columns: list[str],
    preview_rows: list[dict[str, Any]],
    instruction: str,
) -> list[dict[str, Any]]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or not source_columns:
        return []
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = f"""
Infer business validation constraints for a tabular upload.

Instruction:
{instruction or "No user instruction provided."}

Columns:
{json.dumps(source_columns)}

Preview rows:
{json.dumps(preview_rows[:5], default=str)}

Return ONLY valid JSON with this shape:
{{
  "constraints": [
    {{
      "column": "column_name",
      "rule": "non_negative|percentage_range|date_not_future",
      "severity": "warning|error",
      "reason": "short reason"
    }}
  ]
}}

Rules:
1. Infer constraints from semantics, not exact keywords alone.
2. Use only column names from the provided list.
3. Only propose high-confidence constraints.
4. If no good constraint exists, return an empty list.
5. If the instruction explicitly allows negative values (e.g. "leave unchanged", "allow negative", "refunds"), DO NOT output a non_negative constraint for amount/quantity fields.
"""
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You infer tabular validation constraints. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        constraints = parsed.get("constraints")
        if not isinstance(constraints, list):
            return []
        return _sanitize_constraints(
            constraints,
            source_columns,
            source="semantic_llm",
            allowed_rules={"non_negative", "percentage_range", "date_not_future"},
        )
    except Exception:
        return []


def _infer_constraints_with_heuristics(source_columns: list[str], instruction: str = "") -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    
    allow_negative = False
    if instruction:
        lowered = instruction.lower()
        if re.search(r'\b(?:unchanged|as\s+is|allow\s+negative|refunds?|keep\s+negative)\b', lowered):
            allow_negative = True

    for column in source_columns:
        normalized = _tokenize_name(column)
        if _matches_semantic_hint(normalized, "price_like") or _matches_semantic_hint(normalized, "quantity_like"):
            if not allow_negative:
                constraints.append(
                    {
                        "column": column,
                        "rule": "non_negative",
                        "severity": "warning",
                        "reason": "This field looks like a price, amount, or quantity and is usually non-negative.",
                        "source": "semantic_heuristic",
                    }
                )
        elif _matches_semantic_hint(normalized, "discount_like"):
            constraints.append(
                {
                    "column": column,
                    "rule": "percentage_range",
                    "severity": "warning",
                    "reason": "This field looks like a percentage-like discount and is usually between 0 and 100.",
                    "source": "semantic_heuristic",
                }
            )
        elif _matches_semantic_hint(normalized, "date_like"):
            constraints.append(
                {
                    "column": column,
                    "rule": "date_not_future",
                    "severity": "warning",
                    "reason": "This field looks like a business date and future values can be suspicious.",
                    "source": "semantic_heuristic",
                }
            )
    return _remove_shadowed_cross_field_constraints(constraints)


def _extract_prompt_constraints_with_llm(
    source_columns: list[str],
    preview_rows: list[dict[str, Any]],
    instruction: str,
) -> list[dict[str, Any]]:
    if not instruction.strip() or not source_columns:
        return []
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = f"""
Extract explicit validation rules from the user's instruction for this upload.

Instruction:
{instruction}

Columns:
{json.dumps(source_columns)}

Preview rows:
{json.dumps(preview_rows[:5], default=str)}

Return ONLY valid JSON with this shape:
{{
  "constraints": [
    {{
      "column": "column_name or *",
      "rule": "required|unique|numeric_range|date_range|not_allowed_values|contains|ends_with|cross_field_compare|starts_with|regex_match|allowed_values|length_range|non_negative|percentage_range|date_not_future|forbidden_substring|drop_column",
      "severity": "warning|error",
      "reason": "short reason",
      "value": "optional single value",
      "pattern": "optional regex",
      "allowed_values": ["optional", "values"],
      "not_allowed_values": ["optional", "blocked values"],
      "min_value": 0,
      "max_value": 100,
      "min_date": "YYYY-MM-DD",
      "max_date": "YYYY-MM-DD",
      "min_length": 1,
      "max_length": 20,
      "compare_column": "other_column_name",
      "operator": "<|<=|>|>=|==|!="
    }}
  ]
}}

Rules:
1. Extract only constraints explicitly stated or strongly implied by the instruction.
2. Use only column names from the provided list, except use "*" for instructions that apply to any field or whole rows.
3. If the instruction says values must start with a prefix like ACC, use starts_with and set value to that prefix.
4. If the instruction describes removing fields or rows containing a value, use forbidden_substring and set value to that text.
5. If the instruction explicitly asks to remove, drop, delete, omit, or exclude a specific column or field, use drop_column.
5. If the instruction describes a format, use regex_match when a clear regex can express it.
6. If the instruction says a column is mandatory, not blank, or must be present, use required.
7. If the instruction says no duplicates or values must be unique, use unique.
8. If the instruction gives numeric bounds, use numeric_range with min_value and/or max_value.
9. If the instruction gives date bounds, use date_range with min_date and/or max_date.
10. If the instruction bans specific values, use not_allowed_values.
11. If the instruction requires a substring, use contains; if it requires a suffix, use ends_with.
12. If the instruction compares two columns, use cross_field_compare with compare_column and operator.
13. If no explicit rule is present, return an empty list.
"""
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You extract prompt-defined data validation constraints. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        constraints = parsed.get("constraints")
        if not isinstance(constraints, list):
            return []
        return _sanitize_constraints(constraints, source_columns, source="prompt_llm")
    except Exception:
        return []


def _extract_prompt_constraints_with_heuristics(source_columns: list[str], instruction: str) -> list[dict[str, Any]]:
    if not instruction.strip():
        return []
    constraints: list[dict[str, Any]] = []
    lowered = instruction.lower()
    semantic_columns = _semantic_column_map(source_columns)
    constraints.extend(_extract_column_drop_constraints(source_columns, lowered))

    merchant_remove_match = re.search(
        r'remove\s+(?:the\s+)?(?:merchant|vendor|provider|payment method)\s+["\']?([^"\']+?)["\']?(?:\s|$|[,.])',
        lowered,
    )
    if merchant_remove_match:
        forbidden_value = _clean_forbidden_value(merchant_remove_match.group(1))
        if forbidden_value:
            target_column = semantic_columns.get("merchant", "*")
            constraints.append(
                {
                    "column": target_column,
                    "rule": "forbidden_substring",
                    "severity": "warning",
                    "reason": f'Prompt specifies removing merchant values containing "{forbidden_value}".',
                    "value": forbidden_value,
                    "source": "prompt_heuristic",
                }
            )

    merchant_only_match = re.search(
        r'(?:keep\s+only|only\s+(?:give\s+me\s+)?)\s+(?:merchant|vendor|provider|payment method)\s+["\']?([^"\']+?)["\']?(?:\s|$|[,.])',
        lowered,
    )
    if merchant_only_match:
        target_column = semantic_columns.get("merchant", "*")
        constraints.append(
            {
                "column": target_column,
                "rule": "contains",
                "severity": "warning",
                "reason": f'Prompt specifies keeping only merchant values containing "{merchant_only_match.group(1).strip()}".',
                "value": merchant_only_match.group(1).strip(),
                "source": "prompt_heuristic",
            }
        )

    txn_remove_match = re.search(
        r'remove\s+(?:transaction\s+id|txn\s+id|transaction|record|row)\s+["\']?([a-z0-9_-]+)["\']?(?:\s|$|[,.])',
        lowered,
    )
    if txn_remove_match and semantic_columns.get("transaction_id"):
        constraints.append(
            {
                "column": semantic_columns["transaction_id"],
                "rule": "forbidden_substring",
                "severity": "warning",
                "reason": f'Prompt specifies removing transaction id "{txn_remove_match.group(1).strip()}".',
                "value": txn_remove_match.group(1).strip(),
                "source": "prompt_heuristic",
            }
        )

    txn_only_match = re.search(
        r'(?:keep\s+only|only\s+(?:give\s+me\s+)?)\s+(?:transaction\s+id|txn\s+id|transaction|record|row)\s+["\']?([a-z0-9_-]+)["\']?(?:\s|$|[,.])',
        lowered,
    )
    if txn_only_match and semantic_columns.get("transaction_id"):
        constraints.append(
            {
                "column": semantic_columns["transaction_id"],
                "rule": "contains",
                "severity": "warning",
                "reason": f'Prompt specifies keeping only transaction id "{txn_only_match.group(1).strip()}".',
                "value": txn_only_match.group(1).strip(),
                "source": "prompt_heuristic",
            }
        )

    remove_contains_match = re.search(
        r'(?:remove|drop|wipe out|wipe|exclude)\s+(?:any\s+)?(?:row|rows|field|fields|value|values).*?contai?n(?:ing|s)?\s+["\']?([^"\']+?)["\']?(?:$|,|\.|\sand\s)',
        lowered,
    )
    if remove_contains_match:
        forbidden_value = _clean_forbidden_value(remove_contains_match.group(1))
        if forbidden_value:
            constraints.append(
                {
                    "column": "*",
                    "rule": "forbidden_substring",
                    "severity": "warning",
                    "reason": f'Prompt specifies removing values containing "{forbidden_value}".',
                    "value": forbidden_value,
                    "source": "prompt_heuristic",
                }
            )

    for column in source_columns:
        column_phrase = column.replace("_", " ").lower()
        if column_phrase not in lowered and column.lower() not in lowered:
            continue
        starts_with_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)?\s*(?:always\s+)?start\s+with\s+([A-Za-z0-9_-]+)",
            lowered,
        )
        if starts_with_match:
            constraints.append(
                {
                    "column": column,
                    "rule": "starts_with",
                    "severity": "error",
                    "reason": f"Prompt specifies that {column_phrase} must start with {starts_with_match.group(1).upper()}.",
                    "value": starts_with_match.group(1).upper(),
                    "source": "prompt_heuristic",
                }
            )
        ends_with_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)?\s*(?:always\s+)?end\s+with\s+([A-Za-z0-9_-]+)",
            lowered,
        )
        if ends_with_match:
            constraints.append(
                {
                    "column": column,
                    "rule": "ends_with",
                    "severity": "error",
                    "reason": f"Prompt specifies that {column_phrase} must end with {ends_with_match.group(1).upper()}.",
                    "value": ends_with_match.group(1).upper(),
                    "source": "prompt_heuristic",
                }
            )
        contains_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)?\s*(?:always\s+)?contain\s+([A-Za-z0-9_-]+)",
            lowered,
        )
        if contains_match:
            constraints.append(
                {
                    "column": column,
                    "rule": "contains",
                    "severity": "error",
                    "reason": f"Prompt specifies that {column_phrase} must contain {contains_match.group(1).upper()}.",
                    "value": contains_match.group(1).upper(),
                    "source": "prompt_heuristic",
                }
            )
        if re.search(rf"{re.escape(column_phrase)}(?:s)?\s+(?:(?:is|are)\s+)?(?:required|mandatory)", lowered) or re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)\s+(?:be\s+)?(?:present|filled|not\s+empty|not\s+blank)",
            lowered,
        ):
            constraints.append(
                {
                    "column": column,
                    "rule": "required",
                    "severity": "error",
                    "reason": f"Prompt specifies that {column_phrase} is required.",
                    "source": "prompt_heuristic",
                }
            )
        if re.search(rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)\s+be\s+unique", lowered) or re.search(
            rf"(?:no|without)\s+duplicate\s+{re.escape(column_phrase)}",
            lowered,
        ):
            constraints.append(
                {
                    "column": column,
                    "rule": "unique",
                    "severity": "error",
                    "reason": f"Prompt specifies that {column_phrase} must be unique.",
                    "source": "prompt_heuristic",
                }
            )
        numeric_between_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)?\s*(?:be\s+)?between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)",
            lowered,
        )
        if numeric_between_match:
            constraints.append(
                {
                    "column": column,
                    "rule": "numeric_range",
                    "severity": "error",
                    "reason": f"Prompt specifies numeric bounds for {column_phrase}.",
                    "min_value": float(numeric_between_match.group(1)),
                    "max_value": float(numeric_between_match.group(2)),
                    "source": "prompt_heuristic",
                }
            )
        numeric_max_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:(?:must|should)?\s*(?:not\s+)?exceed|(?:must|should|can)?\s*(?:not|never|cannot|can't)\s+be\s+(?:above|greater\s+than))\s+(-?\d+(?:\.\d+)?)",
            lowered,
        )
        if numeric_max_match:
            constraints.append(
                {
                    "column": column,
                    "rule": "numeric_range",
                    "severity": "error",
                    "reason": f"Prompt specifies a maximum value for {column_phrase}.",
                    "max_value": float(numeric_max_match.group(1)),
                    "source": "prompt_heuristic",
                }
            )
        numeric_min_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)?\s*(?:be\s+)?(?:at\s+least|above|greater\s+than)\s+(-?\d+(?:\.\d+)?)",
            lowered,
        )
        if numeric_min_match and not re.search(rf"{re.escape(column_phrase)}(?:s)?.*?(?:not|cannot|can't)", lowered):
            constraints.append(
                {
                    "column": column,
                    "rule": "numeric_range",
                    "severity": "error",
                    "reason": f"Prompt specifies a minimum value for {column_phrase}.",
                    "min_value": float(numeric_min_match.group(1)),
                    "source": "prompt_heuristic",
                }
            )
        not_allowed_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should|can)?\s*(?:not|never|cannot|can't)\s+be\s+([A-Za-z0-9_ -]+(?:\s*(?:,|or)\s*[A-Za-z0-9_ -]+)*)",
            lowered,
        )
        if not_allowed_match:
            raw_values = re.split(r"\s*(?:,|or)\s*", not_allowed_match.group(1))
            values = [value.strip().upper() for value in raw_values if value.strip()]
            if values:
                constraints.append(
                    {
                        "column": column,
                        "rule": "not_allowed_values",
                        "severity": "error",
                        "reason": f"Prompt specifies blocked values for {column_phrase}.",
                        "not_allowed_values": values,
                        "source": "prompt_heuristic",
                    }
                )
        allowed_values_match = re.search(
            rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)?\s*be\s+(?:only\s+)?([A-Za-z0-9_ -]+(?:\s*(?:,|or)\s*[A-Za-z0-9_ -]+)+)",
            lowered,
        )
        if allowed_values_match:
            raw_values = re.split(r"\s*(?:,|or)\s*", allowed_values_match.group(1))
            values = [value.strip().upper() for value in raw_values if value.strip()]
            if values:
                constraints.append(
                    {
                        "column": column,
                        "rule": "allowed_values",
                        "severity": "error",
                        "reason": f"Prompt specifies allowed values for {column_phrase}.",
                        "allowed_values": values,
                        "source": "prompt_heuristic",
                    }
                )
        for compare_column in source_columns:
            if compare_column == column:
                continue
            compare_phrase = compare_column.replace("_", " ").lower()
            if compare_phrase not in lowered and compare_column.lower() not in lowered:
                continue
            comparison_patterns = [
                (r"(?:not\s+)?(?:exceed|be\s+greater\s+than|be\s+above)", "<="),
                (r"(?:be\s+)?(?:less\s+than|below)", "<"),
                (r"(?:be\s+)?(?:greater\s+than|above)", ">"),
                (r"(?:equal|match)", "=="),
            ]
            for phrase, operator in comparison_patterns:
                if re.search(rf"{re.escape(column_phrase)}(?:s)?\s+(?:must|should)?\s*{phrase}\s+{re.escape(compare_phrase)}", lowered):
                    constraints.append(
                        {
                            "column": column,
                            "rule": "cross_field_compare",
                            "severity": "error",
                            "reason": f"Prompt compares {column_phrase} with {compare_phrase}.",
                            "compare_column": compare_column,
                            "operator": operator,
                            "source": "prompt_heuristic",
                        }
                    )
                    break
    return _remove_shadowed_cross_field_constraints(constraints)


def _sanitize_constraints(
    constraints: list[dict[str, Any]],
    source_columns: list[str],
    *,
    source: str,
    allowed_rules: set[str] | None = None,
) -> list[dict[str, Any]]:
    rules = allowed_rules or SUPPORTED_RULE_TYPES
    allowed_columns = set(source_columns) | {"*"}
    cleaned: list[dict[str, Any]] = []
    for item in constraints:
        if not isinstance(item, dict):
            continue
        column = str(item.get("column", "")).strip()
        rule = str(item.get("rule", "")).strip()
        if column not in allowed_columns or rule not in rules:
            continue
        normalized: dict[str, Any] = {
            "column": column,
            "rule": rule,
            "severity": str(item.get("severity", "warning")).strip() or "warning",
            "reason": str(item.get("reason", "Prompt-defined validation rule.")).strip(),
            "source": source,
        }
        if item.get("value") is not None:
            normalized["value"] = str(item.get("value")).strip()
        if item.get("pattern") is not None:
            normalized["pattern"] = str(item.get("pattern")).strip()
        if isinstance(item.get("allowed_values"), list):
            normalized["allowed_values"] = [str(value).strip() for value in item["allowed_values"] if str(value).strip()]
        if isinstance(item.get("not_allowed_values"), list):
            normalized["not_allowed_values"] = [
                str(value).strip() for value in item["not_allowed_values"] if str(value).strip()
            ]
        if item.get("compare_column") is not None:
            compare_column = str(item.get("compare_column")).strip()
            if compare_column in source_columns:
                normalized["compare_column"] = compare_column
        if item.get("operator") is not None:
            operator = str(item.get("operator")).strip()
            if operator in {"<", "<=", ">", ">=", "==", "!="}:
                normalized["operator"] = operator
        for raw_key, normalized_key in (
            ("min_value", "min_value"),
            ("max_value", "max_value"),
            ("min_date", "min_date"),
            ("max_date", "max_date"),
        ):
            if item.get(raw_key) is not None:
                normalized[normalized_key] = item.get(raw_key)
        min_length = item.get("min_length")
        max_length = item.get("max_length")
        if min_length is not None:
            try:
                normalized["min_length"] = int(min_length)
            except (TypeError, ValueError):
                pass
        if max_length is not None:
            try:
                normalized["max_length"] = int(max_length)
            except (TypeError, ValueError):
                pass
        cleaned.append(normalized)
    return cleaned


def _extract_column_drop_constraints(source_columns: list[str], instruction: str) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for column in source_columns:
        if _instruction_requests_column_drop(column, instruction):
            normalized_key = _tokenize_name(column)
            if normalized_key in seen:
                continue
            seen.add(normalized_key)
            constraints.append(
                {
                    "column": column,
                    "rule": "drop_column",
                    "severity": "warning",
                    "reason": f"Prompt specifies removing the {column} column.",
                    "source": "prompt_heuristic",
                }
            )
    return constraints


def _instruction_requests_column_drop(column: str, instruction: str) -> bool:
    if not column or not instruction:
        return False
    variants = sorted(_column_name_variants(column), key=len, reverse=True)
    for variant in variants:
        escaped = re.escape(variant)
        patterns = (
            rf"(?:remove|drop|delete|omit|exclude)\s+(?:the\s+)?{escaped}\s+(?:column|field)\b",
            rf"(?:remove|drop|delete|omit|exclude)\s+(?:the\s+)?(?:column|field)\s+(?:named\s+|called\s+)?{escaped}\b",
            rf"without\s+(?:the\s+)?{escaped}\s+(?:column|field)\b",
        )
        if any(re.search(pattern, instruction) for pattern in patterns):
            return True
    return False


def _column_name_variants(column: str) -> set[str]:
    raw = str(column or "").strip().lower()
    normalized = _tokenize_name(raw)
    variants = {raw, normalized, normalized.replace("_", " ")}
    return {variant for variant in variants if variant}


def _tokenize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _clean_forbidden_value(value: str) -> str:
    cleaned = value.strip().strip("\"'")
    cleaned = re.split(r"\s+(?:in|from|within|on)\s+(?:them|it|that|those|the\s+file|the\s+data)\b", cleaned, maxsplit=1)[0]
    cleaned = re.split(r"\s+(?:and|then|also)\s+", cleaned, maxsplit=1)[0]
    return cleaned.strip().strip("\"'")


def _matches_semantic_hint(normalized: str, hint_group: str) -> bool:
    tokens = {token for token in normalized.split("_") if token}
    for hint in SEMANTIC_HINTS[hint_group]:
        if normalized == hint:
            return True
        hint_tokens = {token for token in hint.split("_") if token}
        if hint_tokens and hint_tokens.issubset(tokens):
            return True
    return False


def _semantic_column_map(source_columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for column in source_columns:
        normalized = _tokenize_name(column)
        if "merchant" not in mapping and _matches_semantic_hint(normalized, "merchant_like"):
            mapping["merchant"] = column
        if "transaction_id" not in mapping and _matches_semantic_hint(normalized, "transaction_id_like"):
            mapping["transaction_id"] = column
        if "status" not in mapping and _matches_semantic_hint(normalized, "status_like"):
            mapping["status"] = column
    return mapping


def _remove_shadowed_cross_field_constraints(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cross_field_constraints = [
        item
        for item in constraints
        if item.get("rule") == "cross_field_compare" and item.get("compare_column") and item.get("operator")
    ]
    filtered: list[dict[str, Any]] = []
    for item in constraints:
        if item.get("rule") != "cross_field_compare":
            filtered.append(item)
            continue
        column = str(item.get("column", ""))
        column_phrase = column.replace("_", " ")
        is_shadowed = any(
            other is not item
            and str(other.get("column", "")).replace("_", " ").endswith(f" {column_phrase}")
            and other.get("compare_column") == item.get("compare_column")
            and other.get("operator") == item.get("operator")
            for other in cross_field_constraints
        )
        if not is_shadowed:
            filtered.append(item)
    return filtered
