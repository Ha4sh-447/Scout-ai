import asyncio
import logging

from agents.resume_matching.state import ResumeMatchingState
from core.embeddings import embed_text
from core.qdrant_mcp import (
    get_qdrant_client,
    qdrant_find,
)
from models.config import QdrantConfig, ResumeMatchingConfig
from models.jobs import Job
from models.resume import MatchedJob

logger = logging.getLogger(__name__)

_SECTION_WEIGHTS = {
    "experience":     1.5,
    "skills":         1.2,
    "education":      1.0,
    "projects":       1.3,
    "achievements":   1.15,
    "certifications": 1.15,
    "summary":        0.75,
    "other":          1.0,
}

async def resume_matching_node(state: ResumeMatchingState) -> dict:
    jobs         = state.get("unique_jobs", [])
    user_id      = state["user_id"]
    resume_id    = state.get("resume_id")
    qdrant_cfg   = state.get("qdrant_cfg")   or QdrantConfig()
    matching_cfg = state.get("matching_cfg") or ResumeMatchingConfig()

    logger.info(f"[resume_matching_node] Matching {len(jobs)} jobs for user {user_id} (resume_id: {resume_id})")

    if not jobs:
        return {"matched_jobs": [], "status": "matching_done"}

    try:
        matched = await _match_all(jobs, user_id, qdrant_cfg, matching_cfg, resume_id=resume_id)
    except Exception as e:
        logger.error(f"[resume_matching_node] Fatal error: {e}")
        return {"matched_jobs": [], "errors": [str(e)], "status": "matching_failed"}

    logger.info(
        f"[resume_matching_node] {len(matched)}/{len(jobs)} jobs passed "
        f"min_score={matching_cfg.min_match_score} for user {user_id}"
    )
    return {"matched_jobs": matched, "status": "matching_done"}

async def _match_all(
    jobs: list[Job],
    user_id: str,
    qdrant_cfg: QdrantConfig,
    matching_cfg: ResumeMatchingConfig,
    resume_id: str | None = None,
) -> list[MatchedJob]:

    logger.info(f"[stage_1] Chunk filtering {len(jobs)} jobs (resume: {resume_id})")
    stage1_results = await _stage1_chunk_filter(jobs, user_id, qdrant_cfg, matching_cfg, resume_id=resume_id)
    logger.info(f"[stage_1] {len(stage1_results)} jobs passed min_score filter")

    if not stage1_results:
        return []

    # Cap at rerank_top_n to avoid spending embed calls on borderline matches
    candidates = stage1_results[: matching_cfg.rerank_top_n]
    rest       = stage1_results[matching_cfg.rerank_top_n :]

    logger.info(f"[stage_2] Reranking top {len(candidates)} jobs against full resume")
    reranked = await _stage2_rerank(candidates, user_id, qdrant_cfg, matching_cfg)

    final = reranked + rest
    final.sort(key=lambda j: j.match_score, reverse=True)
    return final


async def _stage1_chunk_filter(
    jobs: list[Job],
    user_id: str,
    qdrant_cfg: QdrantConfig,
    matching_cfg: ResumeMatchingConfig,
    resume_id: str | None = None,
) -> list[MatchedJob]:
    """
    Query resume_chunks for each job concurrently.
    Returns MatchedJob list (with chunk_score as match_score), sorted desc.
    Drops jobs below min_match_score.
    """
    survivors: list[MatchedJob] = []
    semaphore = asyncio.Semaphore(10)

    async with get_qdrant_client(qdrant_cfg) as client:

        async def filter_one(job: Job) -> None:
            async with semaphore:
                try:
                    result = await _chunk_score_job(job, user_id, client, qdrant_cfg, matching_cfg, resume_id=resume_id)
                    if result:
                        survivors.append(result)
                except Exception as e:
                    logger.warning(f"[stage_1] Failed for {job.source_url}: {e}")

        await asyncio.gather(*[filter_one(j) for j in jobs])

    survivors.sort(key=lambda j: j.match_score, reverse=True)
    return survivors


async def _chunk_score_job(
    job: Job,
    user_id: str,
    client,
    qdrant_cfg: QdrantConfig,
    cfg: ResumeMatchingConfig,
    resume_id: str | None = None,
) -> MatchedJob | None:
    """Score one job via chunk similarity. Returns None if below threshold."""
    query = f"{job.title}\n{job.description}\nSkills: {', '.join(job.skills)}"
    
    # embedding
    query_embedding = await embed_text(query)

    chunks = await qdrant_find(
        client=client,
        collection_name=qdrant_cfg.collection_name,
        query_embedding=query_embedding,
        user_id=user_id,
        resume_id=resume_id,
        top_k=cfg.top_k_chunks,
    )

    if not chunks:
        return None

    chunk_score, winning_resume_id = _aggregate_chunk_scores(chunks)
    logger.info(f"[stage_1] Job: {job.title} @ {job.company} -> Base Chunk Score: {chunk_score:.4f} (Resume: {winning_resume_id})")

    if chunk_score < cfg.min_match_score:
        return None

    # Skill overlap
    matched_text = " ".join(
        c.get("information", c.get("text", "")) for c in chunks
    ).lower()
    top_skills = [s for s in job.skills if s.lower() in matched_text]

    # Apply skill matching penalty
    final_score = _apply_skill_adjustment(chunk_score, job.skills, top_skills)

    if final_score < cfg.min_match_score:
        return None

    return MatchedJob(
        content_hash=job.content_hash or "",
        resume_id=winning_resume_id,
        source_url=job.source_url,
        title=job.title,
        company=job.company,
        location=job.location,
        salary=job.salary,
        skills=job.skills,
        description=job.description,
        source_platform=job.source_platform,
        poster_type=job.poster_type.value,
        match_score=round(final_score, 4),   # will be updated in Stage 2
        top_matching_skills=top_skills,
        recruiter=job.recruiter.model_dump() if job.recruiter else None,
    )


