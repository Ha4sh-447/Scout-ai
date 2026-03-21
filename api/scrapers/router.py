import subprocess
import os
import sys
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from api.deps import get_current_user
from db.models import User
from api.scrapers.schemas import ScrapeRequest, ScrapeResponse
from scrapers.page_loader import load_job_pages
from tools.browser.browser_manager import BrowserManager
from db.base import get_db
from db.models import PipelineRun
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scrapers", tags=["scrapers"])

@router.post("/login/{platform}")
async def trigger_login(
    platform: str,
    current_user: User = Depends(get_current_user)
):
    """
    Triggers the authentication helper for a specific platform.
    Note: This will open a browser window ON THE SERVER/HOST.
    Only suitable for local development/testing.
    """
    if platform.lower() not in ["linkedin", "wellfound", "all"]:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    try:
        # Trigger the existing auth_helper script
        script_path = os.path.join(os.getcwd(), "scripts", "auth_helper.py")

        subprocess.Popen([sys.executable, script_path])
        
        return {"message": f"Login helper triggered for {platform}. Check the host machine for the browser window."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger login helper: {e}")


@router.post("/scrape", response_model=ScrapeResponse, status_code=202)
async def scrape_links(
    request: ScrapeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scrape a list of job links using the full background pipeline.
    Platforms are auto-detected.
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
            celery_task_id=celery_task_id
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
        
        return ScrapeResponse(
            message="SUCCESS: Scraping pipeline triggered. Processing in background...",
            run_id=run.id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scrape request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
