"""
Add resume_id column to job_results

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_results",
        sa.Column("resume_id", sa.String(), nullable=False, server_default="default"),
    )
    op.create_index("ix_job_results_resume_id", "job_results", ["resume_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_results_resume_id", table_name="job_results")
    op.drop_column("job_results", "resume_id")
