"""
Celery task that runs the full job pipeline for one user.
"""



import asyncio
import logging
import os
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from db.models import JobResult, Link, PipelineRun, User, UserSettings
from models.config import (
        EmailConfig, QdrantConfig, RankingConfig,
        ResumeMatchingConfig, ScraperConfig,
    )
from agents.job_discovery.graph import job_discovery_graph
from agents.resume_matching.graph import resume_matching_graph
from agents.ranking.graph import ranking_graph
from agents.messaging.graph import messaging_graph
from agents.notification.graph import notification_graph
from extractors.deduplicator import deduplicate_within_batch
from scrapers.page_loader import detect_platform

from dotenv import load_dotenv
load_dotenv()

from workers.worker import celery_app

logger = logging.getLogger(__name__)


def _make_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    db_url = (
        os.environ["DATABASE_URL"]
        .replace("postgresql+asyncpg://", "postgresql+asyncpg://")
        .replace("postgresql://", "postgresql+asyncpg://")
        .replace("postgres://", "postgresql+asyncpg://")
    )
    return create_async_engine(db_url, pool_pre_ping=True)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def run_pipeline_task(self, run_id: str, user_id: str, custom_urls: list[str] = None):
    """Synchronous Celery entry point - runs the async pipeline in a new event loop."""
    try:
        asyncio.run(_run_pipeline(run_id, user_id, custom_urls=custom_urls))
    except Exception as exc:
        logger.error(f"[task] Pipeline failed for user {user_id}: {exc}")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_mark_run_failed(run_id, str(exc)))
        finally:
            loop.close()
        raise self.retry(exc=exc)


