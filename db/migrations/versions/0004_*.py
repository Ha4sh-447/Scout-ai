"""
Add per-pipeline scheduling fields to pipeline_runs

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_scheduled and interval_hours columns to pipeline_runs
    op.add_column("pipeline_runs", sa.Column("is_scheduled", sa.Boolean(), default=False, nullable=False))
    op.add_column("pipeline_runs", sa.Column("interval_hours", sa.Integer(), default=3, nullable=False))


def downgrade() -> None:
    # Remove the columns
    op.drop_column("pipeline_runs", "interval_hours")
    op.drop_column("pipeline_runs", "is_scheduled")
