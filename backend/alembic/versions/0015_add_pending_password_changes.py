"""add pending password changes

Revision ID: 0015_pwd_changes
Revises: 0014_add_workflow_alert_fields
Create Date: 2026-06-11 02:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015_pwd_changes"
down_revision = "0014_add_workflow_alert_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_password_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("new_password_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_pending_password_changes_user_id", "pending_password_changes", ["user_id"])
    op.create_index("idx_pending_password_changes_token_hash", "pending_password_changes", ["token_hash"])
    op.create_index("idx_pending_password_changes_expires_at", "pending_password_changes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_pending_password_changes_expires_at", table_name="pending_password_changes")
    op.drop_index("idx_pending_password_changes_token_hash", table_name="pending_password_changes")
    op.drop_index("idx_pending_password_changes_user_id", table_name="pending_password_changes")
    op.drop_table("pending_password_changes")
