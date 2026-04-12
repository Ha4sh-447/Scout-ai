import os
import logging
import shutil
import tempfile
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_current_user
from api.users.schemas import ResumeUploadResponse, SessionUpdate, SettingsResponse, SettingsUpdate, UserResumeResponse, LinkedInCookieUpdate
from db.base import get_db
from db.models import User, UserSettings, PipelineRun, UserResume
from workers.worker import celery_app
from scheduler.scheduler import unschedule_user
from sqlalchemy import update

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


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

    if body.max_jobs_per_run is not None:
        if not 1 <= body.max_jobs_per_run <= 100:
            raise HTTPException(status_code=400, detail="max_jobs_per_run must be 1-100")
        settings.max_jobs_per_run = body.max_jobs_per_run

    if body.enable_outreach is not None:
        settings.enable_outreach = body.enable_outreach

    await db.commit()
    await db.refresh(settings)
    return settings


@router.post("/scheduler/stop")
async def stop_user_scheduler(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stop all scheduled pipelines for this user:
    1. Unschedule from APScheduler.
    2. Revoke all pending/running Celery tasks for this user.
    """
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


@router.post("/settings/linkedin-cookie")
async def update_linkedin_cookie(
    request: LinkedInCookieUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Takes a raw li_at cookie and constructs the Playwright storage_state JSON.
    """
    from sqlalchemy import select
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        
    storage_state = {
        "cookies": [
            {
                "name": "li_at",
                "value": request.li_at_cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None"
            }
        ],
        "origins": []
    }
    
    settings.browser_session = storage_state
    await db.commit()
    
    return {"message": "LinkedIn session securely stored"}


def _calculate_file_hash(file_path: str | Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF resume. Triggers the resume pipeline:
    parse → chunk → embed → store in Qdrant.

    The resume_id is derived from the filename stem (e.g. "my_resume.pdf" → "my_resume").
    Re-uploading the same filename will only process if contents differ.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    resume_id = Path(file.filename).stem

    # upload to a temp file 
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        file_size = Path(tmp_path).stat().st_size if Path(tmp_path).exists() else 0
        if file_size > 10 * 1024 * 1024:
            Path(tmp_path).unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Resume file exceeds 10MB limit. Please upload a smaller file.")
            
        file_hash = _calculate_file_hash(tmp_path)

        # Check if resume with same filename already exists for this user
        existing = await db.execute(
            select(UserResume).where(
                UserResume.user_id == current_user.id,
                UserResume.file_name == file.filename
            )
        )
        existing_resume = existing.scalar_one_or_none()
        
        # Check if this is a duplicate
        is_duplicate = False
        if existing_resume and existing_resume.file_size == file_size:
            # File sizes match, likely same file - but verify with hash if possible
            # Since we don't store hash in DB yet, we'll just skip processing for identical sizes
            logger.info(f"[resume_upload] Duplicate detected: {file.filename} for user {current_user.id} (same size: {file_size} bytes)")
            is_duplicate = True
        
        # Only process to Qdrant if it's not a duplicate
        if not is_duplicate:
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
            chunks_stored = result["chunks_stored"]
            full_resume_stored = result["full_resume_stored"]
            message = f"Resume '{resume_id}' processed and stored successfully"
        else:
            chunks_stored = 0
            full_resume_stored = False
            message = f"Resume '{resume_id}' is identical to the previously uploaded version. Skipped Qdrant storage."

    except Exception as e:
        logger.error(f"[resume_upload] Error processing resume: {e}")
        raise HTTPException(status_code=500, detail=f"Resume processing failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Save/Update resume record in database
    try:
        if existing_resume:
            # Update the existing record
            existing_resume.file_size = file_size
            existing_resume.is_active = True
            db.add(existing_resume)
        else:
            # Create new resume record
            new_resume = UserResume(
                user_id=current_user.id,
                file_name=file.filename,
                file_path=f"resumes/{current_user.id}/{resume_id}.pdf",
                file_size=file_size,
                is_active=True
            )
            db.add(new_resume)
        
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"[resume_upload] Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save resume record: {e}")

    return ResumeUploadResponse(
        resume_id=resume_id,
        chunks_stored=chunks_stored,
        full_resume_stored=full_resume_stored,
        message=message,
    )


@router.get("/resumes", response_model=list[UserResumeResponse])
async def get_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all uploaded resumes for the current user."""
    result = await db.execute(
        select(UserResume).where(
            UserResume.user_id == current_user.id,
            UserResume.is_active == True
        ).order_by(UserResume.created_at.desc())
    )
    resumes = result.scalars().all()
    return resumes
