"""add preferred agent name to submissions

Revision ID: 0016_preferred_agent
Revises: 0015_pwd_changes
Create Date: 2026-06-11 03:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_preferred_agent"
down_revision = "0015_pwd_changes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("preferred_agent_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "preferred_agent_name")
