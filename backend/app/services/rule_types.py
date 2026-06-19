from __future__ import annotations

SUPPORTED_RULE_TYPES = {
    "allowed_values",
    "contains",
    "cross_field_compare",
    "date_range",
    "date_not_future",
    "drop_column",
    "ends_with",
    "forbidden_substring",
    "length_range",
    "non_negative",
    "not_allowed_values",
    "percentage_range",
    "numeric_range",
    "regex_match",
    "required",
    "starts_with",
    "unique",
}

SEMANTIC_HINTS = {
    "price_like": {
        "price",
        "amount",
        "cost",
        "rate",
        "value",
        "total",
        "subtotal",
        "unit_price",
        "debit_amount",
        "credit_amount",
    },
    "quantity_like": {"qty", "quantity", "units", "count", "pieces", "volume"},
    "discount_like": {"discount", "discount_pct", "discount_percent", "markdown"},
    "date_like": {"date", "voucher_date", "invoice_date", "posting_date", "txn_date"},
    "merchant_like": {"merchant", "merchant_name", "vendor", "provider", "payment_method", "payment_type", "gateway"},
    "transaction_id_like": {"transaction_id", "txn_id", "tx_id", "transactionid", "order_id", "invoice_id", "id"},
    "status_like": {"status", "transaction_status", "payment_status", "state"},
}
