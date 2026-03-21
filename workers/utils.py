import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import PipelineRun
from workers.worker import celery_app

logger = logging.getLogger(__name__)

async def purge_user_tasks(db: AsyncSession, user_id: str):
    """
    Finds and revokes all pending/running Celery tasks for a specific user.
    Marks their database records as failed with 'Superseded' message.
    """
    try:
        # Find all active runs for this user
        result = await db.execute(
            select(PipelineRun).where(
                PipelineRun.user_id == user_id,
                PipelineRun.status.in_(["pending", "running"])
            )
        )
        active_runs = result.scalars().all()

        revoked_count = 0
        for run in active_runs:
            if run.celery_task_id:
                try:
                    logger.info(f"[purge] Revoking task: {run.celery_task_id}")
                    # terminate=True kills it if it's already running
                    celery_app.control.revoke(run.celery_task_id, terminate=True)
                    logger.info(f"[purge] Revoke command sent for: {run.celery_task_id}")
                    revoked_count += 1
                except Exception as e:
                    logger.error(f"[purge] Failed to revoke task {run.celery_task_id}: {e}")
            
            run.status = "failed"
            run.error_message = "Superseded by a newer task or manual stop."

        await db.commit()
        if revoked_count > 0:
            logger.info(f"[purge] Revoked {revoked_count} stale tasks for user {user_id}")
        
        return revoked_count
    except Exception as e:
        logger.error(f"[purge] Error during user task purge: {e}")
        return 0
