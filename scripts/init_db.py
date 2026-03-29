#!/usr/bin/env python
"""
Database initialization script - runs before API startup
"""
import asyncio
import time
import sys
import os
import logging

# Add parent directory to path so we can import from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_database():
    """Initialize database tables"""
    try:
        from db.base import init_db
        logger.info("🔧 Initializing database tables...")
        await init_db()
        logger.info("✅ Database tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def wait_for_db():
    """Wait for database to be ready with retry logic"""
    from db.base import engine
    from sqlalchemy import text
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
            return True
        except Exception as e:
            retry_count += 1
            wait_time = min(retry_count, 10)
            logger.warning(f"⏳ Database not ready ({retry_count}/{max_retries}), retrying in {wait_time}s: {e}")
            await asyncio.sleep(wait_time)
    
    logger.error("❌ Failed to connect to database after maximum retries")
    return False

async def main():
    logger.info("🚀 Starting database pre-initialization...")
    
    # Wait for database to be available
    if not await wait_for_db():
        sys.exit(1)
    
    # Initialize database tables
    if not await init_database():
        sys.exit(1)
    
    logger.info("✅ Pre-initialization complete, API ready to start")

if __name__ == "__main__":
    asyncio.run(main())
