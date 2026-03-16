"""Add FTS to agent_memory table

Revision ID: 006
Revises: 005
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE agent_memory ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', coalesce(key, '') || ' ' || coalesce(content, ''))
        ) STORED
    """)
    op.execute(
        "CREATE INDEX idx_memory_fts ON agent_memory USING GIN (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memory_fts")
    op.execute("ALTER TABLE agent_memory DROP COLUMN IF EXISTS search_vector")
