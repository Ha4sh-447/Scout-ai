from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class JobResultResponse(BaseModel):
    id: str
    run_id: str
    user_id: str
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
    description: Optional[str] = None
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
    jobs_found: int
    jobs_matched: int
    jobs_ranked: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TriggerResponse(BaseModel):
    run_id: str
    message: str