async def _run_pipeline(run_id: str, user_id: str, custom_urls: list[str] = None):
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:

            # Load user
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Load settings
            settings_result = await db.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = settings_result.scalar_one_or_none()
            if not settings:
                raise ValueError(f"Settings not found for user {user_id}")

            # Load links
            if custom_urls:
                urls = custom_urls
                platforms = list({detect_platform(u) for u in urls})
            else:
                links_result = await db.execute(
                    select(Link).where(Link.user_id == user_id, Link.is_active == True)
                )
                links = links_result.scalars().all()
                urls = [l.url for l in links]
                platforms = list({l.platform for l in links}) if links else ["linkedin"]

            # Mark run as running
            run_result = await db.execute(
                select(PipelineRun).where(PipelineRun.id == run_id)
            )
            run = run_result.scalar_one_or_none()
            if run:
                run.status = "running"
                await db.commit()

            logger.info(
                f"[pipeline] Starting run {run_id} for user {user_id} "
                f"({len(urls)} links, queries: {settings.search_queries})"
            )

            qdrant_cfg   = QdrantConfig(
                url=os.environ["QDRANT_URL"],
                api_key=os.environ.get("QDRANT_API_KEY"),
            )
            matching_cfg = ResumeMatchingConfig()
            ranking_cfg  = RankingConfig(
                match_weight=0.85,
                recency_weight=0.075,
                source_quality_weight=0.075,
            )

            # Stage 1: Job discovery
            all_jobs = []
            for query in (settings.search_queries or []):
                try:
                    result = await job_discovery_graph.ainvoke({
                        "user_id":        user_id,
                        "urls":           urls,
                        "search_queries": [query],
                        "location":       settings.location or "India",
                        "platforms":      platforms,
                        "scraper_config": ScraperConfig(
                            max_jobs_per_url=10,
                            batch_size=5,
                            enrich_jobs=True,
                        ),
                        "qdrant_cfg":    qdrant_cfg,
                        "matching_cfg":  matching_cfg,
                        "browser_session": settings.browser_session,
                        "raw_jobs": [], "parsed_jobs": [], "unique_jobs": [],
                        "errors": [], "status": "starting",
                        "freshness": "default", "retry_count": 0,
                    })
                    all_jobs.extend(result.get("unique_jobs", []))
                except Exception as e:
                    logger.warning(f"[pipeline] Discovery failed for '{query}': {e}")

            if all_jobs:
                all_jobs = deduplicate_within_batch(all_jobs)

            if not all_jobs:
                await _finish_run(db, run_id, status="done", jobs_found=0)
                logger.info(f"[pipeline] No new jobs found for run {run_id}")
                return

            # Stage 2: Resume matching
            match_result = await resume_matching_graph.ainvoke({
                "user_id":      user_id,
                "unique_jobs":  all_jobs,
                "qdrant_cfg":   qdrant_cfg,
                "matching_cfg": matching_cfg,
                "matched_jobs": [], "errors": [], "status": "starting",
            })
            matched_jobs = match_result.get("matched_jobs", [])

            if not matched_jobs:
                await _finish_run(db, run_id, status="done", jobs_found=len(all_jobs))
                logger.info(f"[pipeline] No jobs passed match threshold for run {run_id}")
                return

            # Stage 3: Ranking
            rank_result = await ranking_graph.ainvoke({
                "user_id":      user_id,
                "matched_jobs": matched_jobs,
                "ranking_cfg":  ranking_cfg,
                "ranked_jobs":  [], "errors": [], "status": "starting",
            })
            ranked_jobs = rank_result.get("ranked_jobs", [])

            # Stage 4: Messaging
            msg_result = await messaging_graph.ainvoke({
                "user_id":          user_id,
                "ranked_jobs":      ranked_jobs,
                "resume_summary":   settings.resume_summary or "",
                "jobs_with_drafts": [], "errors": [], "status": "starting",
            })
            jobs_with_drafts = msg_result.get("jobs_with_drafts", ranked_jobs)

            # Save job results to Postgres
            for job in jobs_with_drafts:
                jr = JobResult(
                    run_id=run_id,
                    user_id=user_id,
                    content_hash=job.content_hash or "",
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    source_url=job.source_url,
                    source_platform=job.source_platform,
                    match_score=job.match_score,
                    final_score=job.final_score,
                    rank=job.rank,
                    skills=job.skills,
                    top_matching_skills=job.top_matching_skills,
                    salary=job.salary,
                    description=job.description,
                    poster_type=job.poster_type,
                    outreach_email_draft=getattr(job, "outreach_email_draft", None),
                    outreach_linkedin_draft=getattr(job, "outreach_linkedin_draft", None),
                )
                db.add(jr)
            await db.commit()

            # Stage 5: Notification
            if settings.notification_email:
                try:
                    email_cfg = EmailConfig(
                        sender_email=os.environ["EMAIL_SENDER"],
                        sender_password=os.environ["EMAIL_PASSWORD"],
                        recipient_email=settings.notification_email,
                    )
                    run_label = datetime.utcnow().strftime("%-d %b %Y · %H:%M UTC")
                    await notification_graph.ainvoke({
                        "user_id":          user_id,
                        "jobs_with_drafts": jobs_with_drafts,
                        "email_cfg":        email_cfg,
                        "run_label":        run_label,
                        "status":           "starting",
                    })
                except Exception as e:
                    logger.warning(f"[pipeline] Notification failed: {e}")

            await _finish_run(
                db, run_id,
                status="done",
                jobs_found=len(all_jobs),
                jobs_matched=len(matched_jobs),
                jobs_ranked=len(ranked_jobs),
            )
            logger.info(
                f"[pipeline] Run {run_id} complete: "
                f"{len(all_jobs)} found, {len(matched_jobs)} matched, "
                f"{len(ranked_jobs)} ranked"
            )

    finally:
        await engine.dispose()


async def _finish_run(
    db,
    run_id: str,
    status: str,
    jobs_found: int = 0,
    jobs_matched: int = 0,
    jobs_ranked: int = 0,
):
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if run:
        run.status = status
        run.jobs_found = jobs_found
        run.jobs_matched = jobs_matched
        run.jobs_ranked = jobs_ranked
        run.completed_at = datetime.utcnow()   # naive UTC — matches TIMESTAMP WITHOUT TIME ZONE
        await db.commit()


async def _mark_run_failed(run_id: str, error: str):
    """
    Called in a fresh event loop after the main pipeline loop has closed.
    Creates its own engine so it has no dependency on the previous loop.
    """

    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error_message = error[:1000]
                run.completed_at = datetime.utcnow()
                await db.commit()
    finally:
        await engine.dispose()