"""add max_jobs_per_run and enable_outreach to user_settings

Revision ID: 3a7776335cef
Revises: 0008
Create Date: 2026-04-26 15:29:57.199354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7776335cef'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # user_settings
    op.execute('ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS max_jobs_per_run INTEGER DEFAULT 20')
    op.execute('ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS enable_outreach BOOLEAN DEFAULT TRUE')

    # job_results
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS experience VARCHAR')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS min_years_experience FLOAT')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS skills JSON')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS top_matching_skills JSON')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS salary VARCHAR')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS responsibilities TEXT')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS requirements TEXT')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS benefits TEXT')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS about_company TEXT')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS poster_type VARCHAR')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS outreach_email_draft TEXT')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS outreach_linkedin_draft TEXT')
    op.execute('ALTER TABLE job_results ADD COLUMN IF NOT EXISTS resume_id VARCHAR')

def downgrade():
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS resume_id')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS outreach_linkedin_draft')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS outreach_email_draft')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS poster_type')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS about_company')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS benefits')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS requirements')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS responsibilities')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS salary')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS top_matching_skills')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS skills')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS min_years_experience')
    op.execute('ALTER TABLE job_results DROP COLUMN IF EXISTS experience')
    op.execute('ALTER TABLE user_settings DROP COLUMN IF EXISTS enable_outreach')
    op.execute('ALTER TABLE user_settings DROP COLUMN IF EXISTS max_jobs_per_run')