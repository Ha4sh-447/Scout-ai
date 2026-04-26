"""
Add execution_count to PipelineRun

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add execution_count column to pipeline_runs table
    op.add_column(
        "pipeline_runs",
        sa.Column("execution_count", sa.Integer(), default=1, nullable=False),
    )


def downgrade() -> None:
    # Remove execution_count column from pipeline_runs table
    op.drop_column("pipeline_runs", "execution_count")
