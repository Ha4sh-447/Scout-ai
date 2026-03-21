from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_current_user
from api.jobs.schemas import JobResultResponse, PipelineRunResponse, TriggerResponse
from db.base import get_db
from db.models import JobResult, PipelineRun, User

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


@router.post("/trigger", response_model=TriggerResponse, status_code=202)
async def trigger_pipeline(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a pipeline run. Returns immediately, runs in background."""
    from workers.tasks import run_pipeline_task
    from db.models import PipelineRun

    run = PipelineRun(user_id=current_user.id, triggered_by="manual")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Dispatch to Celery worker
    run_pipeline_task.delay(run_id=run.id, user_id=current_user.id)

    return TriggerResponse(
        run_id=run.id,
        message="Pipeline started. Check /jobs/runs for status.",
    )
