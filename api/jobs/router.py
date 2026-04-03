from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from api.deps import get_current_user
from api.jobs.schemas import JobResultResponse, PipelineRunResponse, TriggerResponse, TriggerPipelineRequest
from db.base import get_db
from db.models import JobResult, PipelineRun, User, UserSettings

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResultResponse])
async def get_jobs(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    min_score: float = Query(default=0.0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get matched job results for the current user, newest first."""
    result = await db.execute(
        select(JobResult)
        .where(
            JobResult.user_id == current_user.id,
            JobResult.final_score >= min_score,
        )
        .order_by(JobResult.created_at.desc(), JobResult.rank.asc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/runs", response_model=list[PipelineRunResponse])
async def get_runs(
    limit: int = Query(default=20, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline run history for the current user."""
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.user_id == current_user.id)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_run_details(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific pipeline run with aggregated stats."""
    # Get the run
    result = await db.execute(
        select(PipelineRun)
        .where(
            PipelineRun.id == run_id,
            PipelineRun.user_id == current_user.id
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Get user settings for notification email
    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = settings_result.scalar_one_or_none()
    notification_email = settings.notification_email if settings else None
    
    # Calculate total unique jobs ranked across all runs by this user
    jobs_result = await db.execute(
        select(func.count(JobResult.id.distinct()))
        .where(
            JobResult.user_id == current_user.id,
            JobResult.rank > 0
        )
    )
    total_jobs_ranked = jobs_result.scalar() or 0
    
    # Calculate active duration in minutes from first run start to now
    active_duration_minutes = None
    if run.started_at:
        now = datetime.utcnow()
        duration_seconds = (now - run.started_at).total_seconds()
        active_duration_minutes = max(0, int(duration_seconds / 60))
    
    # Build response with aggregated data
    return PipelineRunResponse(
        id=run.id,
        user_id=run.user_id,
        triggered_by=run.triggered_by,
        status=run.status,
        execution_count=run.execution_count,
        jobs_found=run.jobs_found,
        jobs_matched=run.jobs_matched,
        jobs_ranked=run.jobs_ranked,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        notification_email=notification_email,
        total_jobs_ranked=total_jobs_ranked,
        active_duration_minutes=active_duration_minutes,
    )


@router.post("/trigger", response_model=TriggerResponse, status_code=202)
async def trigger_pipeline(
    body: TriggerPipelineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a pipeline run. Returns immediately, runs in background.
    
    Args:
        body.is_scheduled: If True, this pipeline will be rescheduled after completion
        body.interval_hours: How many hours between scheduled executions (only if is_scheduled=True)
        body.queries: Search queries to use
        body.location: Job location filter
        body.experience: Experience level filter
        body.urls: Direct URLs to scrape
    """
    from workers.tasks import run_pipeline_task
    from db.models import PipelineRun, UserResume
    import logging
    import uuid
    
    logger = logging.getLogger(__name__)
    
    # Check that user has at least one active resume uploaded
    resume_result = await db.execute(
        select(UserResume).where(
            UserResume.user_id == current_user.id,
            UserResume.is_active == True
        ).limit(1)
    )
    if not resume_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Please upload at least one resume before starting a pipeline."
        )
    
    logger.info(f"[trigger_pipeline] Pipeline triggered: is_scheduled={body.is_scheduled}, interval_hours={body.interval_hours}")

    run = PipelineRun(
        user_id=current_user.id, 
        triggered_by="manual",
    )
    run.is_scheduled = body.is_scheduled
    run.interval_hours = body.interval_hours
    
    db.add(run)
    await db.commit()
    await db.refresh(run)
    
    logger.info(f"[trigger_pipeline] Run {run.id} created with is_scheduled={run.is_scheduled}")

    celery_task_id = str(uuid.uuid4())
    run_pipeline_task.apply_async(
        kwargs={"run_id": run.id, "user_id": current_user.id, "custom_urls": body.urls if body.urls else None},
        task_id=celery_task_id
    )

    scheduling_msg = f" Scheduled every {body.interval_hours}h" if body.is_scheduled else ""
    return TriggerResponse(
        run_id=run.id,
        message=f"Pipeline started. Check /jobs/runs for status.{scheduling_msg}",
    )


@router.post("/{run_id}/cancel")
async def cancel_pipeline(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a specific pipeline run."""
    from workers.worker import celery_app
    
    # Find the run
    result = await db.execute(
        select(PipelineRun).where(
            PipelineRun.id == run_id,
            PipelineRun.user_id == current_user.id
        )
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # If already failed or cancelled, can't cancel again
    if run.status in ("failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel a pipeline that is already {run.status}"
        )
    
    # Revoke the Celery task if it's still running (completed_at is NULL)
    if run.celery_task_id and run.completed_at is None:
        try:
            celery_app.control.revoke(run.celery_task_id, terminate=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to revoke task: {e}")
    
    # Mark as cancelled
    run.status = "cancelled"
    run.error_message = "Cancelled by user"
    run.completed_at = datetime.utcnow()
    await db.commit()
    
    return {
        "message": "Pipeline cancelled successfully",
        "run_id": run.id,
        "status": run.status
    }


@router.get("/resumes")
async def get_user_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all resumes uploaded by the user."""
    from db.models import UserResume
    
    result = await db.execute(
        select(UserResume)
        .where(
            UserResume.user_id == current_user.id,
            UserResume.is_active == True
        )
        .order_by(UserResume.created_at.desc())
    )
    resumes = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "file_name": r.file_name,
            "file_path": r.file_path,
            "file_size": r.file_size,
            "created_at": r.created_at.isoformat(),
        }
        for r in resumes
    ]


@router.post("/resumes")
async def add_resume(
    file_name: str,
    file_path: str,
    file_size: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add/register a resume that was uploaded."""
    from db.models import UserResume
    import uuid
    
    resume = UserResume(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        file_name=file_name,
        file_path=file_path,
        file_size=file_size,
        is_active=True,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    
    return {
        "id": resume.id,
        "file_name": resume.file_name,
        "message": "Resume registered successfully",
    }


@router.delete("/resumes/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete/deactivate a resume."""
    from db.models import UserResume
    
    result = await db.execute(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == current_user.id
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    resume.is_active = False
    await db.commit()
    
    return {"message": "Resume deactivated successfully"}
