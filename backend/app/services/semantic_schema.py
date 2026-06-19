from __future__ import annotations

import re


ROLE_HINTS: dict[str, set[str]] = {
    "transaction_id": {"transaction_id", "txn_id", "tx_id", "transactionid", "order_id", "invoice_id", "id"},
    "merchant": {"merchant", "merchant_name", "vendor", "provider", "payment_method", "payment_type", "gateway"},
    "gender": {"gender", "sex"},
    "marital_status": {"marital_status", "maritalstatus", "relationship_status", "civil_status"},
    "education": {"education", "education_level", "degree", "qualification", "academic_qualification"},
    "quantity": {"quantity", "qty", "qty_ordered", "units", "pieces", "volume", "count"},
    "payment_value": {
        "payment",
        "payment_value",
        "amount",
        "amt",
        "price",
        "cost",
        "value",
        "total",
        "subtotal",
        "unit_price",
        "debit_amount",
        "credit_amount",
    },
    "status": {"status", "transaction_status", "payment_status", "state"},
    "date": {"date", "transaction_date", "txn_date", "invoice_date", "posting_date", "voucher_date"},
}


ROLE_TARGETS = {
    "transaction_id": "transaction_id",
    "merchant": "merchant",
    "gender": "gender",
    "marital_status": "marital_status",
    "education": "education_level",
    "quantity": "quantity",
    "payment_value": "payment_value",
    "status": "status",
    "date": "transaction_date",
}


def normalize_semantic_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def infer_column_roles(source_columns: list[str]) -> dict[str, list[str]]:
    roles: dict[str, list[str]] = {role: [] for role in ROLE_HINTS}
    for column in source_columns:
        normalized = normalize_semantic_name(column)
        tokens = {token for token in normalized.split("_") if token}
        for role, hints in ROLE_HINTS.items():
            if normalized in hints:
                roles[role].append(str(column))
                continue
            for hint in hints:
                hint_tokens = {token for token in hint.split("_") if token}
                if hint_tokens and hint_tokens.issubset(tokens):
                    roles[role].append(str(column))
                    break
    return {role: columns for role, columns in roles.items() if columns}


def canonical_target_for_column(column_name: str) -> str | None:
    normalized = normalize_semantic_name(column_name)
    tokens = {token for token in normalized.split("_") if token}
    for role, hints in ROLE_HINTS.items():
        if normalized in hints:
            return ROLE_TARGETS[role]
        for hint in hints:
            hint_tokens = {token for token in hint.split("_") if token}
            if hint_tokens and hint_tokens.issubset(tokens):
                return ROLE_TARGETS[role]
    return None
