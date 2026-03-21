"""
initial tables

Revision ID: 0001
Revises:
Create Date: 2026-03-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_settings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("interval_hours", sa.Integer(), default=3),
        sa.Column("is_scheduler_active", sa.Boolean(), default=False),
        sa.Column("search_queries", sa.JSON(), default=list),
        sa.Column("location", sa.String(), default="India"),
        sa.Column("resume_summary", sa.Text(), nullable=True),
        sa.Column("notification_email", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(), default="generic"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_links_user_id", "links", ["user_id"])

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("triggered_by", sa.String(), default="scheduler"),
        sa.Column("status", sa.String(), default="pending"),
        sa.Column("jobs_found", sa.Integer(), default=0),
        sa.Column("jobs_matched", sa.Integer(), default=0),
        sa.Column("jobs_ranked", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pipeline_runs_user_id", "pipeline_runs", ["user_id"])

    op.create_table(
        "job_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_platform", sa.String(), nullable=False),
        sa.Column("match_score", sa.Float(), default=0.0),
        sa.Column("final_score", sa.Float(), default=0.0),
        sa.Column("rank", sa.Integer(), default=0),
        sa.Column("skills", sa.JSON(), default=list),
        sa.Column("top_matching_skills", sa.JSON(), default=list),
        sa.Column("salary", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("poster_type", sa.String(), default="unknown"),
        sa.Column("outreach_email_draft", sa.Text(), nullable=True),
        sa.Column("outreach_linkedin_draft", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_job_results_run_id", "job_results", ["run_id"])
    op.create_index("ix_job_results_user_id", "job_results", ["user_id"])


def downgrade() -> None:
    op.drop_table("job_results")
    op.drop_table("pipeline_runs")
    op.drop_table("links")
    op.drop_table("user_settings")
    op.drop_table("users")
