"""Simplify FinFlow workflow statuses

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-10
"""

from alembic import op


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE reviews DROP CONSTRAINT IF EXISTS ck_reviews_comment_required")

    op.execute("ALTER TABLE submissions ALTER COLUMN review_status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN review_status TYPE TEXT
        USING review_status::text
        """
    )
    op.execute("UPDATE submissions SET review_status = 'complete' WHERE review_status = 'approved'")
    op.execute("UPDATE submissions SET review_status = 'failed' WHERE review_status IN ('declined', 'parse_failed', 'reupload_requested')")
    op.execute("ALTER TYPE review_status RENAME TO review_status_old")
    op.execute("CREATE TYPE review_status AS ENUM ('pending', 'processing', 'complete', 'failed')")
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN review_status TYPE review_status
        USING review_status::review_status
        """
    )
    op.execute("DROP TYPE review_status_old")
    op.execute("ALTER TABLE submissions ALTER COLUMN review_status SET DEFAULT 'pending'")

    op.execute(
        """
        ALTER TABLE reviews
        ALTER COLUMN action TYPE TEXT
        USING action::text
        """
    )
    op.execute("UPDATE reviews SET action = 'complete' WHERE action = 'approved'")
    op.execute("UPDATE reviews SET action = 'failed' WHERE action IN ('declined', 'reupload_requested')")
    op.execute("ALTER TYPE review_action RENAME TO review_action_old")
    op.execute("CREATE TYPE review_action AS ENUM ('complete', 'failed')")
    op.execute(
        """
        ALTER TABLE reviews
        ALTER COLUMN action TYPE review_action
        USING action::review_action
        """
    )
    op.execute("DROP TYPE review_action_old")

    op.execute(
        """
        ALTER TABLE reviews
        ADD CONSTRAINT ck_reviews_comment_required
        CHECK ((action = 'complete') OR (comment IS NOT NULL AND length(trim(comment)) > 0))
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE reviews DROP CONSTRAINT IF EXISTS ck_reviews_comment_required")

    op.execute("ALTER TABLE submissions ALTER COLUMN review_status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN review_status TYPE TEXT
        USING review_status::text
        """
    )
    op.execute("UPDATE submissions SET review_status = 'approved' WHERE review_status = 'complete'")
    op.execute("UPDATE submissions SET review_status = 'declined' WHERE review_status = 'failed'")
    op.execute("ALTER TYPE review_status RENAME TO review_status_old")
    op.execute("CREATE TYPE review_status AS ENUM ('pending', 'processing', 'approved', 'declined', 'parse_failed', 'reupload_requested')")
    op.execute(
        """
        ALTER TABLE submissions
        ALTER COLUMN review_status TYPE review_status
        USING review_status::review_status
        """
    )
    op.execute("DROP TYPE review_status_old")
    op.execute("ALTER TABLE submissions ALTER COLUMN review_status SET DEFAULT 'pending'")

    op.execute(
        """
        ALTER TABLE reviews
        ALTER COLUMN action TYPE TEXT
        USING action::text
        """
    )
    op.execute("UPDATE reviews SET action = 'approved' WHERE action = 'complete'")
    op.execute("UPDATE reviews SET action = 'declined' WHERE action = 'failed'")
    op.execute("ALTER TYPE review_action RENAME TO review_action_old")
    op.execute("CREATE TYPE review_action AS ENUM ('approved', 'declined', 'reupload_requested')")
    op.execute(
        """
        ALTER TABLE reviews
        ALTER COLUMN action TYPE review_action
        USING action::review_action
        """
    )
    op.execute("DROP TYPE review_action_old")

    op.execute(
        """
        ALTER TABLE reviews
        ADD CONSTRAINT ck_reviews_comment_required
        CHECK ((action = 'approved') OR (comment IS NOT NULL AND length(trim(comment)) > 0))
        """
    )
