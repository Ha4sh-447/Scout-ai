import os
import sys
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("preflight")

def check_env_vars():
    """Verify all required environment variables are present."""
    required = [
        "MISTRAL_API_KEY",
        "DATABASE_URL",
        "QDRANT_URL",
    ]
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return False
    
    logger.info("✓ All required environment variables are present.")
    return True

def ensure_directories():
    """Ensure required data directories exist."""
    dirs = ["data", "data/resumes"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info("✓ Data directories verified.")
    return True

async def check_qdrant():
    """Verify connection to Qdrant."""
    q_url = os.getenv("QDRANT_URL")
    if not q_url:
        return False
    
    try:
        from qdrant_client import AsyncQdrantClient
        client = AsyncQdrantClient(url=q_url, api_key=os.getenv("QDRANT_API_KEY"))
        # Minimal check
        await client.get_collections()
        logger.info("✓ Qdrant connection successful.")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant at {q_url}: {e}")
        return False

async def check_postgres():
    """Verify connection to PostgreSQL."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return False
    
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("✓ PostgreSQL connection successful.")
        await engine.dispose()
        return True
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return False

def check_playwright():
    """Check if Playwright browsers are installed."""
    try:
        import playwright
        logger.info("✓ Playwright package found. (Note: Run 'playwright install chromium' if browser launch fails)")
        return True
    except ImportError:
        logger.error("Playwright package not found. Run 'pip install playwright'.")
        return False

async def run_all_checks():
    """Run all pre-flight checks."""
    load_dotenv()
    
    success = True
    success &= check_env_vars()
    success &= ensure_directories()
    success &= check_playwright()
    
    # Async checks
    success &= await check_qdrant()
    success &= await check_postgres()
    
    if success:
        logger.info("\n" + "="*40)
        logger.info("  PRE-FLIGHT CHECKS PASSED")
        logger.info("="*40 + "\n")
    else:
        logger.error("\n" + "!"*40)
        logger.error("  PRE-FLIGHT CHECKS FAILED")
        logger.error("  Please fix the issues above before running.")
        logger.error("!"*40 + "\n")
    
    return success

if __name__ == "__main__":
    is_ready = asyncio.run(run_all_checks())
    if not is_ready:
        sys.exit(1)
