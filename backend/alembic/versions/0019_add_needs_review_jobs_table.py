"""add needs_review_jobs table

Revision ID: 0019_add_needs_review_jobs_table
Revises: 0018_submission_status_canonical
Create Date: 2026-06-18 17:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_add_needs_review_jobs_table"
down_revision = "0018_submission_status_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "needs_review_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("submission_id", sa.UUID(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_needs_review_jobs_submission_id"), "needs_review_jobs", ["submission_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_needs_review_jobs_submission_id"), table_name="needs_review_jobs")
    op.drop_table("needs_review_jobs")
