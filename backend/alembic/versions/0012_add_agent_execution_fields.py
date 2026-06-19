"""Add agent execution fields to submissions

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("agent_task_id", sa.String(length=255), nullable=True))
    op.add_column("submissions", sa.Column("agent_status", sa.String(length=40), nullable=True))
    op.add_column("submissions", sa.Column("output_file_path", sa.String(length=500), nullable=True))
    op.add_column("submissions", sa.Column("agent_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("submissions", sa.Column("agent_error", sa.Text(), nullable=True))
    op.add_column("submissions", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submissions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "completed_at")
    op.drop_column("submissions", "dispatched_at")
    op.drop_column("submissions", "agent_error")
    op.drop_column("submissions", "agent_result")
    op.drop_column("submissions", "output_file_path")
    op.drop_column("submissions", "agent_status")
    op.drop_column("submissions", "agent_task_id")
