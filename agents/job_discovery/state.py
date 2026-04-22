from models.config import ResumeMatchingConfig
from models.config import QdrantConfig
import operator
from typing import Annotated, TypedDict

from models.config import ScraperConfig
from models.jobs import Job, RawJobData


class JobDiscoveryState(TypedDict):
    user_id: str
    urls: list[str]
    search_queries: list[str]  
    location: str | None = None  
    experience_level: str | None = None 
    platforms: list[str]
    scraper_config: ScraperConfig
    browser_session: dict | None = None

    qdrant_cfg: QdrantConfig
    matching_cfg: ResumeMatchingConfig

    _scraped_raw_jobs: list[RawJobData]

    raw_jobs: Annotated[list[RawJobData], operator.add]
    _raw_jobs_parsed_count: int

    parsed_jobs: Annotated[list[Job], operator.add]

    unique_jobs: Annotated[list[Job], operator.add]

    errors: Annotated[list[str], operator.add]
    status: str

    freshness: str
    retry_count: int