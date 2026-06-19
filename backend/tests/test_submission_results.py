from app.services.submission_results import extract_structured_records


def test_extract_structured_records_prefers_full_cleaned_data_over_preview():
    result_payload = {
        "record_count": 3,
        "cleaned_data": [
            {"customer_id": "1", "gender": "FEMALE"},
            {"customer_id": "2", "gender": "FEMALE"},
            {"customer_id": "3", "gender": "FEMALE"},
        ],
        "cleaned_preview": [
            {"customer_id": "1", "gender": "FEMALE"},
        ],
    }

    assert extract_structured_records(result_payload) == [
        {"customer_id": "1", "gender": "FEMALE"},
        {"customer_id": "2", "gender": "FEMALE"},
        {"customer_id": "3", "gender": "FEMALE"},
    ]


def test_extract_structured_records_rejects_truncated_preview_when_full_count_is_larger():
    result_payload = {
        "record_count": 4621,
        "cleaned_preview": [
            {"customer_id": "1", "gender": "FEMALE"},
            {"customer_id": "2", "gender": "FEMALE"},
        ],
    }

    assert extract_structured_records(result_payload) == []
