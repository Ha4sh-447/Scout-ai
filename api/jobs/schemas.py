from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class JobResultResponse(BaseModel):
    id: str
    run_id: str
    user_id: str
    resume_id: str
    content_hash: str
    title: str
    company: str
    location: str
    source_url: str
    source_platform: str
    match_score: float
    final_score: float
    rank: int
    skills: List[str] = []
    top_matching_skills: List[str] = []
    salary: Optional[str] = None
    experience: Optional[str] = None
    min_years_experience: Optional[int] = None
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    about_company: Optional[str] = None
    poster_type: str
    outreach_email_draft: Optional[str] = None
    outreach_linkedin_draft: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PipelineRunResponse(BaseModel):
    id: str
    user_id: str
    triggered_by: str
    status: str
    execution_count: int = 1
    jobs_found: int
    jobs_matched: int
    jobs_ranked: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    notification_email: Optional[str] = None  # Receiver's mail ID
    total_jobs_ranked: Optional[int] = None  # Aggregate across all executions
    active_duration_minutes: Optional[int] = None  # Minutes since first execution
    is_scheduled: bool = False  # Whether this pipeline is scheduled for recurring runs
    interval_hours: int = 3  # Scheduling interval for this run
    emails_sent: bool = False  # Whether notification email was successfully sent

    class Config:
        from_attributes = True

class TriggerResponse(BaseModel):
    run_id: str
    message: str

class TriggerPipelineRequest(BaseModel):
    # Search parameters
    queries: List[str] = []  # Search queries for job discovery
    location: Optional[str] = None  # Job location filter
    experience: Optional[str] = None  # User experience level
    urls: List[str] = []  # Direct URLs to scrape
    # Scheduling parameters
    is_scheduled: bool = False  # Whether to schedule this pipeline for recurring runs
    interval_hours: int = 3  # Scheduler interval for this specific run (only if is_scheduled=True)

