#!/usr/bin/env python
"""Manual scheduler check and reschedule for overdue pipelines"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://harsh:Harsh%40%241711@localhost:5432/job_agent")

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime, timedelta
from db.models import PipelineRun, Base
import uuid

DATABASE_URL = os.environ["DATABASE_URL"]

async def check_and_reschedule_manual():
    """Manually check and reschedule overdue pipelines"""
    engine = create_async_engine(DATABASE_URL)
    
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        result = await db.execute(
            select(PipelineRun).where(
                and_(
                    PipelineRun.is_scheduled == True,
                    or_(
                        PipelineRun.status == "done",
                        PipelineRun.status == "running"
                    ),
                    PipelineRun.completed_at.isnot(None)
                )
            )
        )
        scheduled_runs = result.scalars().all()
        
        print(f"✓ Found {len(scheduled_runs)} scheduled pipeline(s)\n")
        
        rescheduled_count = 0
        for run in scheduled_runs:
            next_execution = run.completed_at + timedelta(hours=run.interval_hours)
            time_since_completion = datetime.utcnow() - run.completed_at
            time_until_next = next_execution - datetime.utcnow()
            
            print(f"Pipeline: {run.id}")
            print(f"  Status: {run.status}")
            print(f"  Completed: {run.completed_at}")
            print(f"  Time since: {str(time_since_completion).split('.')[0]}")
            print(f"  Interval: {run.interval_hours}h")
            print(f"  Next due: {next_execution}")
            
            if next_execution <= datetime.utcnow():
                print(f"  ⏰ OVERDUE by: {str(-time_until_next).split('.')[0]}")
                print(f"  ➜ RESCHEDULING...")
                
                # Reset for next execution
                run.status = "pending"
                run.execution_count = run.execution_count + 1
                run.started_at = datetime.utcnow()
                run.completed_at = None
                run.celery_task_id = str(uuid.uuid4())
                run.error_message = None
                
                await db.commit()
                await db.refresh(run)
                
                print(f"  ✅ Rescheduled as execution #{run.execution_count}\n")
                rescheduled_count += 1
            else:
                print(f"  ⏳ Not yet due (in {str(time_until_next).split('.')[0]})\n")
        
        print(f"\n{'='*60}")
        print(f"Summary: Rescheduled {rescheduled_count} pipeline(s)")
        print(f"{'='*60}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_and_reschedule_manual())
