import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_current_user
from api.users.schemas import ResumeUploadResponse, SessionUpdate, SettingsResponse, SettingsUpdate
from db.base import get_db
from db.models import User, UserSettings, PipelineRun
from workers.worker import celery_app
from scheduler.scheduler import unschedule_user
from sqlalchemy import update

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@router.patch("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    if body.interval_hours is not None:
        if not 1 <= body.interval_hours <= 24:
            raise HTTPException(status_code=400, detail="interval_hours must be 1-24")
        settings.interval_hours = body.interval_hours

    if body.search_queries is not None:
        if len(body.search_queries) > 10:
            raise HTTPException(status_code=400, detail="Max 10 search queries")
        settings.search_queries = body.search_queries

    if body.location is not None:
        settings.location = body.location

    if body.resume_summary is not None:
        settings.resume_summary = body.resume_summary

    if body.notification_email is not None:
        settings.notification_email = body.notification_email

    if body.is_scheduler_active is not None:
        settings.is_scheduler_active = body.is_scheduler_active

    await db.commit()
    await db.refresh(settings)
    return settings


@router.post("/scheduler/stop")
async def stop_user_scheduler(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    1. Deactivate scheduler in settings.
    2. Remove from APScheduler.
    3. Revoke all pending/running Celery tasks for this user.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    # Set is_scheduler_active as false and remove from scheduler
    settings.is_scheduler_active = False

    try:
        unschedule_user(current_user.id)
    except Exception as e:
        logger.warning(f"Failed to unschedule user {current_user.id}: {e}")

    # Purge celery tasks
    from workers.utils import purge_user_tasks
    revoked_count = await purge_user_tasks(db, current_user.id)

    return {
        "message": "Scheduler stopped and pending tasks revoked",
        "revoked_tasks": revoked_count,
        "is_scheduler_active": False
    }

@router.post("/settings/session")
async def update_browser_session(
    request: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the browser session (storage state) for the current user.
    This session will be used for all future scraping tasks.
    """
    from sqlalchemy import select
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
    
    settings.browser_session = request.storage_state
    await db.commit()
    
    return {"message": "Browser session updated successfully"}


@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a PDF resume. Triggers the resume pipeline:
    parse → chunk → embed → store in Qdrant.

    The resume_id is derived from the filename stem (e.g. "my_resume.pdf" → "my_resume").
    Re-uploading the same filename replaces the previous vectors.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    resume_id = Path(file.filename).stem

    # upload to a temp file 
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        from resume.pipeline import process_resume_upload
        from models.config import QdrantConfig, ResumeMatchingConfig

        qdrant_cfg = QdrantConfig(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ.get("QDRANT_API_KEY"),
        )

        result = await process_resume_upload(
            pdf_path=tmp_path,
            user_id=current_user.id,
            resume_id=resume_id,
            qdrant_cfg=qdrant_cfg,
            matching_cfg=ResumeMatchingConfig(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume processing failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return ResumeUploadResponse(
        resume_id=resume_id,
        chunks_stored=result["chunks_stored"],
        full_resume_stored=result["full_resume_stored"],
        message=f"Resume '{resume_id}' processed and stored successfully",
    )
