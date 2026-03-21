from models.config import ResumeMatchingConfig
from models.config import QdrantConfig
import operator
from typing import Annotated, TypedDict

from models.config import ScraperConfig
from models.jobs import Job, RawJobData


class JobDiscoveryState(TypedDict):
    user_id: str
    urls: list[str]  # user-uploaded links
    search_queries: list[str]  
    location: str | None = None  
    experience_level: str | None = None 
    platforms: list[str]
    scraper_config: ScraperConfig
    browser_session: dict | None = None

    # Resume matching config 
    qdrant_cfg: QdrantConfig
    matching_cfg: ResumeMatchingConfig

    raw_jobs: Annotated[list[RawJobData], operator.add]

    parsed_jobs: list[Job]

    unique_jobs: Annotated[list[Job], operator.add]

    errors: Annotated[list[str], operator.add]
    status: str

    freshness: str
    retry_count: int
