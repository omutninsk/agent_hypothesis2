"""Add scheduled_tasks table

Revision ID: 007
Revises: 006
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE scheduled_tasks (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            description TEXT NOT NULL,
            interval_minutes INT,
            next_run_at TIMESTAMPTZ NOT NULL,
            last_run_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT true,
            run_count INT NOT NULL DEFAULT 0,
            last_result TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX idx_scheduled_tasks_user_id ON scheduled_tasks (user_id)"
    )
    op.execute(
        "CREATE INDEX idx_scheduled_tasks_active_next ON scheduled_tasks (is_active, next_run_at) WHERE is_active = true"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scheduled_tasks")
