from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from models.jobs import RecruiterInfo


class ResumeChunk(BaseModel):
    user_id: str
    resume_id: str = "default"
    chunk_id: str
    text: str
    section: str
    chunk_index: int
    embeddings: Optional[list[float]] = None


class Resume(BaseModel):
    user_id: str
    resume_id: str = "default"
    raw_text: str
    chunks: list[ResumeChunk] = []
    uploaded_at: Optional[datetime] = None

    def model_post_init(self, __context):
        if self.uploaded_at is None:
            self.uploaded_at = datetime.utcnow()


class MatchedJob(BaseModel):
    content_hash: str
    resume_id: str = "default"
    resume_summary: Optional[str] = None
    location: str
    company: str
    title: str
    salary: Optional[str] = None
    skills: list[str] = []
    experience: Optional[str] = None
    min_years_experience: Optional[int] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    about_company: Optional[str] = None
    job_type: list[str] = []
    recruiter: Optional[dict] = None
    description: str
    source_url: str
    source_platform: str
    poster_type: str
    match_score: float
    top_matching_skills: list[str] = []
    matched_at: Optional[datetime] = None
    chunk_score: float = 0.0
    full_resume_score: float = 0.0

    recency_score: float = 0.0
    source_quality_score: float = 0.0
    final_score: float = 0.0
    rank: int = 0

    outreach_email_draft: Optional[str] = None
    outreach_linkedin_draft: Optional[str] = None

    posted_at_text: Optional[str] = None
    matched_at: Optional[datetime] = None

    def model_post_init(self, __context) -> None:
        if self.matched_at is None:
            self.matched_at = datetime.utcnow()
