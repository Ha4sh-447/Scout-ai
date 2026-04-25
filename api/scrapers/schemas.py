from pydantic import BaseModel
from typing import List, Optional

class ScrapeRequest(BaseModel):
    links: List[str]
    is_scheduled: Optional[bool] = False  # Whether to schedule for repeated scraping
    interval_hours: Optional[int] = 3  # How many hours between scheduled scrapes

class ScrapeResponse(BaseModel):
    message: str
    run_id: str
    jobs_found: int = 0
    errors: List[str] = []


class SaveSearchLinksRequest(BaseModel):
    """Save search URLs permanently for automated scheduled runs"""
    links: List[str]  # URLs or search page links


class SaveSearchLinksResponse(BaseModel):
    message: str
    saved_count: int
    skipped_count: int
    skipped_platforms: List[str]


class SavedLinkResponse(BaseModel):
    id: str
    url: str
    platform: str
    created_at: str


class AuthenticateRequest(BaseModel):
    platforms: List[str] = ["linkedin", "wellfound", "indeed"]
