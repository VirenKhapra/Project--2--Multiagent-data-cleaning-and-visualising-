"""add submission records

Revision ID: 0013_add_submission_records
Revises: 0012_add_agent_execution_fields
Create Date: 2026-06-10 03:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013_add_submission_records"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_index", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submission_records_submission_id", "submission_records", ["submission_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_submission_records_submission_id", table_name="submission_records")
    op.drop_table("submission_records")
