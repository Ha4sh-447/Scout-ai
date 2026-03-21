import operator
from typing import Annotated
from models.config import RankingConfig
from typing import TypedDict

from models.resume import MatchedJob
class RankingState(TypedDict):
    user_id: str
    matched_jobs: list[MatchedJob]
    ranking_cfg: RankingConfig

    ranked_jobs: list[MatchedJob]

    errors: Annotated[list[str], operator.add]
    status: str
