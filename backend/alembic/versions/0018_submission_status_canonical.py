"""Canonical submission statuses

Revision ID: 0018_submission_status_canonical
Revises: 0017_fix_submission_columns
Create Date: 2026-06-18 16:30:00.000000
"""

from alembic import op


revision = "0018_submission_status_canonical"
down_revision = "0017_fix_submission_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE submissions ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN status TYPE TEXT
        USING status::text
        """
    )
    op.execute(
        """
        UPDATE submissions
        SET status = CASE
            WHEN status = 'pending' AND COALESCE(summary->>'status', '') IN ('pending_agent_availability', 'rejected') THEN 'quarantined'
            WHEN status = 'pending' THEN 'queued'
            WHEN status = 'processing' THEN 'running'
            WHEN status = 'complete' THEN 'succeeded'
            WHEN status = 'success' THEN 'succeeded'
            WHEN status = 'partial' THEN 'failed'
            WHEN status = 'rejected' THEN 'quarantined'
            WHEN status IN (
                'queued',
                'planning',
                'running',
                'succeeded',
                'failed',
                'quarantined',
                'callback_failed',
                'awaiting_schema_approval',
                'awaiting_confirmation',
                'declined'
            ) THEN status
            ELSE 'queued'
        END
        """
    )
    op.execute("ALTER TYPE submission_status RENAME TO submission_status_old")
    op.execute(
        """
        CREATE TYPE submission_status AS ENUM (
            'queued',
            'planning',
            'running',
            'succeeded',
            'failed',
            'quarantined',
            'callback_failed',
            'awaiting_schema_approval',
            'awaiting_confirmation',
            'declined'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN status TYPE submission_status
        USING status::submission_status
        """
    )
    op.execute("ALTER TABLE submissions ALTER COLUMN status SET DEFAULT 'queued'")
    op.execute("DROP TYPE submission_status_old")


def downgrade() -> None:
    op.execute("ALTER TABLE submissions ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN status TYPE TEXT
        USING status::text
        """
    )
    op.execute(
        """
        UPDATE submissions
        SET status = CASE
            WHEN status IN ('queued', 'planning', 'pending', 'awaiting_schema_approval', 'awaiting_confirmation') THEN 'pending'
            WHEN status = 'running' THEN 'processing'
            WHEN status = 'succeeded' THEN 'complete'
            WHEN status IN ('failed', 'callback_failed', 'declined') THEN 'failed'
            WHEN status = 'quarantined' THEN 'quarantined'
            WHEN status IN ('complete', 'processing') THEN status
            ELSE 'pending'
        END
        """
    )
    op.execute("ALTER TYPE submission_status RENAME TO submission_status_canonical")
    op.execute(
        """
        CREATE TYPE submission_status AS ENUM (
            'pending',
            'processing',
            'complete',
            'failed',
            'quarantined'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN status TYPE submission_status
        USING status::submission_status
        """
    )
    op.execute("ALTER TABLE submissions ALTER COLUMN status SET DEFAULT 'pending'")
    op.execute("DROP TYPE submission_status_canonical")
