from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.uploads import build_job_audit
from app.models import SubmissionStatus


@pytest.mark.parametrize(
    "status, summary, expected_action, expected_detail",
    [
        (
            SubmissionStatus.failed,
            {"status": "failed"},
            "workflow failed",
            "Agent execution failed.",
        ),
        (
            SubmissionStatus.quarantined,
            {"status": "quarantined"},
            "workflow quarantined",
            "Part of the workflow is quarantined pending review.",
        ),
    ],
)
def test_build_job_audit_uses_string_fallbacks_when_summary_error_missing(
    status,
    summary,
    expected_action,
    expected_detail,
):
    submission = SimpleNamespace(
        uploaded_at=datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc),
        dispatched_at=datetime(2026, 6, 18, 12, 5, tzinfo=timezone.utc),
        completed_at=datetime(2026, 6, 18, 12, 10, tzinfo=timezone.utc),
        status=status,
        summary=summary,
        file_name="input.csv",
        agent_task_id="task-123",
        output_path=None,
    )

    audit_entries = build_job_audit(submission, [])

    matching = [entry for entry in audit_entries if entry.action == expected_action]
    assert matching, f"Expected audit entry {expected_action!r} was not produced."
    assert matching[0].detail == expected_detail
    assert all(isinstance(entry.detail, str) for entry in audit_entries)
