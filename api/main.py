from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from api.auth.router import router as auth_router
from api.users.router import router as users_router
from api.jobs.router import router as jobs_router
from api.scrapers.router import router as scrapers_router
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage app lifecycle - start scheduler on startup, recover missed scheduled pipelines, stop on shutdown.
    """
    global scheduler_task
    
    try:
        # Startup
        logger.info("[Lifespan] ============ Starting API Lifespan ============")
        from scheduler.scheduler import scheduler, _check_and_reschedule_pipelines, _recover_scheduled_pipelines
        
        logger.info("[Lifespan] Imported scheduler successfully")
        logger.info("[Lifespan] Starting scheduler...")
        scheduler.start()
        logger.info("[Lifespan] Scheduler started successfully")
        
        # Recover any pipelines that should have been rescheduled while app was offline
        logger.info("[Lifespan] Running recovery check for missed scheduled pipelines...")
        try:
            await _recover_scheduled_pipelines()
            logger.info("[Lifespan] Recovery check completed")
        except Exception as e:
            logger.error(f"[Lifespan] Error during recovery: {e}", exc_info=True)
        
        # Schedule the check-and-reschedule job to run every 1 minute
        from apscheduler.triggers.interval import IntervalTrigger
        logger.info("[Lifespan] Adding check-and-reschedule job to scheduler...")
        scheduler.add_job(
            _check_and_reschedule_pipelines,
            trigger=IntervalTrigger(minutes=1),
            id="check_reschedule_pipelines",
            replace_existing=True,
            name="Check and reschedule pipelines"
        )
        logger.info("[Lifespan] Scheduler configured with 1-minute check interval")
        logger.info("[Lifespan] ============ API Lifespan Startup Complete ============")
    except Exception as e:
        logger.error(f"[Lifespan] CRITICAL ERROR during startup: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("[Lifespan] ============ Shutting down API Lifespan ============")
    try:
        scheduler.shutdown()
        logger.info("[Lifespan] Scheduler shut down successfully")
    except Exception as e:
        logger.error(f"[Lifespan] Error during shutdown: {e}", exc_info=True)
    logger.info("[Lifespan] ============ API Lifespan Shutdown Complete ============")


app = FastAPI(
    title="Agentic Job Finder API",
    description="Backend API",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(jobs_router)
app.include_router(scrapers_router)

@app.get("/debug/env")
async def debug_env():
    import os
    s = os.environ.get("JWT_SECRET_KEY", "MISSING")
    masked_s = f"{s[0]}...{s[-1]}" if len(s) > 2 else s
    return {
        "REDIS_URL": os.environ.get("REDIS_URL"), 
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "JWT_SECRET_KEY_MASKED": masked_s
    }

@app.get("/")
async def root():
    return {
        "message": "Get a job.",
        "docs": "/docs",
        "status": "online"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
