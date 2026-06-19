from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.api.uploads import get_schema_proposal_with_fallback
from app.services.action_schema import build_action_schema
from app.services.rule_engine import build_validation_warnings
from app.services.rule_extractor import extract_prompt_constraints
from app.services.schema_proposal import build_schema_proposal_from_file


def test_forbidden_substring_flags_normalized_variants():
    frame = pd.DataFrame({"payment_method": ["Card", "PayPal", "pay pal"]})

    warnings = build_validation_warnings(
        frame,
        [{"column": "*", "rule": "forbidden_substring", "value": "PayPal", "severity": "warning"}],
    )

    assert warnings == [
        {
            "column": "payment_method",
            "rule": "forbidden_substring",
            "severity": "warning",
            "reason": "",
            "invalid_count": 2,
            "sample_values": ["PayPal", "pay pal"],
        }
    ]


def test_starts_with_flags_invalid_account_prefix():
    frame = pd.DataFrame({"account_number": ["ACC100", "ZCC200"]})

    warnings = build_validation_warnings(
        frame,
        [{"column": "account_number", "rule": "starts_with", "value": "ACC", "severity": "error"}],
    )

    assert warnings[0]["column"] == "account_number"
    assert warnings[0]["rule"] == "starts_with"
    assert warnings[0]["invalid_count"] == 1
    assert warnings[0]["sample_values"] == ["ZCC200"]


def test_date_not_future_handles_naive_dates_without_crashing():
    future_year = pd.Timestamp.now().year + 3
    frame = pd.DataFrame({"invoice_date": ["2024-01-01", f"{future_year}-01-01"]})

    warnings = build_validation_warnings(
        frame,
        [{"column": "invoice_date", "rule": "date_not_future", "severity": "warning"}],
    )

    assert warnings[0]["column"] == "invoice_date"
    assert warnings[0]["rule"] == "date_not_future"
    assert warnings[0]["invalid_count"] == 1


