"""Add index for task history queries

Revision ID: 005
Revises: 004
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_tasks_user_chat_status_created",
        "tasks",
        ["user_id", "chat_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_user_chat_status_created")
