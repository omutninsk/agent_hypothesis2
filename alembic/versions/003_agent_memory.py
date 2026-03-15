"""Add agent_memory table

Revision ID: 003
Revises: 002
Create Date: 2026-03-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_memory",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_memory_key", "agent_memory", ["key"])
    op.create_index("idx_memory_user", "agent_memory", ["created_by"])
    op.create_unique_constraint("uq_memory_key_user", "agent_memory", ["key", "created_by"])


def downgrade() -> None:
    op.drop_table("agent_memory")
