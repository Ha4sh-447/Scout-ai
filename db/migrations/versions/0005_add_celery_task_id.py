"""
Add celery_task_id column to pipeline_runs

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add celery_task_id column to pipeline_runs table
    op.add_column(
        "pipeline_runs",
        sa.Column("celery_task_id", sa.String(), nullable=True)
    )


def downgrade() -> None:
    # Remove the column
    op.drop_column("pipeline_runs", "celery_task_id")
