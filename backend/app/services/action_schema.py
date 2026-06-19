from __future__ import annotations

import difflib
import json
import os
import re
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.services.semantic_schema import infer_column_roles, normalize_semantic_name


class FilterCondition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    op: Literal["eq", "neq", "gt", "lt", "gte", "lte", "contains"]
    value: Any


class ConditionTree(BaseModel):
    model_config = ConfigDict(extra="ignore")

    logic: Literal["and", "or"]
    conditions: list[Union["FilterCondition", "ConditionTree"]]


ConditionTree.model_rebuild()


class KeepRowsWhereAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["keep_rows_where"]
    condition_tree: ConditionTree


class DropRowsWhereAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["drop_rows_where"]
    condition_tree: ConditionTree


class DropColumnsAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["drop_columns"]
    roles: list[str]


class KeepColumnsAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["keep_columns"]
    roles: list[str]


class RenameColumnsAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["rename_columns"]
    mapping: dict[str, str]


class ExtractFromUnstructuredAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["extract_from_unstructured"]
    target_roles: list[str]


class ExportFormatAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["export_format"]
    format: str


ActionType = Union[
    KeepRowsWhereAction,
    DropRowsWhereAction,
    DropColumnsAction,
    KeepColumnsAction,
    RenameColumnsAction,
    ExtractFromUnstructuredAction,
    ExportFormatAction,
]


class ActionSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    actions: list[ActionType]
    required_capabilities: list[str] = Field(default_factory=list)
    optional_hints: dict[str, Any] = Field(default_factory=dict)


ROLE_ALIAS_MAP: dict[str, set[str]] = {
    "merchant": {"merchant", "vendor", "provider", "payment method", "payment_method", "payement method", "gateway"},
    "status": {"status", "state", "payment status", "payment_status", "loan status", "loan_status"},
    "gender": {"gender", "sex"},
    "marital_status": {"marital status", "marital_status", "relationship status", "relationship_status"},
    "education": {"education", "education level", "education_level", "degree", "qualification"},
    "transaction_id": {"transaction id", "transaction_id", "txn id", "txn_id", "invoice id", "invoice_id", "id"},
    "payment_value": {"amount", "payment", "payment value", "payment_value", "price", "cost", "value"},
    "quantity": {"quantity", "qty", "units", "count"},
    "date": {"date", "transaction date", "invoice date", "application date"},
}
ROLE_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical_role
    for canonical_role, aliases in ROLE_ALIAS_MAP.items()
    for alias in aliases
}
SORTED_ROLE_ALIASES: list[str] = sorted(ROLE_ALIAS_TO_CANONICAL, key=len, reverse=True)
FILTER_INTENT_PREFIX = re.compile(
    r"^\s*(?:clean(?:\s+this\s+data)?\s+and\s+)?"
    r"(?:only allow|keep only|only keep|show only|only show|only return|filter|"
    r"extract\s+rows?|return\s+rows?|pull(?:\s+out)?\s+rows?|remove|drop|exclude|"
    r"do not allow|don't allow|dont allow)\s*",
    re.IGNORECASE,
)
CLAUSE_PREFIX_NOISE = re.compile(
    r"^\s*(?:rows?|records?|data|which|that|contains?|containing|with|where|only|just|"
    r"allow|keep|show|return|extract|have|has|are|is)\s+",
    re.IGNORECASE,
)
ROLE_VALUE_OPERATORS = (" is ", " equals ", " equal to ", " = ", ": ")


def build_action_schema(
    source_columns: list[str],
    preview_rows: list[dict[str, Any]],
    instruction: str,
) -> dict[str, Any]:
    if not instruction.strip() or not source_columns:
        return {"actions": [], "required_capabilities": [], "source": "empty"}

    llm_schema = _parse_action_schema_with_llm(source_columns, preview_rows, instruction)
    if llm_schema.get("actions"):
        return llm_schema
    return _parse_action_schema_with_heuristics(source_columns, instruction)


