from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PosterType(str, Enum):
    direct_hire = "direct_hire"
    agency_recruiter = "agency_recruiter"
    unknown = "unknown"


class JobType(str, Enum):
    remote = "remote"
    on_site = "on_site"
    hybrid = "hybrid"
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    unknown = "unknown"


class RecruiterInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    profile_url: str | None = None


class Job(BaseModel):
    # id: str | None
    title: str
    company: str
    location: str
    salary: str | None = None
    experience: str | None = None
    min_years_experience: int | None = None
    skills: list[str] = []
    source_url: str
    description: str 
    about_company: str | None = None

    source_platform: str
    scraped_at: datetime | None = None

    job_type: list[JobType] = [JobType.unknown]

    poster_type: PosterType = PosterType.unknown
    recruiter: RecruiterInfo | None = None
    content_hash: Optional[str] = None
    posted_at_text: str | None = None

    def model_post_init(self, __context):
        if self.scraped_at is None:
            self.scraped_at = datetime.utcnow()


class RawJobData(BaseModel):
    source_url: str
    source_platform: str
    raw_text: str
    raw_html: str | None = None
    scraped_at: datetime | None = None
    posted_at_text: str | None = None

    salary: str | None = None
    recruiter_name: str | None = None
    recruiter_link: str | None = None

    def model_post_init(self, __context):
        if self.scraped_at is None:
            self.scraped_at = datetime.utcnow()
