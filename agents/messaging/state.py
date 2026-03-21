import operator
from typing import Annotated, TypedDict

from models.resume import MatchedJob
class MessagingState(TypedDict):
    user_id: str
    ranked_jobs: list[MatchedJob]

    jobs_with_drafts: list[MatchedJob]

    errors: Annotated[list[str], operator.add]
    status: str
