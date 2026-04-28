import subprocess
import os
import sys
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from api.deps import get_current_user
from db.models import User, Link, UserSettings
from api.scrapers.schemas import ScrapeRequest, ScrapeResponse, SaveSearchLinksRequest, SaveSearchLinksResponse, SavedLinkResponse, AuthenticateRequest
from scrapers.page_loader import load_job_pages, detect_platform
from tools.browser.browser_manager import BrowserManager
from db.base import get_db
from db.models import PipelineRun
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scrapers", tags=["scrapers"])

@router.post("/authenticate")
async def trigger_browser_authentication(
    request: AuthenticateRequest = AuthenticateRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers the browser authentication helper to save LinkedIn session.
    
    This will:
    1. Check if a session already exists (skips if found)
    2. Open a browser window on the host machine
    3. Let user log into LinkedIn and/or Indeed
    4. Save the browser session to the database for future pipelines
    5. User can then scrape personalized results using saved session
    
    Note: Only works on development machines where you have access to the server UI.
    Only needs to be done ONCE per user - subsequent calls reuse the saved session.
    """
    try:
        # Validate platforms
        if not all(p in ["linkedin", "indeed"] for p in request.platforms):
            raise HTTPException(status_code=400, detail="Invalid platform(s) requested")

        # Session may exist, but we allow re-triggering to "Sync" or update
        script_path = os.path.join(os.getcwd(), "scripts", "auth_helper.py")
        
        # Call auth_helper with user_id for database storage
        env = os.environ.copy()
        
        # Log to file instead of suppressing output for debugging
        log_file_path = os.path.join("data", f"auth_{current_user.id}.log")
        os.makedirs("data", exist_ok=True)
        with open(log_file_path, "w") as logfile:
            subprocess.Popen(
                [sys.executable, script_path, "--platforms", *request.platforms, "--user-id", current_user.id],
                env=env,
                stdout=logfile,
                stderr=subprocess.STDOUT
            )
        
        logger.info(f"[authenticate] Browser auth helper triggered for user {current_user.id}, log: {log_file_path}")
        
        return {
            "message": "Browser authentication window opened. Session will auto-save after login.",
            "authenticated": False,
            "status": "Authentication in progress",
            "instructions": [
                "1. A browser window has opened with login pages for the selected platforms",
                "2. Log into the platforms you want to use",
                "3. The script will auto-detect successful login and save your session",
                "4. The browser will close automatically after authentication",
                "5. Check back here shortly - you'll see the status updated",
                "💡 For Indeed, once you reach the job search or account page, it will be detected.",
                "📌 This only needs to be done ONCE. Future runs will reuse this session."
            ]
        }
    except Exception as e:
        logger.error(f"[authenticate] Failed to trigger auth helper: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger authentication: {e}")


@router.get("/authenticate/status")
async def get_authentication_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if the user has a saved browser session.
    Returns status indicating if LinkedIn/Indeed sessions are available.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings or not settings.browser_session:
        return {
            "authenticated": False,
            "message": "No saved browser session found",
            "browser_session": None
        }
    
    # Check what's in the session
    session = settings.browser_session
    has_linkedin = False
    has_indeed = False
    
    if isinstance(session, dict):
        cookies = session.get("cookies", [])
        for cookie in cookies:
            domain = cookie.get("domain", "")
            if "linkedin" in domain.lower():
                has_linkedin = True
            elif "indeed" in domain.lower():
                has_indeed = True
    
    return {
        "authenticated": has_linkedin or has_indeed,
        "has_linkedin": has_linkedin,
        "has_indeed": has_indeed,
        "message": "Browser session is active",
        "saved_at": settings.updated_at.isoformat() if settings.updated_at else None
    }


@router.delete("/authenticate/session")
async def clear_browser_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear the saved browser session. User will need to re-authenticate.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    if settings:
        settings.browser_session = None
        await db.commit()
    
    logger.info(f"[authenticate] Browser session cleared for user {current_user.id}")
    
    return {"message": "Browser session cleared. You will need to authenticate again."}


@router.post("/scrape", response_model=ScrapeResponse, status_code=202)
async def scrape_links(
    request: ScrapeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scrape a list of job links using the full background pipeline.
    Platforms are auto-detected.
    
    Args:
        request.links: List of URLs to scrape
        request.is_scheduled: If True, this scrape will be rescheduled after completion
        request.interval_hours: How many hours between scheduled scrapes (only if is_scheduled=True)
    """
    if not request.links:
        raise HTTPException(status_code=400, detail="No links provided")

    try:
        from workers.tasks import run_pipeline_task
        from workers.utils import purge_user_tasks
        

        await purge_user_tasks(db, current_user.id)

        import uuid
        celery_task_id = str(uuid.uuid4())

        run = PipelineRun(
            user_id=current_user.id, 
            triggered_by="manual",
            celery_task_id=celery_task_id,
            is_scheduled=request.is_scheduled,
            interval_hours=request.interval_hours
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            run_pipeline_task.apply_async(
                kwargs={
                    "run_id": run.id, 
                    "user_id": current_user.id, 
                    "custom_urls": request.links
                },
                task_id=celery_task_id
            )
        except Exception as celery_err:
            run.status = "failed"
            run.error_message = f"Failed to queue task: {celery_err}"
            await db.commit()
            raise HTTPException(
                status_code=503, 
                detail=f"Background worker is unreachable (Redis timeout/connection error). Please try again in a few moments."
            )
        
        scheduling_msg = f" Scheduled every {request.interval_hours}h" if request.is_scheduled else ""
        return ScrapeResponse(
            message=f"SUCCESS: Scraping pipeline triggered. Processing in background...{scheduling_msg}",
            run_id=run.id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scrape request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-search-links", response_model=SaveSearchLinksResponse)
async def save_search_links(
    request: SaveSearchLinksRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save search URLs permanently for automated scheduled pipeline runs.
    Accepts all platform types. LinkedIn links benefit from 
    authenticated browser sessions for personalized results.
    """
    if not request.links:
        raise HTTPException(status_code=400, detail="No links provided")

    saved_count = 0
    linkedin_indeed_count = 0
    other_platforms = []

    for url in request.links:
        if not url.strip():
            continue

        platform = detect_platform(url)

        # Check if link already exists for this user
        existing = await db.execute(
            select(Link).where(
                Link.user_id == current_user.id,
                Link.url == url.strip()
            )
        )
        if not existing.scalar_one_or_none():
            link = Link(
                user_id=current_user.id,
                url=url.strip(),
                platform=platform.lower() if platform else "generic",
                is_active=True
            )
            db.add(link)
            saved_count += 1
            
            # Track which platforms were saved
            if platform.lower() in ["linkedin", "indeed"]:
                linkedin_indeed_count += 1
            else:
                other_platforms.append(platform.lower() if platform else "generic")

    if saved_count > 0:
        await db.commit()

    unique_other_platforms = list(set(other_platforms))
    
    logger.info(
        f"[save-search-links] User {current_user.id}: "
        f"saved {saved_count} links ({linkedin_indeed_count} LinkedIn/Indeed, {len(unique_other_platforms)} other platforms)"
    )

    message = f"Saved {saved_count} search link"
    if saved_count != 1:
        message += "s"
    message += " for automated runs."
    
    if linkedin_indeed_count > 0 and len(unique_other_platforms) > 0:
        message += f" LinkedIn/Indeed links will use your authenticated session."
    elif len(unique_other_platforms) > 0:
        message += f" Authenticate LinkedIn/Indeed to enable personalized results."

    return SaveSearchLinksResponse(
        message=message,
        saved_count=saved_count,
        skipped_count=0,
        skipped_platforms=[]
    )


@router.get("/search-links", response_model=list[SavedLinkResponse])
async def get_search_links(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all saved search URLs for the current user.
    These are used by the scheduled pipeline runs.
    """
    result = await db.execute(
        select(Link).where(
            Link.user_id == current_user.id,
            Link.is_active == True
        ).order_by(Link.created_at.desc())
    )
    links = result.scalars().all()

    return [
        SavedLinkResponse(
            id=link.id,
            url=link.url,
            platform=link.platform,
            created_at=link.created_at.isoformat()
        )
        for link in links
    ]


@router.delete("/search-links/{link_id}")
async def delete_search_link(
    link_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a saved search URL."""
    result = await db.execute(
        select(Link).where(
            Link.id == link_id,
            Link.user_id == current_user.id
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    link.is_active = False
    await db.commit()

    logger.info(f"[delete-search-link] User {current_user.id} deleted link {link_id}")

    return {"message": "Search link removed from automated runs"}
