import logging
from sqlalchemy import select, and_, delete
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from workers.tasks import run_pipeline_task
from db.models import JobResult, PipelineRun
from db.base import AsyncSessionLocal
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

_recovery_complete = False

async def _start_user_pipeline(user_id: str, run_id: str, celery_task_id: str):
    run_pipeline_task.apply_async(
        kwargs={"run_id": run_id, "user_id": user_id},
        task_id=celery_task_id
    )
    logger.info(f"[Scheduler] Task {celery_task_id} started for user {user_id}: {run_id}")


async def _recover_scheduled_pipelines():
    """
    Recovery function: On startup, check all existing pipelines in the database.
    For pipelines with is_scheduled=true and status="done" (or "running") with completed_at set:
    - Calculate elapsed time since completion
    - If interval_hours has passed, create and queue a new run
    
    This ensures no scheduled pipeline is missed if the app was offline.
    
    NOTE: This should only run ONCE on startup, not every check cycle.
    """
    global _recovery_complete
    
    if _recovery_complete:
        logger.debug("[Scheduler] Recovery already completed this session, skipping")
        return
    
    import uuid
    from workers.utils import purge_user_tasks
    
    logger.info("[Scheduler] Starting recovery check for existing pipelines...")
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PipelineRun).where(
                and_(
                    PipelineRun.is_scheduled == True,
                    PipelineRun.status == "done",
                    PipelineRun.completed_at.isnot(None)
                )
            )
        )
        scheduled_pipelines = result.scalars().all()
        
        if not scheduled_pipelines:
            logger.info("[Scheduler] Recovery: No scheduled pipelines found in database")
            _recovery_complete = True
            return
        
        logger.info(f"[Scheduler] Recovery: Found {len(scheduled_pipelines)} scheduled pipeline(s) to check")
        
        recovered_count = 0
        for run in scheduled_pipelines:
            elapsed = datetime.utcnow() - run.completed_at
            elapsed_hours = elapsed.total_seconds() / 3600
            interval_hours = run.interval_hours
            
            logger.info(
                f"[Scheduler] Recovery: Pipeline {run.id} (user: {run.user_id}) - "
                f"Elapsed: {elapsed_hours:.1f}h, Interval: {interval_hours}h, "
                f"Last completed: {run.completed_at.isoformat()}"
            )
            
            if elapsed_hours >= interval_hours:
                logger.info(
                    f"[Scheduler] Recovery: 🚀 Pipeline {run.id} is due for reschedule "
                    f"(elapsed {elapsed_hours:.1f}h >= interval {interval_hours}h)"
                )
                
                try:
                    await purge_user_tasks(db, run.user_id)
                    
                    celery_task_id = str(uuid.uuid4())
                    run.execution_count = run.execution_count + 1
                    run.celery_task_id = celery_task_id
                    run.error_message = None
                    
                    await db.commit()
                    await db.refresh(run)
                    
                    logger.info(
                        f"[Scheduler] Recovery: Reset run {run.id} for reexecution "
                        f"(execution_count now: {run.execution_count})"
                    )
                    
                    await _start_user_pipeline(user_id=run.user_id, run_id=run.id, celery_task_id=celery_task_id)
                    recovered_count += 1
                    logger.info(f"[Scheduler] Recovery: Task submitted to Celery for {run.id}")
                    
                except Exception as e:
                    logger.error(f"[Scheduler] Recovery: Failed to reschedule pipeline {run.id}: {e}", exc_info=True)
                    continue
        
        logger.info(f"[Scheduler] Recovery complete: {recovered_count} pipeline(s) rescheduled")
        _recovery_complete = True


