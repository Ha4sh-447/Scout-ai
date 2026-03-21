from pydantic import BaseModel
from typing import List

class ScrapeRequest(BaseModel):
    links: List[str]

class ScrapeResponse(BaseModel):
    message: str
    run_id: str
    jobs_found: int = 0
    errors: List[str] = []
