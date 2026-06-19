from app.services.structured_output import sanitize_structured_row, sanitize_structured_rows


def test_sanitize_structured_row_removes_internal_metadata_keys():
    assert sanitize_structured_row(
        {
            "invoice_id": "INV-1001",
            "vendor": "ABC Supplies",
            "_source": "table_recovery",
            "_confidence": "high",
            "_issues": [],
            "_row_status": "complete",
        }
    ) == {
        "invoice_id": "INV-1001",
        "vendor": "ABC Supplies",
    }


def test_sanitize_structured_rows_drops_empty_or_non_dict_rows():
    assert sanitize_structured_rows(
        [
            {"invoice_id": "INV-1001", "_source": "table_recovery"},
            None,
            "bad",
            {"invoice_id": "INV-1002", "amount": "5000", "_row_status": "complete"},
        ]
    ) == [
        {"invoice_id": "INV-1001"},
        {"invoice_id": "INV-1002", "amount": "5000"},
    ]
