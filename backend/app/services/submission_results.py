from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission, SubmissionRecord
from app.services.structured_output import sanitize_structured_rows


def extract_structured_records(result_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(result_payload, dict):
        return []

    cleaned_data = result_payload.get("cleaned_data")
    if isinstance(cleaned_data, list) and cleaned_data and all(isinstance(item, dict) for item in cleaned_data):
        return sanitize_structured_rows(cleaned_data)

    cleaned_preview = result_payload.get("cleaned_preview")
    if isinstance(cleaned_preview, list) and cleaned_preview and all(isinstance(item, dict) for item in cleaned_preview):
        try:
            expected_count = int(result_payload.get("record_count") or 0)
        except (TypeError, ValueError):
            expected_count = 0
        if expected_count and expected_count > len(cleaned_preview):
            return []
        return sanitize_structured_rows(cleaned_preview)

    for key in ("records", "rows", "data"):
        value = result_payload.get(key)
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            return sanitize_structured_rows(value)
    return []


async def persist_submission_results(
    db: AsyncSession,
    submission: Submission,
    result_payload: dict[str, Any] | None,
) -> dict[str, int]:
    records = extract_structured_records(result_payload)

    await db.execute(delete(SubmissionRecord).where(SubmissionRecord.submission_id == submission.id))

    if not records:
        return {"structured_records": 0}

    db.add_all([
        SubmissionRecord(
            submission_id=submission.id,
            record_index=index,
            payload=record,
        )
        for index, record in enumerate(records, start=1)
    ])

    return {"structured_records": len(records)}
