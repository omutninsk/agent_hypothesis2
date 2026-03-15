"""Add proto_schema, input_schema, output_schema to skills

Revision ID: 002
Revises: 001
Create Date: 2026-03-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("proto_schema", sa.Text, nullable=True))
    op.add_column("skills", sa.Column("input_schema", JSONB, nullable=True))
    op.add_column("skills", sa.Column("output_schema", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("skills", "output_schema")
    op.drop_column("skills", "input_schema")
    op.drop_column("skills", "proto_schema")
