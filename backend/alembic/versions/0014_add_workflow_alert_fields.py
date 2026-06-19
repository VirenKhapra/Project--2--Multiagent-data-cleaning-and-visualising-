"""add workflow alert fields

Revision ID: 0014_add_workflow_alert_fields
Revises: 0013_add_submission_records
Create Date: 2026-06-11 01:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014_add_workflow_alert_fields"
down_revision = "0013_add_submission_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("alert_type", sa.String(length=50), nullable=False, server_default="transaction_validation"))
    op.add_column("alerts", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("alerts", sa.Column("message", sa.Text(), nullable=True))
    op.add_column("alerts", sa.Column("upload_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_alerts_upload_id_submissions", "alerts", "submissions", ["upload_id"], ["id"], ondelete="SET NULL")
    op.create_index("idx_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("idx_alerts_upload_id", "alerts", ["upload_id"])


def downgrade() -> None:
    op.drop_index("idx_alerts_upload_id", table_name="alerts")
    op.drop_index("idx_alerts_alert_type", table_name="alerts")
    op.drop_constraint("fk_alerts_upload_id_submissions", "alerts", type_="foreignkey")
    op.drop_column("alerts", "upload_id")
    op.drop_column("alerts", "message")
    op.drop_column("alerts", "title")
    op.drop_column("alerts", "alert_type")
