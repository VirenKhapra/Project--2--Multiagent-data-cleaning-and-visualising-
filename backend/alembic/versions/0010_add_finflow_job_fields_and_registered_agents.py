"""Add FinFlow job fields and registered agents

Revision ID: 0010
Revises: 0009, 1859bbd362b3
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010"
down_revision = ("0009", "1859bbd362b3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("instruction", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "submissions",
        sa.Column("output_format", sa.String(length=32), nullable=False, server_default=sa.text("'XLSX'")),
    )

    op.create_table(
        "registered_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("capability_tags", postgresql.ARRAY(sa.String(length=64)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("input_formats", postgresql.ARRAY(sa.String(length=32)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_formats", postgresql.ARRAY(sa.String(length=32)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("endpoint_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_invocations", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_registered_agents_name"),
    )


def downgrade() -> None:
    op.drop_table("registered_agents")
    op.drop_column("submissions", "output_format")
    op.drop_column("submissions", "instruction")