def action_schema_to_constraints(action_schema: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(action_schema, dict):
        return []

    constraints: list[dict[str, Any]] = []
    for action in action_schema.get("actions", []):
        if not isinstance(action, dict):
            continue

        action_type = str(action.get("action", "")).strip()
        if action_type == "drop_columns":
            for role in action.get("roles", []):
                role_name = str(role or "").strip()
                if not role_name:
                    continue
                constraints.append(
                    {
                        "column": role_name,
                        "rule": "drop_column",
                        "severity": "warning",
                        "reason": f"Instruction removes the {role_name} field.",
                        "source": "action_schema",
                    }
                )
            continue

        if action_type in {"keep_rows_where", "drop_rows_where"}:
            rule = "allowed_values" if action_type == "keep_rows_where" else "not_allowed_values"
            for leaf in _iter_leaf_conditions(action.get("condition_tree")):
                role_name = str(leaf.get("role", "")).strip()
                op = str(leaf.get("op", "")).strip().lower()
                value = str(leaf.get("value", "")).strip()
                if not role_name or not value:
                    continue
                if op == "contains":
                    constraints.append(
                        {
                            "column": role_name,
                            "rule": "contains" if action_type == "keep_rows_where" else "forbidden_substring",
                            "severity": "warning",
                            "reason": f"Instruction filters on {role_name}.",
                            "value": value,
                            "source": "action_schema",
                        }
                    )
                elif op in {"eq", "equals"}:
                    constraints.append(
                        {
                            "column": role_name,
                            "rule": rule,
                            "severity": "warning",
                            "reason": f"Instruction filters on {role_name}.",
                            "allowed_values": [value] if rule == "allowed_values" else [],
                            "not_allowed_values": [value] if rule == "not_allowed_values" else [],
                            "source": "action_schema",
                        }
                    )
    return constraints


def _parse_action_schema_with_llm(
    source_columns: list[str],
    preview_rows: list[dict[str, Any]],
    instruction: str,
) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return {"actions": [], "required_capabilities": [], "source": "llm_unavailable"}

    normalized_columns = {column: normalize_semantic_name(column) for column in source_columns}
    role_columns = infer_column_roles(source_columns)
    prompt = f"""
Interpret the user's tabular data-cleaning instruction and return ONLY valid JSON matching the ActionSchema below.

Instruction:
{instruction}

Source columns:
{json.dumps(source_columns)}

Normalized column names:
{json.dumps(normalized_columns)}

Inferred semantic roles:
{json.dumps(role_columns)}

Preview rows:
{json.dumps(preview_rows[:5], default=str)}

Output schema:
{{
  "actions": [
    {{
      "action": "keep_rows_where|drop_rows_where|drop_columns|keep_columns|rename_columns",
      "condition_tree": {{
        "logic": "and|or",
        "conditions": [
          {{"role": "gender", "op": "eq|contains", "value": "female"}}
        ]
      }},
      "roles": ["semantic_role_or_column_name"],
      "mapping": {{"source_role_or_column": "new_name"}}
    }}
  ],
  "required_capabilities": ["row_filter|column_drop|column_keep|column_rename"]
}}

Rules:
1. For row filtering, always use condition_tree.
2. Combined conditions like "female and single" must become one keep_rows_where action with condition_tree.logic = "and".
3. Use the most specific semantic role when possible, otherwise use the best matching normalized column name.
4. Negative phrasing like "do not extract cash", "remove payment column", "exclude customer id" must map to drop_columns.
5. "Only keep status and amount" or "Extract columns A and B" must map to keep_columns.
6. "Rename payment value to amount paid" must map to rename_columns.
7. Tagged clauses like "paypal as merchant and pending as status" must become one keep_rows_where action with two conditions and logic "and".
8. For tagged clauses, preserve the user value literally and assign it to the tagged role instead of guessing from the value.
9. If no clear transformation is requested, return an empty actions array.

Examples:
- "only allow paypal as merchant and pending as status"
  -> {{
       "actions": [
         {{
           "action": "keep_rows_where",
           "condition_tree": {{
             "logic": "and",
             "conditions": [
               {{"role": "merchant", "op": "eq", "value": "paypal"}},
               {{"role": "status", "op": "eq", "value": "pending"}}
             ]
           }}
         }}
       ],
       "required_capabilities": ["row_filter"]
     }}
"""
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You convert tabular cleaning instructions into strict ActionSchema JSON. Output only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        return _sanitize_action_schema(parsed, source_columns, source="llm")
    except Exception:
        return {"actions": [], "required_capabilities": [], "source": "llm_error"}


def _parse_action_schema_with_heuristics(source_columns: list[str], instruction: str) -> dict[str, Any]:
    normalized_instruction = " ".join(str(instruction or "").split()).lower()
    actions: list[dict[str, Any]] = []
    required_capabilities: set[str] = set()

    drop_roles: list[str] = []
    for column in source_columns:
        if _instruction_requests_column_drop(column, normalized_instruction):
            drop_roles.append(normalize_semantic_name(column))
    if drop_roles:
        actions.append({"action": "drop_columns", "roles": list(dict.fromkeys(drop_roles))})
        required_capabilities.add("column_drop")

    keep_match = re.search(r"(?:keep only|show only|only give me|only return|extract(?:\s+only)?)\s+(.+)", normalized_instruction)
    if keep_match and re.search(r"\b(?:column|columns|field|fields)\b", normalized_instruction) and not re.search(r"\bcontain(?:s|ing)?\b", normalized_instruction):
        requested = _extract_named_targets(keep_match.group(1), source_columns)
        if requested:
            actions.append({"action": "keep_columns", "roles": requested})
            required_capabilities.add("column_keep")

    tagged_clause_filter = _parse_tagged_clause_filter(normalized_instruction)
    if tagged_clause_filter:
        actions.append(tagged_clause_filter)
        required_capabilities.add("row_filter")

    role_columns = infer_column_roles(source_columns)
    row_filter = _parse_simple_row_filter(normalized_instruction, role_columns)
    if row_filter and not tagged_clause_filter:
        actions.append(row_filter)
        required_capabilities.add("row_filter")

    return _sanitize_action_schema(
        {
            "actions": actions,
            "required_capabilities": sorted(required_capabilities),
        },
        source_columns,
        source="heuristic",
    )


def _sanitize_action_schema(payload: dict[str, Any], source_columns: list[str], *, source: str) -> dict[str, Any]:
    aliases = _build_column_aliases(source_columns)
    actions: list[dict[str, Any]] = []
    for item in payload.get("actions", []):
        if not isinstance(item, dict):
            continue

        action_type = str(item.get("action", "")).strip()
        if action_type in {"drop_columns", "keep_columns"}:
            roles = [_resolve_role_or_column(role, aliases) for role in item.get("roles", [])]
            roles = [role for role in roles if role]
            if roles:
                actions.append({"action": action_type, "roles": list(dict.fromkeys(roles))})
            continue

        if action_type == "rename_columns":
            raw_mapping = item.get("mapping", {})
            if not isinstance(raw_mapping, dict):
                continue
            mapping: dict[str, str] = {}
            for source_name, target_name in raw_mapping.items():
                resolved_source = _resolve_role_or_column(source_name, aliases)
                normalized_target = str(target_name or "").strip()
                if resolved_source and normalized_target:
                    mapping[resolved_source] = normalized_target
            if mapping:
                actions.append({"action": action_type, "mapping": mapping})
            continue

        if action_type in {"keep_rows_where", "drop_rows_where"}:
            condition_tree = _sanitize_condition_tree(item.get("condition_tree"), aliases)
            if condition_tree:
                actions.append({"action": action_type, "condition_tree": condition_tree})

    try:
        schema = ActionSchema.model_validate(
            {
                "actions": actions,
                "required_capabilities": payload.get("required_capabilities", []),
                "optional_hints": payload.get("optional_hints", {}),
            }
        )
        sanitized = schema.model_dump(mode="json")
        sanitized["source"] = source
        return sanitized
    except Exception:
        return {"actions": [], "required_capabilities": [], "source": f"{source}_invalid"}


def _sanitize_condition_tree(raw_tree: Any, aliases: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(raw_tree, dict):
        return None

    logic = str(raw_tree.get("logic", "and")).strip().lower()
    if logic not in {"and", "or"}:
        logic = "and"

    sanitized_conditions: list[dict[str, Any]] = []
    for item in raw_tree.get("conditions", []):
        if not isinstance(item, dict):
            continue
        if "logic" in item:
            nested = _sanitize_condition_tree(item, aliases)
            if nested:
                sanitized_conditions.append(nested)
            continue

        role_name = _resolve_role_or_column(item.get("role"), aliases)
        op = str(item.get("op", "")).strip().lower()
        value = item.get("value")
        if not role_name or op not in {"eq", "neq", "gt", "lt", "gte", "lte", "contains"} or value in {None, ""}:
            continue
        sanitized_conditions.append({"role": role_name, "op": op, "value": value})

    if not sanitized_conditions:
        return None
    return {"logic": logic, "conditions": sanitized_conditions}


def _resolve_role_or_column(raw_name: Any, aliases: dict[str, str]) -> str | None:
    value = str(raw_name or "").strip()
    if not value:
        return None
    normalized = normalize_semantic_name(value)
    return aliases.get(value) or aliases.get(normalized) or normalized


def _build_column_aliases(source_columns: list[str]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for column in source_columns:
        normalized = normalize_semantic_name(column)
        aliases[str(column).strip()] = normalized
        aliases[str(column).strip().lower()] = normalized
        aliases[normalized] = normalized
        aliases[normalized.replace("_", " ")] = normalized
    return aliases


def _instruction_requests_column_drop(column: str, instruction: str) -> bool:
    normalized_column = normalize_semantic_name(column)
    variants = {
        str(column or "").strip().lower(),
        normalized_column,
        normalized_column.replace("_", " "),
    }
    verb_group = r"(?:remove|drop|delete|omit|exclude|get rid of|strip away|wipe out|i don't need|dont need|do not need|without|do not extract)"
    for variant in sorted(variants, key=len, reverse=True):
        escaped = re.escape(variant)
        patterns = (
            rf"{verb_group}\s+(?:the\s+)?{escaped}\s+(?:column|field)?\b",
            rf"{verb_group}\s+(?:the\s+)?(?:column|field)\s+(?:named\s+|called\s+)?{escaped}\b",
        )
        if any(re.search(pattern, instruction) for pattern in patterns):
            return True
    return False


def _extract_named_targets(fragment: str, source_columns: list[str]) -> list[str]:
    aliases = _build_column_aliases(source_columns)
    targets: list[str] = []
    for piece in re.split(r",|\band\b", fragment):
        resolved = _resolve_role_or_column(piece.strip().strip("\"'"), aliases)
        if resolved:
            targets.append(resolved)
    return list(dict.fromkeys(targets))


def _preferred_filter_role(role_columns: dict[str, list[str]], value: str = "") -> str | None:
    normalized_value = normalize_semantic_name(value)
    if normalized_value in {"single", "married", "widowed", "divorced", "separated", "engaged", "complicated"}:
        for role in ("marital_status", "status", "merchant", "transaction_id"):
            if role_columns.get(role):
                return role
    if normalized_value in {"phd", "doctorate", "master", "masters", "bachelor", "associate", "diploma", "mba"}:
        for role in ("education", "status", "merchant", "transaction_id"):
            if role_columns.get(role):
                return role
    if normalized_value in {"female", "male", "woman", "man"} and role_columns.get("gender"):
        return "gender"
    for role in ("merchant", "transaction_id", "status", "gender", "marital_status", "education"):
        if role_columns.get(role):
            return role
    return None


def _normalize_clause_role(raw_role: str) -> str | None:
    normalized = normalize_semantic_name(raw_role).replace("_", " ")
    for canonical_role, aliases in ROLE_ALIAS_MAP.items():
        if normalized in aliases:
            return canonical_role
    alias_to_role: dict[str, str] = {}
    for canonical_role, aliases in ROLE_ALIAS_MAP.items():
        for alias in aliases:
            alias_to_role[alias] = canonical_role
    fuzzy_match = difflib.get_close_matches(normalized, list(alias_to_role.keys()), n=1, cutoff=0.8)
    if fuzzy_match:
        return alias_to_role[fuzzy_match[0]]
    return None


def _strip_clause_noise(text: str) -> str:
    cleaned = str(text or "").strip().strip(",")
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = CLAUSE_PREFIX_NOISE.sub("", cleaned).strip().strip(",")
    return cleaned


def _normalize_filter_value(raw_value: str) -> str:
    cleaned = str(raw_value or "").strip().strip(",").strip("\"'")
    cleaned = re.sub(r"^(?:is|equals|equal to)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _split_filter_clauses(text: str) -> tuple[list[str], list[str]]:
    clauses: list[str] = []
    connectors: list[str] = []
    buffer: list[str] = []
    tokens = re.split(r"(\s+(?:and|or)\s+)", text)
    for token in tokens:
        if not token:
            continue
        connector_match = re.fullmatch(r"\s+(and|or)\s+", token, flags=re.IGNORECASE)
        if connector_match:
            clause = _strip_clause_noise("".join(buffer))
            if clause:
                clauses.append(clause)
                connectors.append(connector_match.group(1).lower())
            buffer = []
            continue
        buffer.append(token)
    trailing = _strip_clause_noise("".join(buffer))
    if trailing:
        clauses.append(trailing)
    if len(connectors) >= len(clauses):
        connectors = connectors[: max(len(clauses) - 1, 0)]
    return clauses, connectors


def _parse_role_first_clause(clause: str) -> dict[str, Any] | None:
    lowered = clause.lower().strip()
    for alias in SORTED_ROLE_ALIASES:
        alias_with_space = f"{alias} "
        if not lowered.startswith(alias_with_space) and lowered != alias:
            continue
        remainder = clause[len(alias):].strip()
        operator = next((item for item in ROLE_VALUE_OPERATORS if remainder.lower().startswith(item.strip())), None)
        if operator:
            value = _normalize_filter_value(remainder[len(operator.strip()):])
        else:
            stripped = re.sub(r"^(?:is|equals|equal to|=|:)\s*", "", remainder, flags=re.IGNORECASE).strip()
            value = _normalize_filter_value(stripped)
        if not value:
            return None
        return {
            "role": ROLE_ALIAS_TO_CANONICAL[alias],
            "op": "eq",
            "value": value,
        }
    return None


def _parse_value_first_clause(clause: str) -> dict[str, Any] | None:
    normalized_clause = _strip_clause_noise(clause)
    for alias in SORTED_ROLE_ALIASES:
        pattern = rf"^(?P<value>.+?)\s+as\s+(?:a\s+)?{re.escape(alias)}$"
        match = re.match(pattern, normalized_clause, flags=re.IGNORECASE)
        if not match:
            continue
        value = _normalize_filter_value(match.group("value"))
        if not value:
            return None
        return {
            "role": ROLE_ALIAS_TO_CANONICAL[alias],
            "op": "eq",
            "value": value,
        }
    return None


def _parse_filter_clause(clause: str) -> dict[str, Any] | None:
    normalized_clause = _strip_clause_noise(clause)
    if not normalized_clause:
        return None
    return _parse_role_first_clause(normalized_clause) or _parse_value_first_clause(normalized_clause)


def _parse_tagged_clause_filter(instruction: str) -> dict[str, Any] | None:
    action_type = ""
    if re.search(
        r"\b(?:only allow|keep only|only keep|show only|only show|only return|filter|extract\s+rows?|return\s+rows?|pull(?:\s+out)?\s+rows?)\b",
        instruction,
    ):
        action_type = "keep_rows_where"
    elif re.search(r"\b(?:remove|drop|exclude|do not allow|don't allow|dont allow)\b", instruction):
        action_type = "drop_rows_where"
    if not action_type:
        return None

    filter_segment = FILTER_INTENT_PREFIX.sub("", instruction, count=1).strip()
    clauses, connectors = _split_filter_clauses(filter_segment)
    if not clauses:
        return None

    conditions: list[dict[str, Any]] = []
    for clause in clauses:
        parsed_clause = _parse_filter_clause(clause)
        if parsed_clause:
            conditions.append(parsed_clause)

    if not conditions:
        return None
    logic = "or" if connectors and all(connector == "or" for connector in connectors) else "and"
    return {
        "action": action_type,
        "condition_tree": {
            "logic": logic,
            "conditions": conditions,
        },
    }


def _parse_simple_row_filter(instruction: str, role_columns: dict[str, list[str]]) -> dict[str, Any] | None:
    keep_match = re.search(
        r"(?:keep only|show only|only give me|filter|only show|only return)\s+(?:rows?|records?|data|field|fields)?\s*(?:where|which contains|that contains)?\s*(.+)",
        instruction,
    )
    drop_match = re.search(
        r"(?:remove|drop|exclude|wipe out|get rid of)\s+(?:rows?|records?|data|transactions?)\s*(?:which contains?|that contains?|where|with)?\s*(.+)",
        instruction,
    )
    action_type = "keep_rows_where" if keep_match else "drop_rows_where" if drop_match else ""
    match = keep_match or drop_match
    if not match or not action_type:
        return None

    fragment = match.group(1).strip().strip(".")
    contains_match = re.search(
        r"\bcontain(?:s|ing)?\b\s+[\"']?([^\"']+?)[\"']?(?:\s+as\s+(?:a\s+)?field)?$",
        fragment,
    )
    if contains_match:
        values = [contains_match.group(1).strip()]
        operator = "contains"
    else:
        operator = "contains" if (re.search(r"\bcontain(?:s|ing)?\b", fragment) or re.search(r"\bcontain(?:s|ing)?\b", instruction)) else "eq"
        values = [part.strip().strip("\"'") for part in re.split(r"\band\b", fragment) if part.strip()]
    conditions: list[dict[str, Any]] = []
    for value in values:
        value = re.sub(r"^(?:field|fields|contains?|with)\s+", "", value).strip()
        value = re.sub(r"\s+as\s+(?:a\s+)?field$", "", value).strip()
        for alias in SORTED_ROLE_ALIASES:
            value = re.sub(rf"\s+as\s+(?:a\s+)?{re.escape(alias)}$", "", value, flags=re.IGNORECASE).strip()
        role_name = _preferred_filter_role(role_columns, value)
        if role_name:
            conditions.append({"role": role_name, "op": operator, "value": value})
    if not conditions:
        return None

    return {
        "action": action_type,
        "condition_tree": {
            "logic": "and" if len(conditions) > 1 else "or",
            "conditions": conditions,
        },
    }


def _iter_leaf_conditions(condition_tree: Any) -> list[dict[str, Any]]:
    if not isinstance(condition_tree, dict):
        return []
    leaves: list[dict[str, Any]] = []
    for item in condition_tree.get("conditions", []):
        if not isinstance(item, dict):
            continue
        if "logic" in item:
            leaves.extend(_iter_leaf_conditions(item))
        else:
            leaves.append(item)
    return leaves