async def _stage2_rerank(
    candidates: list[MatchedJob],
    user_id: str,
    qdrant_cfg: QdrantConfig,
    matching_cfg: ResumeMatchingConfig,
) -> list[MatchedJob]:
    """
    For each surviving job, query the resume_full collection to get a
    whole-resume similarity score, then blend with the Stage 1 chunk score.

    final_score = (chunk_score * (1 - w)) + (full_score * w)
    where w = matching_cfg.full_resume_weight (default 0.35)
    """
    semaphore = asyncio.Semaphore(10)
    w = matching_cfg.full_resume_weight

    async with get_qdrant_client(qdrant_cfg) as client:

        async def rerank_one(job: MatchedJob) -> None:
            async with semaphore:
                try:
                    query = f"{job.title}\n{job.description}\nSkills: {', '.join(job.skills)}"
                    query_embedding = await embed_text(query)

                    results = await qdrant_find(
                        client=client,
                        collection_name=qdrant_cfg.full_resume_collection,
                        query_embedding=query_embedding,
                        user_id=user_id,
                        resume_id=job.resume_id,
                        top_k=1,
                    )

                    if not results:
                        return  # keep Stage 1 score unchanged

                    full_score     = results[0].get("score", 0.0)
                    full_metadata  = results[0].get("metadata", {})
                    resume_summary = full_metadata.get("summary") or full_metadata.get("information", "")[:1000]
                    
                    chunk_score = job.match_score
                    job.resume_summary = resume_summary

                    # Blend scores
                    blended = (chunk_score * (1 - w)) + (full_score * w)
                    job.match_score = round(min(max(blended, 0.0), 1.0), 4)

                    logger.info(f"[stage_2] {job.title} @ {job.company}: chunk={chunk_score:.3f} full={full_score:.3f} → blended={job.match_score:.3f}")

                except Exception as e:
                    logger.warning(f"[stage_2] Rerank failed for {job.source_url}: {e}")

        await asyncio.gather(*[rerank_one(j) for j in candidates])

    return candidates


def _aggregate_chunk_scores(chunks: list[dict]) -> tuple[float, str]:
    """
    Density-Based Selection:
    1. Group chunks by resume_id.
    2. For each resume, calculate:
       - max_score (best single match)
       - weighted_avg_top_3 (average of top 3 hits, considering section weights)
    3. Final score = 0.4 * max_score + 0.6 * weighted_avg_top_3
    4. Return (winning_score, winning_resume_id)
    """
    if not chunks:
        return 0.0, "default"

    from collections import defaultdict
    resumes = defaultdict(list)
    for c in chunks:
        metadata = c.get("metadata", {})
        rid = metadata.get("resume_id", "default")
        resumes[rid].append(c)

    resume_results = {}
    for rid, resume_chunks in resumes.items():
        # Sort chunks by score descending
        resume_chunks.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        # Max score (peak match)
        max_s = resume_chunks[0].get("score", 0.0)
        
        # Weighted average of top 3
        top_3 = resume_chunks[:3]
        total_score = 0.0
        total_weight = 0.0
        
        for chunk in top_3:
            metadata = chunk.get("metadata", {})
            section = metadata.get("section", "other")
            score = chunk.get("score", 0.0)
            weight = _SECTION_WEIGHTS.get(section, 1.0)
            
            total_score += score * weight
            total_weight += weight
            
        avg_s = total_score / total_weight if total_weight > 0 else 0.0
        
        # Combine: Density (consistency) + Peak (precision)
        final_s = (0.4 * max_s) + (0.6 * avg_s)
        resume_results[rid] = final_s

    # Top result
    logger.info("    [match] Candidate scores:")
    for rid, score in sorted(resume_results.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"      - {rid}: {score:.4f}")

    winning_resume_id = max(resume_results, key=resume_results.get)
    winning_score = resume_results[winning_resume_id]
    
    logger.info(f"  - Winner: {winning_resume_id} (score={winning_score:.3f})")

    return winning_score, winning_resume_id


def _apply_skill_adjustment(score: float, job_skills: list[str], matched_skills: list[str]) -> float:
    """
    Adjusts the semantic similarity score based on explicit skill overlap.
    """
    if not job_skills:
        return score

    match_ratio = len(matched_skills) / len(job_skills)
    original_score = score

    # Penalty: If no skills match, drop the score significantly
    if match_ratio == 0:
        score *= 0.4  # 60% penalty
    # Lower Penalty: If less than 25% match
    elif match_ratio < 0.25:
        score *= 0.7  # 30% penalty
    # Boost: If most skills match, give a slight lift
    elif match_ratio >= 0.75:
        score *= 1.1  # 10% boost

    adjusted = min(max(score, 0.0), 1.0)
    
    if original_score != adjusted:
        logger.info(f"[scoring] Skill Adjustment: {original_score:.3f} -> {adjusted:.3f} (ratio={match_ratio:.2f})")

    return adjusted