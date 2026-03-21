"""Switch FTS config from 'simple' to 'russian' for stemming and stop words

Revision ID: 008
Revises: 007
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memory_fts")
    op.execute("ALTER TABLE agent_memory DROP COLUMN IF EXISTS search_vector")
    op.execute("""
        ALTER TABLE agent_memory ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('russian', coalesce(key, '') || ' ' || coalesce(content, ''))
        ) STORED
    """)
    op.execute(
        "CREATE INDEX idx_memory_fts ON agent_memory USING GIN (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memory_fts")
    op.execute("ALTER TABLE agent_memory DROP COLUMN IF EXISTS search_vector")
    op.execute("""
        ALTER TABLE agent_memory ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', coalesce(key, '') || ' ' || coalesce(content, ''))
        ) STORED
    """)
    op.execute(
        "CREATE INDEX idx_memory_fts ON agent_memory USING GIN (search_vector)"
    )
