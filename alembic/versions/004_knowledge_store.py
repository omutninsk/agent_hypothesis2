"""Add knowledge store table

Revision ID: 004
Revises: 003
Create Date: 2026-03-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("topic", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source", sa.String(256), nullable=True),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_knowledge_user", "knowledge", ["created_by"])
    op.create_index("idx_knowledge_topic", "knowledge", ["topic"])

    # tsvector GENERATED STORED — auto-updated by PostgreSQL
    op.execute("""
        ALTER TABLE knowledge ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', coalesce(topic, '') || ' ' || coalesce(content, ''))
        ) STORED
    """)
    op.execute(
        "CREATE INDEX idx_knowledge_fts ON knowledge USING GIN (search_vector)"
    )


def downgrade() -> None:
    op.drop_table("knowledge")
