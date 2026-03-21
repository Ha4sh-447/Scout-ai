import operator
from typing import Annotated, TypedDict

from models.config import QdrantConfig, ResumeMatchingConfig
from models.jobs import Job
from models.resume import MatchedJob


class ResumeMatchingState(TypedDict):
    user_id: str
    resume_id: str | None = None
    unique_jobs: list[Job]
    qdrant_cfg: QdrantConfig
    matching_cfg: ResumeMatchingConfig

    matched_jobs: list[MatchedJob]

    errors: Annotated[list[str], operator.add]
    status: str
