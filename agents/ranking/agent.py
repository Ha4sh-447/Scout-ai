from models.resume import MatchedJob
from datetime import datetime, timezone
from agents.ranking.state import RankingState
import logging

from models.config import RankingConfig


logger = logging.getLogger(__name__)

_SOURCE_QUALITY: dict[str, float] = {
        "linkedin": 1.00,
        "indeed": 1.00,
        "glassdoor": 1.00,
        "reddit": 0.85,
        "generic": 0.65
        }

async def ranking_node(state: RankingState) -> dict:

    jobs = state.get("matched_jobs", [])
    cfg = state.get("ranking_cfg") or RankingConfig()

    logger.info(f"[ranking_node] Ranking {len(jobs)} jobs for user {state['user_id']}")

    if not jobs:
        return {"ranked_jobs": [], "status": "ranking_done"}

    now = datetime.now(timezone.utc)

    for job in jobs:
        match_s = job.match_score

        recency_s = _compute_recency(job, now, cfg.recency_decay_days)
        job.recency_score = round(recency_s, 4)

        source_s = _SOURCE_QUALITY.get(job.source_platform.lower(), 0.65)
        job.source_quality_score = round(source_s, 4)

        raw_score = (
                (match_s * cfg.match_weight)
                + (recency_s * cfg.recency_weight)
                + (source_s * cfg.source_quality_weight)
                )

        if job.poster_type == "agency_recruiter":
            raw_score *= (1.0 - cfg.agency_recruiter_weight)

        job.final_score = round(min(max(raw_score, 0.0), 1.0),4)

    # Sort jobs in decending order
    jobs.sort(key = lambda j: j.final_score, reverse=True)
    for i, job in enumerate(jobs, start=1):
        job.rank = i

    logger.info(f"[ranking_node] Ranking done")

    return {"ranked_jobs": jobs, "status": "ranking_done"}

def _compute_recency(job: MatchedJob, now: datetime, decay_days: int) -> float:
    """
    Linear decay: 1.0 if scraped today, 0.0 if scraped >= decay_days ago.
    Returns 0.5 if scraped_at is unavailable (conservative default).
    """
    if not job.matched_at:
        return 0.5
 
    matched_at = job.matched_at
    if matched_at.tzinfo is None:
        matched_at = matched_at.replace(tzinfo=timezone.utc)
 
    age_days = (now - matched_at).total_seconds() / 86400
    score    = 1.0 - (age_days / decay_days)
    return max(score, 0.0)