def test_prompt_fallback_extracts_remove_contains_typo(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    constraints = extract_prompt_constraints(
        ["payment_method"],
        [{"payment_method": "PayPal"}],
        'Clean the data and remove any field contaning "PayPal"',
    )

    assert constraints == [
        {
            "column": "*",
            "rule": "forbidden_substring",
            "severity": "warning",
            "reason": 'Prompt specifies removing values containing "paypal".',
            "value": "paypal",
            "source": "prompt_heuristic",
        }
    ]


def test_prompt_fallback_trims_trailing_contains_phrase(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    constraints = extract_prompt_constraints(
        ["payment_method", "quantity"],
        [{"payment_method": "PayPal", "quantity": -5}],
        "Remove any field which contains paypal in them and also remove things which should not have negative value like quantity",
    )

    forbidden = [constraint for constraint in constraints if constraint["rule"] == "forbidden_substring"]
    assert forbidden[0]["value"] == "paypal"


def test_schema_proposal_integrates_prompt_rule(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    csv_path = Path(__file__).with_name(".tmp_payments.csv")
    try:
        csv_path.write_text("payment_method,amount\nCard,10\nPayPal,20\npay pal,30\n", encoding="utf-8")

        result = build_schema_proposal_from_file(
            csv_path,
            max_preview_rows=10,
            instruction='Clean the data and remove any field containing "PayPal"',
        )
    finally:
        csv_path.unlink(missing_ok=True)

    assert result is not None
    proposal, preview_rows = result
    assert len(preview_rows) == 3
    assert proposal["prompt_constraints"][0]["rule"] == "forbidden_substring"
    assert proposal["validation_warnings"][0]["column"] == "payment_method"
    assert proposal["validation_warnings"][0]["invalid_count"] == 2


def test_schema_proposal_fallback_rebuilds_missing_payload(monkeypatch):
    csv_path = Path(__file__).with_name(".tmp_schema_fallback.csv")
    try:
        csv_path.write_text("date,vendor,invoice_id\n2026-06-14,ABC,#INV-1\n", encoding="utf-8")
        submission = SimpleNamespace(
            summary={"schema_proposal": {}},
            file_path=str(csv_path),
            instruction="Clean the data and do not extract cash or payment column only",
        )

        proposal = get_schema_proposal_with_fallback(submission)
    finally:
        csv_path.unlink(missing_ok=True)

    assert proposal["status"] == "awaiting_schema_approval"
    assert proposal["schema_kind"] == "tabular"
    assert proposal["source_columns"] == ["voucher_date", "vendor", "invoice_id"]


def test_rule_engine_supports_high_priority_rule_primitives():
    frame = pd.DataFrame(
        {
            "invoice_id": ["INV-1", "INV-1", ""],
            "amount": [10, 150, 20],
            "invoice_date": ["2024-01-01", "2035-01-01", "bad-date"],
            "status": ["paid", "cancelled", "open"],
            "sku": ["PROD-IN", "TEST-US", "PROD-US"],
            "paid_amount": [10, 200, 5],
            "invoice_amount": [10, 150, 20],
        }
    )

    warnings = build_validation_warnings(
        frame,
        [
            {"column": "invoice_id", "rule": "required", "severity": "error"},
            {"column": "invoice_id", "rule": "unique", "severity": "error"},
            {"column": "amount", "rule": "numeric_range", "min_value": 0, "max_value": 100, "severity": "error"},
            {
                "column": "invoice_date",
                "rule": "date_range",
                "min_date": "2024-01-01",
                "max_date": "2026-12-31",
                "severity": "error",
            },
            {"column": "status", "rule": "not_allowed_values", "not_allowed_values": ["cancelled"], "severity": "error"},
            {"column": "sku", "rule": "contains", "value": "PROD", "severity": "error"},
            {"column": "sku", "rule": "ends_with", "value": "US", "severity": "error"},
            {
                "column": "paid_amount",
                "rule": "cross_field_compare",
                "compare_column": "invoice_amount",
                "operator": "<=",
                "severity": "error",
            },
        ],
    )

    warnings_by_rule = {warning["rule"]: warning for warning in warnings}
    assert warnings_by_rule["required"]["sample_values"] == [""]
    assert warnings_by_rule["unique"]["sample_values"] == ["INV-1"]
    assert warnings_by_rule["numeric_range"]["sample_values"] == [150]
    assert warnings_by_rule["date_range"]["invalid_count"] == 2
    assert warnings_by_rule["not_allowed_values"]["sample_values"] == ["cancelled"]
    assert warnings_by_rule["contains"]["sample_values"] == ["TEST-US"]
    assert warnings_by_rule["ends_with"]["sample_values"] == ["PROD-IN"]
    assert warnings_by_rule["cross_field_compare"]["sample_values"] == [
        {"paid_amount": 200, "invoice_amount": 150}
    ]


def test_prompt_fallback_extracts_common_rule_primitives(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    constraints = extract_prompt_constraints(
        ["invoice_id", "amount", "sku", "status", "paid_amount", "invoice_amount"],
        [],
        (
            "invoice id is required and invoice id must be unique. "
            "amount must be between 0 and 100. "
            "sku must contain PROD and sku must end with US. "
            "status cannot be cancelled. "
            "paid amount must not exceed invoice amount."
        ),
    )

    extracted = {(constraint["column"], constraint["rule"]) for constraint in constraints}
    assert ("invoice_id", "required") in extracted
    assert ("invoice_id", "unique") in extracted
    assert ("amount", "numeric_range") in extracted
    assert ("sku", "contains") in extracted
    assert ("sku", "ends_with") in extracted
    assert ("status", "not_allowed_values") in extracted
    assert ("paid_amount", "cross_field_compare") in extracted
    assert ("amount", "cross_field_compare") not in extracted


def test_prompt_fallback_uses_semantic_merchant_column(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    constraints = extract_prompt_constraints(
        ["merchant_name", "txn_id"],
        [],
        'Remove merchant "Stripe"',
    )

    assert ("merchant_name", "forbidden_substring") in {
        (constraint["column"], constraint["rule"]) for constraint in constraints
    }


def test_prompt_fallback_uses_semantic_transaction_id_column(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    constraints = extract_prompt_constraints(
        ["merchant_name", "txn_id"],
        [],
        "Remove transaction id T0012",
    )

    assert ("txn_id", "forbidden_substring") in {
        (constraint["column"], constraint["rule"]) for constraint in constraints
    }


def test_prompt_fallback_extracts_generic_drop_column_rule(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    constraints = extract_prompt_constraints(
        ["customer_id", "merchant_name"],
        [],
        "Clean this data and remove the customer_id column",
    )

    assert {
        "column": "customer_id",
        "rule": "drop_column",
        "severity": "warning",
        "reason": "Prompt specifies removing the customer_id column.",
        "source": "prompt_heuristic",
    } in constraints


def test_action_schema_understands_filter_paraphrase(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    plan = build_action_schema(
        ["payment_method", "amount"],
        [{"payment_method": "PayPal", "amount": 10}],
        "wipe out rows which contains paypal as a payement method",
    )

    assert plan["actions"] == [
        {
            "action": "drop_rows_where",
            "condition_tree": {
                "logic": "or",
                "conditions": [
                    {
                        "role": "merchant",
                        "op": "contains",
                        "value": "paypal",
                    }
                ],
            },
        }
    ]


def test_schema_proposal_includes_action_schema(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    csv_path = Path(__file__).with_name(".tmp_payments_actions.csv")
    try:
        csv_path.write_text("payment_method,amount\nPayPal,10\nCard,20\n", encoding="utf-8")

        result = build_schema_proposal_from_file(
            csv_path,
            max_preview_rows=10,
            instruction="wipe out rows which contains paypal as a payement method",
        )
    finally:
        csv_path.unlink(missing_ok=True)

    assert result is not None
    proposal, _preview_rows = result
    assert proposal["action_schema"]["source"] == "deferred_to_agent_parser"
    assert proposal["prompt_constraints"][0]["rule"] == "forbidden_substring"
