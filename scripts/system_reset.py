import os
import asyncio
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from db.models import PipelineRun, JobResult
from workers.worker import celery_app
from dotenv import load_dotenv

load_dotenv()

async def reset_system():
    print("--- Starting System Reset ---")
    
    # Purge Celery Queue
    try:
        print("Purging Celery queue...")
        purged = celery_app.control.purge()
        print(f"  Done. Purged {purged} messages.")
    except Exception as e:
        print(f"  Warning: Could not purge Celery: {e}")

    # Update Database
    db_url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with SessionLocal() as db:
        print("Cleaning up Database Pipeline Runs...")
        try:
            # Delete JobResults first
            await db.execute(delete(JobResult))
            # Delete PipelineRuns
            res = await db.execute(delete(PipelineRun))
            await db.commit()
            print(f"  Done. Deleted {res.rowcount} PipelineRun records and ALL JobResults.")
        except Exception as e:
            await db.rollback()
            print(f"  Error cleaning database: {e}")

    await engine.dispose()
    print("\n--- Reset Complete! ---")
    print("Recommendation: Now run 'pkill -f celery' and restart your worker.")

if __name__ == "__main__":
    asyncio.run(reset_system())
