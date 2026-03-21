import asyncio
import os
import sys
from sqlalchemy import delete
from dotenv import load_dotenv

sys.path.append(os.getcwd())

from db.base import AsyncSessionLocal, engine
from db.models import JobResult, PipelineRun

async def cleanup_db():
    print("🧹 Starting Database Cleanup...")
    load_dotenv()
    
    async with AsyncSessionLocal() as db:
        try:
            # Delete Job Results
            print("Deleting Job Results...")
            await db.execute(delete(JobResult))
            
            # Delete Pipeline Runs
            print("Deleting Pipeline Runs...")
            await db.execute(delete(PipelineRun))
            
            await db.commit()
            print("✅ Database tables cleared successfully.")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error during cleanup: {e}")

    seen_jobs_path = os.path.join(os.getcwd(), "data", "seen_jobs.json")
    if os.path.exists(seen_jobs_path):
        try:
            os.remove(seen_jobs_path)
            print("✅ Removed seen_jobs.json cache.")
        except Exception as e:
            print(f"⚠️ Could not remove seen_jobs.json: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_db())
