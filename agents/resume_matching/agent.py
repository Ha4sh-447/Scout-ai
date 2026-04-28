import asyncio
import logging
import re

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

_AI_HINTS = {
    "ai", "ml", "machine learning", "deep learning", "llm", "nlp", "genai", "artificial intelligence",
    "computer vision", "rag", "prompt", "data scientist", "model"
}
_SWE_HINTS = {
    "swe", "software engineer", "backend", "frontend", "full stack", "full-stack", "intern", "internship",
    "react", "node", "java", "golang", "python", "developer", "engineering"
}

_NAV_KEYWORDS = {
    "student", "employer", "login", "register", "signup", "rules", "terms", "privacy", "about", "contact",
    "dashboard", "profile", "settings", "notifications", "support", "help", "company", "companies"
}


def _normalize_text(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _contains_any(text: str, phrases: set[str]) -> bool:
    return any(p in text for p in phrases)


def _infer_role_signal(job: Job) -> str | None:
    haystack = _normalize_text(
        " ".join(
            [job.search_query or "", job.title or "", job.description or "", " ".join(job.skills or [])]
        )
    )
    if not haystack:
        return None

    ai_hits = sum(1 for p in _AI_HINTS if p in haystack)
    swe_hits = sum(1 for p in _SWE_HINTS if p in haystack)

    if ai_hits > swe_hits and ai_hits > 0:
        return "ai"
    if swe_hits > ai_hits and swe_hits > 0:
        return "swe"
    return None


def _infer_resume_track(resume_id: str) -> str | None:
    rid = _normalize_text(resume_id)
    if not rid:
        return None

    has_ai = _contains_any(rid, _AI_HINTS)
    has_swe = _contains_any(rid, _SWE_HINTS)

    if has_ai and not has_swe:
        return "ai"
    if has_swe and not has_ai:
        return "swe"
    return None


def _apply_query_prior(score: float, resume_id: str, role_signal: str | None) -> float:
    if not role_signal:
        return score

    track = _infer_resume_track(resume_id)
    if not track:
        return score

    if track == role_signal:
        return min(max(score * 1.08, 0.0), 1.0)
    return min(max(score * 0.95, 0.0), 1.0)


def _build_semantic_job_query(job: Job) -> str:
    """Build a richer semantic query from the full scraped job context."""
    parts = [
        job.title or "",
        job.description or "",
        f"Skills: {', '.join(job.skills or [])}",
        job.requirements or "",
        job.responsibilities or "",
        job.benefits or "",
        job.about_company or "",
        f"Experience: {job.experience or ''}",
    ]
    return "\n".join([p for p in parts if p and p.strip()])


def _score_resume_chunks_for_vote(
    chunks: list[dict],
    cfg: ResumeMatchingConfig,
) -> tuple[int, int, float, float]:
    """
    Returns:
      high_count: chunks above high threshold
      strong_count: chunks significantly above threshold
      weighted_avg: section-weighted average over top chunks
      final_score: vote-aware semantic score for ranking
    """
    if not chunks:
        return 0, 0, 0.0, 0.0

    threshold = cfg.high_chunk_score_threshold
    strong_threshold = min(0.95, threshold + 0.08)

    high_count = sum(1 for c in chunks if c.get("score", 0.0) >= threshold)
    strong_count = sum(1 for c in chunks if c.get("score", 0.0) >= strong_threshold)

    total_score = 0.0
    total_weight = 0.0
    for chunk in chunks[: max(3, min(len(chunks), cfg.top_k_chunks))]:
        metadata = chunk.get("metadata", {})
        section = metadata.get("section", "other")
        score = chunk.get("score", 0.0)
        weight = _SECTION_WEIGHTS.get(section, 1.0)
        total_score += score * weight
        total_weight += weight

    weighted_avg = total_score / total_weight if total_weight > 0 else 0.0

    vote_bonus = 0.0
    if high_count >= cfg.min_high_chunks_for_boost:
        vote_bonus += min(0.06, 0.02 * (high_count - cfg.min_high_chunks_for_boost + 1))
    if strong_count > 0:
        vote_bonus += min(0.04, 0.015 * strong_count)

    final_score = min(max(weighted_avg + vote_bonus, 0.0), 1.0)
    return high_count, strong_count, weighted_avg, final_score

async def resume_matching_node(state: ResumeMatchingState) -> dict:
    jobs         = state.get("unique_jobs", [])
    user_id      = state["user_id"]
    resume_id    = state.get("resume_id")
    resume_ids   = state.get("resume_ids")
    qdrant_cfg   = state.get("qdrant_cfg")   or QdrantConfig()
    matching_cfg = state.get("matching_cfg") or ResumeMatchingConfig()

    logger.info(
        f"[resume_matching_node] Matching {len(jobs)} jobs for user {user_id} "
        f"(resume_id: {resume_id}, resume_ids: {resume_ids})"
    )

    if not jobs:
        return {"matched_jobs": [], "status": "matching_done"}

    try:
        matched = await _match_all(
            jobs,
            user_id,
            qdrant_cfg,
            matching_cfg,
            resume_id=resume_id,
            resume_ids=resume_ids,
        )
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
    resume_ids: list[str] | None = None,
) -> list[MatchedJob]:

    stage1_results = await _stage1_chunk_filter(
        jobs,
        user_id,
        qdrant_cfg,
        matching_cfg,
        resume_id=resume_id,
        resume_ids=resume_ids,
    )
    logger.info(f"[stage_1] {len(stage1_results)} jobs passed min_score filter")

    if not stage1_results:
        return []

    candidates = stage1_results[: matching_cfg.rerank_top_n]
    rest       = stage1_results[matching_cfg.rerank_top_n :]

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
    resume_ids: list[str] | None = None,
) -> list[MatchedJob]:
    """Query resume_chunks for each job concurrently."""
    survivors: list[MatchedJob] = []
    semaphore = asyncio.Semaphore(10)

    async with get_qdrant_client(qdrant_cfg) as client:

        async def filter_one(job: Job) -> None:
            async with semaphore:
                try:
                    result = await _chunk_score_job(
                        job,
                        user_id,
                        client,
                        qdrant_cfg,
                        matching_cfg,
                        resume_id=resume_id,
                        resume_ids=resume_ids,
                    )
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
    resume_ids: list[str] | None = None,
) -> MatchedJob | None:
    """Score one job via chunk similarity. Returns None if below threshold."""
    query = _build_semantic_job_query(job)
    
    # embedding
    query_embedding = await embed_text(query)
    role_signal = _infer_role_signal(job)

    search_resume_ids: list[str] = []
    if resume_id:
        search_resume_ids = [resume_id]
    elif resume_ids:
        search_resume_ids = list(dict.fromkeys([rid for rid in resume_ids if rid]))

    if search_resume_ids:
        resume_scores: list[tuple[str, int, int, float, float, list[dict], list[str]]] = []
        for rid in search_resume_ids:
            rid_chunks = await qdrant_find(
                client=client,
                collection_name=qdrant_cfg.collection_name,
                query_embedding=query_embedding,
                user_id=user_id,
                resume_id=rid,
                top_k=cfg.top_k_chunks,
            )
            if not rid_chunks:
                continue
            high_count, strong_count, rid_chunk_score, rid_vote_score = _score_resume_chunks_for_vote(rid_chunks, cfg)

            rid_matched_text = " ".join(
                c.get("information", c.get("text", "")) for c in rid_chunks
            ).lower()
            rid_top_skills = [s for s in job.skills if s.lower() in rid_matched_text]
            rid_final_score = _apply_skill_adjustment(rid_vote_score, job.skills, rid_top_skills)
            rid_final_with_prior = _apply_query_prior(rid_final_score, rid, role_signal)

            logger.info(
                f"[stage_1] Resume candidate '{rid}' for '{job.title}': "
                f"high_chunks={high_count}, strong_chunks={strong_count}, "
                f"chunk_avg={rid_chunk_score:.4f}, vote_score={rid_vote_score:.4f}, final={rid_final_score:.4f}, "
                f"final_with_prior={rid_final_with_prior:.4f}, matched_skills={len(rid_top_skills)}, "
                f"role_signal={role_signal}"
            )
            resume_scores.append((rid, high_count, strong_count, rid_chunk_score, rid_final_with_prior, rid_chunks, rid_top_skills))

        if not resume_scores:
            return None

        winning_resume_id, high_count, strong_count, chunk_score, final_score, chunks, top_skills = max(
            resume_scores, key=lambda x: (x[1], x[2], x[4], x[3])
        )
        logger.info(
            f"[stage_1] Resume winner for '{job.title}': {winning_resume_id} "
            f"(high_chunks={high_count}, strong_chunks={strong_count}, score={final_score:.4f})"
        )
    else:
        chunks = await qdrant_find(
            client=client,
            collection_name=qdrant_cfg.collection_name,
            query_embedding=query_embedding,
            user_id=user_id,
            resume_id=None,
            top_k=max(cfg.top_k_chunks, 20),
        )
        if not chunks:
            return None

        from collections import defaultdict
        by_resume: dict[str, list[dict]] = defaultdict(list)
        for c in chunks:
            rid = c.get("metadata", {}).get("resume_id", "default")
            by_resume[rid].append(c)

        resume_scores: list[tuple[str, int, int, float, float, list[dict], list[str]]] = []
        for rid, rid_chunks in by_resume.items():
            rid_chunks.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            rid_chunks = rid_chunks[: cfg.top_k_chunks]

            high_count, strong_count, rid_chunk_score, rid_vote_score = _score_resume_chunks_for_vote(rid_chunks, cfg)
            rid_matched_text = " ".join(
                c.get("information", c.get("text", "")) for c in rid_chunks
            ).lower()
            rid_top_skills = [s for s in job.skills if s.lower() in rid_matched_text]
            rid_final_score = _apply_skill_adjustment(rid_vote_score, job.skills, rid_top_skills)
            resume_scores.append((rid, high_count, strong_count, rid_chunk_score, rid_final_score, rid_chunks, rid_top_skills))

        if not resume_scores:
            return None

        winning_resume_id, _, _, chunk_score, final_score, chunks, top_skills = max(
            resume_scores, key=lambda x: (x[1], x[2], x[4], x[3])
        )

    logger.info(f"[stage_1] Job: {job.title} @ {job.company} -> Base Chunk Score: {chunk_score:.4f} (Resume: {winning_resume_id})")

    title_words = (job.title or "").lower().split()
    if len(title_words) == 1 and title_words[0] in _NAV_KEYWORDS:
        logger.info(f"[scoring] CRITICAL PENALTY: Navigation-like title detected ('{job.title}')")
        final_score *= 0.1
    elif len(title_words) < 2:
        final_score *= 0.7  # relaxed from 0.5
        
    _DEDICATED_PLATFORMS = {"linkedin", "indeed", "glassdoor", "reddit"}
    is_dedicated = job.source_platform in _DEDICATED_PLATFORMS
    
    if not job.description or len(job.description) < 50:
        if is_dedicated:
            logger.info(f"[scoring] PENALTY: Extremely short description on dedicated platform ({job.source_platform})")
            final_score *= 0.4
        elif not job.description or len(job.description) < 20:
            logger.info(f"[scoring] PENALTY: Extremely short description on generic platform")
            final_score *= 0.8


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
        experience=job.experience,
        min_years_experience=job.min_years_experience,
        description=job.description,
        responsibilities=job.responsibilities,
        requirements=job.requirements,
        benefits=job.benefits,
        about_company=job.about_company,
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
    """Query full resume for reranking."""
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
    """Density-Based Selection logic."""
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
        resume_chunks.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        max_s = resume_chunks[0].get("score", 0.0)
        
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