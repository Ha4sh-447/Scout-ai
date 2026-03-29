from datetime import datetime
from sqlalchemy import func, DateTime, Boolean, String, Integer, JSON, Text, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    links: Mapped[list["Link"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    resumes: Mapped[list["UserResume"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class UserSettings(Base):
    __tablename__ = "user_settings"
 
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), unique=True, nullable=False)
 
    interval_hours: Mapped[int] = mapped_column(Integer, default=3)
 
    search_queries: Mapped[list] = mapped_column(JSON, default=list) # JSON, so that i can change it later if needed
    job_experience : Mapped[str] = mapped_column(String, default="0")
    location: Mapped[str] = mapped_column(String, default="India")
 
    resume_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
 
    notification_email: Mapped[str | None] = mapped_column(String, nullable=True)
    
    browser_session: Mapped[dict | None] = mapped_column(JSON, nullable=True)
 
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
 
    user: Mapped["User"] = relationship(back_populates="settings")
 
 
class Link(Base):
    __tablename__ = "links"
 
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String, default="generic")  # linkedin, indeed, reddit, generic
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
 
    user: Mapped["User"] = relationship(back_populates="links")


class UserResume(Base):
    __tablename__ = "user_resumes"
 
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)  # Original filename as uploaded
    file_path: Mapped[str] = mapped_column(String, nullable=False)  # Path in storage
    file_size: Mapped[int] = mapped_column(Integer, default=0)  # File size in bytes
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
 
    user: Mapped["User"] = relationship(back_populates="resumes")
 
 
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
 
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String, default="scheduler")  # "scheduler" | "manual"
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|running|done|failed|cancelled
    execution_count: Mapped[int] = mapped_column(Integer, default=1)  # Track how many times this pipeline run has executed
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    jobs_matched: Mapped[int] = mapped_column(Integer, default=0)
    jobs_ranked: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Per-pipeline scheduling
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether this run should be rescheduled
    interval_hours: Mapped[int] = mapped_column(Integer, default=3)  # Scheduling interval for this specific run
 
    user: Mapped["User"] = relationship(back_populates="pipeline_runs")
    job_results: Mapped[list["JobResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")
 
 
class JobResult(Base):
    __tablename__ = "job_results"
 
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
 
    # Job identity
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_platform: Mapped[str] = mapped_column(String, nullable=False)
 
    # Scores
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
 
    # Details stored as JSON
    skills: Mapped[list] = mapped_column(JSON, default=list)
    top_matching_skills: Mapped[list] = mapped_column(JSON, default=list)
    salary: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_type: Mapped[str] = mapped_column(String, default="unknown")
    outreach_email_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_linkedin_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
 
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
 
    run: Mapped["PipelineRun"] = relationship(back_populates="job_results")

