"""
Fix user_settings table schema - add missing columns and remove old ones

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    
    try:
        op.drop_column("user_settings", "is_scheduler_active")
    except Exception:
        pass 
    
    # Add missing columns
    op.add_column(
        "user_settings",
        sa.Column("job_experience", sa.String(), default="0", nullable=False)
    )
    op.add_column(
        "user_settings",
        sa.Column("browser_session", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    try:
        op.drop_column("user_settings", "browser_session")
    except Exception:
        pass
    try:
        op.drop_column("user_settings", "job_experience")
    except Exception:
        pass
    
    
    try:
        op.add_column(
            "user_settings",
            sa.Column("is_scheduler_active", sa.Boolean(), default=False, nullable=False)
        )
    except Exception:
        pass
