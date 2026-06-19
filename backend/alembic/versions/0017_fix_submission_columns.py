"""fix submission columns

Revision ID: 0017_fix_submission_columns
Revises: 0016_preferred_agent
Create Date: 2026-06-18 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '0017_fix_submission_columns'
down_revision = '0016_preferred_agent'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col["name"] for col in inspector.get_columns("submissions")]

    # 1. Handle submission_status enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'submission_status') THEN
                CREATE TYPE submission_status AS ENUM ('pending', 'processing', 'complete', 'failed', 'quarantined');
            END IF;
        END;
        $$;
    """)

    # 2. Add columns if they are not already present
    if "status" not in columns:
        op.add_column("submissions", sa.Column("status", postgresql.ENUM("pending", "processing", "complete", "failed", "quarantined", name="submission_status", create_type=False), nullable=False, server_default="pending"))
    if "summary" not in columns:
        op.add_column("submissions", sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "output_path" not in columns:
        op.add_column("submissions", sa.Column("output_path", sa.String(length=500), nullable=True))
    if "dispatched_at" not in columns:
        op.add_column("submissions", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    if "completed_at" not in columns:
        op.add_column("submissions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col["name"] for col in inspector.get_columns("submissions")]

    if "completed_at" in columns:
        op.drop_column("submissions", "completed_at")
    if "dispatched_at" in columns:
        op.drop_column("submissions", "dispatched_at")
    if "output_path" in columns:
        op.drop_column("submissions", "output_path")
    if "summary" in columns:
        op.drop_column("submissions", "summary")
    if "status" in columns:
        op.drop_column("submissions", "status")

    # Optionally drop enum type
    op.execute("DROP TYPE IF EXISTS submission_status")