async def _check_and_reschedule_pipelines():
    """
    Check all pipelines marked as scheduled.
    Only reschedule if:
    - status == "done" (NOT running - don't interrupt active tasks)
    - is_scheduled == true
    - completed_at is set and interval has passed
    
    This function is called every 1 minute by the scheduler.
    """
    import uuid
    from workers.utils import purge_user_tasks
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PipelineRun).where(
                and_(
                    PipelineRun.is_scheduled == True,
                    PipelineRun.status == "done",
                    PipelineRun.completed_at.isnot(None)
                )
            )
        )
        scheduled_runs = result.scalars().all()
        
        if scheduled_runs:
            logger.info(f"[Scheduler] Found {len(scheduled_runs)} scheduled pipeline(s) to check for rescheduling")
        
        for run in scheduled_runs:
            next_execution = run.completed_at + timedelta(hours=run.interval_hours)
            time_until_next = next_execution - datetime.utcnow()
            
            logger.info(f"[Scheduler] Pipeline {run.id} (user: {run.user_id}) - Interval: {run.interval_hours}h, Next execution: {next_execution.isoformat()}, Time until next: {time_until_next}")
            
            if next_execution <= datetime.utcnow():
                logger.info(f"[Scheduler] 🚀 Rescheduling pipeline {run.id} for user {run.user_id} (execution #{run.execution_count + 1})")
                
                try:
                    await purge_user_tasks(db, run.user_id)
                    
                    celery_task_id = str(uuid.uuid4())
                    run.execution_count = run.execution_count + 1
                    run.celery_task_id = celery_task_id
                    run.error_message = None
                    
                    await db.commit()
                    await db.refresh(run)
                    
                    logger.info(f"[Scheduler] Reset run {run.id} for reexecution (execution_count now: {run.execution_count})")
                    
                    await _start_user_pipeline(user_id=run.user_id, run_id=run.id, celery_task_id=celery_task_id)
                    logger.info(f"[Scheduler] Task submitted to Celery for {run.id}")
                    
                except Exception as e:
                    logger.error(f"[Scheduler] Failed to reschedule pipeline {run.id}: {e}", exc_info=True)
                    continue

async def _cleanup_old_job_results():
    """
    Delete JobResult rows that are older than 7 days (based on created_at).
    PipelineRun rows are intentionally kept — they are the user's run history.
    This only prunes stale scraped job details to keep the DB lean.
    Runs once on startup and every 24 hours thereafter via APScheduler.
    """
    cutoff = datetime.utcnow() - timedelta(days=7)
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(JobResult).where(JobResult.created_at < cutoff)
            )
            await db.commit()
            deleted = result.rowcount
            if deleted:
                logger.info(f"[Cleanup] Deleted {deleted} job result(s) older than 7 days")
            else:
                logger.info("[Cleanup] No stale job results to delete")
    except Exception as e:
        logger.error(f"[Cleanup] Failed to clean up old job results: {e}", exc_info=True)


def _job_id(user_id:str):
    return f"pipeline_{user_id}"

def schedule_user_pipeline(user_id: str, interval_hours: int):
    """DEPRECATED: This function is now only used for backwards compatibility.
    Per-pipeline scheduling is now handled by _check_and_reschedule_pipelines()"""
    job_id = _job_id(user_id)

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    logger.info(f"[scheduler] Scheduled user {user_id} for every {interval_hours} hours (via legacy method)")

def unschedule_user(user_id: str):
    """DEPRECATED: Per-pipeline scheduling doesn't use this anymore."""
    job_id = _job_id(user_id)

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"[scheduler] Unscheduled user {user_id}")

async def sync_all_users():
    """
    DEPRECATED: User-based scheduler is no longer used.
    Keeping for backwards compatibility only.
    """
    logger.info(f"[scheduler] sync_all_users called (legacy method, not used for per-pipeline scheduling)")


async def start_scheduler():
    scheduler.add_job(
            _check_and_reschedule_pipelines,
            trigger=IntervalTrigger(minutes=1),
            id="reschedule_pipelines",
            replace_existing=True,
    )

    scheduler.add_job(
            _cleanup_old_job_results,
            trigger=IntervalTrigger(hours=24),
            id="cleanup_old_job_results",
            replace_existing=True,
    )

    scheduler.start()
    logger.info(f"[scheduler] Started")

    await _check_and_reschedule_pipelines()

    await _cleanup_old_job_results()


async def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info(f"[scheduler] Stopped")