import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from workers.tasks import run_pipeline_task
from db.models import PipelineRun
from db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

async def _start_user_pipeline(user_id: str, run_id: str, celery_task_id: str):
    run_pipeline_task.apply_async(
        kwargs={"run_id": run_id, "user_id": user_id},
        task_id=celery_task_id
    )
    logger.info(f"[Scheduler] Task {celery_task_id} started for user {user_id}: {run_id}")

async def _create_pipeline(user_id: str):
    from workers.utils import purge_user_tasks
    import uuid
    celery_task_id = str(uuid.uuid4())
    
    async with AsyncSessionLocal() as db:
        #Purge any existing tasks for this user first
        await purge_user_tasks(db, user_id)
        
        #Create the new run with pre-generated task ID
        run = PipelineRun(
            user_id=user_id, 
            triggered_by="scheduler",
            celery_task_id=celery_task_id
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    await _start_user_pipeline(user_id=user_id, run_id=run_id, celery_task_id=celery_task_id)

def _job_id(user_id:str):
    return f"pipeline_{user_id}"

def schedule_user_pipeline(user_id: str, interval_hours: int):
    job_id = _job_id(user_id)

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
            _create_pipeline,
            trigger=IntervalTrigger(interval_hours),
            id = job_id,
            args=[user_id],
            replace_existing=True,
            misfire_grace_time=300,
            )
    logger.info(f"[scheduler] Scheduled user {user_id} for every {interval_hours}")

def unschedule_user(user_id: str):
    job_id = _job_id(user_id)

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"[scheduler] Unscheduled user {user_id}")

# Sync every user
async def sync_all_users():
    """
    Load all active users from DB and sync scheduler state.
    Runs on startup and every 5 minutes to pick up settings changes.
    """
    from db.base import AsyncSessionLocal
    from db.models import UserSettings
 
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserSettings).where(UserSettings.is_scheduler_active == True)
        ) 
        active_settings = result.scalars().all()
 
    active_user_ids = {s.user_id for s in active_settings}
 
    #Add/update jobs for active users
    for s in active_settings:
        await schedule_user(s.user_id, s.interval_hours)
 
    # Remove jobs for users who deactivated their scheduler
    for job in scheduler.get_jobs():
        if job.id.startswith("pipeline_"):
            uid = job.id.replace("pipeline_", "")
            if uid not in active_user_ids:
                scheduler.remove_job(job.id)
                logger.info(f"[scheduler] Removed job for inactive user {uid}")


async def start_scheduler():
    scheduler.add_job(
            start_scheduler,
            trigger= IntervalTrigger(minutes=5),
            id="sync_users",
            replace_existing=True,
            )

    scheduler.start()
    logger(f"[scheduler] Started")

    await sync_all_users()


async def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info(f"[scheduler] Stopped")
