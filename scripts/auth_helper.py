"""
Browser session authentication helper.
Opens a browser for user to log into LinkedIn/Wellfound and saves the session.
"""
import asyncio
import os
import sys
import json
import argparse
import time
from pathlib import Path
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from dotenv import load_dotenv
import logging

# Add project root to Python path so we can import db module
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Setup logging to file - do this FIRST before any other operations
log_path = "data/auth_helper.log"
os.makedirs("data", exist_ok=True)

# Force recreate basicConfig with proper handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, mode='a'),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("="*70)
logger.info("auth_helper.py STARTED")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Project root: {project_root}")
logger.info("="*70)


async def get_existing_session(user_id: str):
    """Check if user already has a saved browser session in the database."""
    logger.debug(f"Checking for existing session for user {user_id}")
    database_url = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")
    
    # When running locally on host machine, replace Docker hostname with localhost
    if "localhost" not in database_url:
        database_url = database_url.replace("@db:", "@localhost:")
    
    if not database_url:
        logger.warning("DATABASE_URL not set")
        return None
    
    try:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with async_session() as session:
            from db.models import UserSettings
            
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            
            if settings and settings.browser_session:
                logger.info(f"✓ Found existing session for user {user_id}")
                return settings.browser_session
            logger.debug(f"No existing session found for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"Failed to check existing session: {e}", exc_info=True)
        print(f"⚠️  Failed to check existing session: {e}")
        return None
    finally:
        await engine.dispose()


async def save_to_database(user_id: str, storage_state: dict):
    """Save browser session to database for the user."""
    logger.debug(f"Saving session to database for user {user_id}")
    database_url = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")
    
    # When running locally on host machine, replace Docker hostname with localhost
    if "localhost" not in database_url:
        database_url = database_url.replace("@db:", "@localhost:")
    
    if not database_url:
        logger.error("DATABASE_URL not set in environment")
        print("❌ DATABASE_URL not set in environment")
        return False
    
    try:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with async_session() as session:
            from db.models import User, UserSettings
            
            # First, ensure the user exists (required for foreign key)
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.debug(f"Creating new User record for {user_id}")
                # Create a user record if it doesn't exist
                user = User(
                    id=user_id,
                    email=f"user_{user_id}@job-finder.local",  # Temporary email
                    hashed_password="",  # No password for session-only auth
                    is_active=True
                )
                session.add(user)
                await session.flush()  # Flush to ensure user is created before settings
            
            # Get or create user settings
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            
            if not settings:
                logger.debug(f"Creating new UserSettings for {user_id}")
                settings = UserSettings(user_id=user_id)
                session.add(settings)
            
            # Save browser session
            settings.browser_session = storage_state
            await session.commit()
            
            logger.info(f"✓ Browser session saved to database for user {user_id}")
            print(f"✓ Browser session saved to database for user {user_id}")
            return True
    except Exception as e:
        logger.error(f"Failed to save to database: {e}", exc_info=True)
        print(f"❌ Failed to save to database: {e}")
        return False
    finally:
        await engine.dispose()


async def check_linkedin_authenticated(page):
    """Check if user is authenticated on LinkedIn by looking for profile indicator."""
    try:
        # Wait briefly for any navigation to complete
        await asyncio.sleep(1)
        current_url = page.url
        
        # Check if we're past the login page
        if "linkedin.com/login" not in current_url and "linkedin.com" in current_url:
            logger.info(f"LinkedIn navigation detected: {current_url}")
            return True
        
        # Also check for the presence of profile/feed indicators
        try:
            # Look for feed element or profile picture (indicators of successful login)
            has_feed = await page.query_selector('[data-test-id="feed"]') is not None
            has_profile = await page.query_selector('img[alt*="member profile"]') is not None
            if has_feed or has_profile:
                logger.info("LinkedIn: Found feed/profile indicators")
                return True
        except:
            pass
        
        return False
    except Exception as e:
        logger.debug(f"LinkedIn auth check error: {e}")
        return False


async def check_wellfound_authenticated(page):
    """Check if user is authenticated on Wellfound."""
    try:
        await asyncio.sleep(1)
        current_url = page.url
        
        # Check if we're past the login page
        if "wellfound.com/login" not in current_url and "wellfound.com" in current_url:
            logger.info(f"Wellfound navigation detected: {current_url}")
            return True
        
        return False
    except Exception as e:
        logger.debug(f"Wellfound auth check error: {e}")
        return False


async def run(platforms: list = None, user_id: str = None):
    """
    Launch browser for user to login to job platforms.
    Auto-detects successful login and saves session for authenticated platforms only.
    
    Args:
        platforms: List of platforms to login to (default: ["linkedin", "wellfound"])
        user_id: User ID for database storage (if provided, saves to DB instead of file)
    """
    try:
        if platforms is None:
            platforms = ["linkedin", "wellfound"]
        
        logger.info(f"=== Starting authentication for user {user_id} ===")
        logger.info(f"Platforms: {platforms}")
        
        print("\n" + "="*60)
        print("  JOB FINDER - BROWSER SESSION AUTHENTICATION")
        print("="*60)
        print(f"\nPlatforms: {', '.join(p.upper() for p in platforms)}")
        print(f"Storage: {'Database' if user_id else 'Local File'}")
        
        if user_id:
            print(f"User ID: {user_id}")
        
        # Check if user already has a saved session
        if user_id:
            print("\n🔍 Checking for existing browser session...")
            logger.info(f"Checking for existing session for user {user_id}")
            existing_session = await get_existing_session(user_id)
            
            if existing_session:
                print("✓ Browser session already saved for this user!")
                print("\n" + "-"*60)
                print("  EXISTING SESSION FOUND")
                print("-"*60)
                print("Your browser session is already saved and will be used for:")
                print("• LinkedIn scraping")
                print("• Wellfound scraping")
                print("\nYou don't need to log in again.")
                print("="*60 + "\n")
                logger.info("Returning early - existing session found")
                return True
        
        print("\n✓ Simply log in to the platforms in the browser tabs")
        print("✓ Authentication will be detected automatically")
        print("✓ Session will be saved when you're done\n")
        logger.info("Opening browser for new authentication")

        os.makedirs("data", exist_ok=True)

        async with async_playwright() as p:
            logger.info("Launching Chromium browser...")
            print("📶 Launching browser...")
            
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--hide-scrollbars",
                    "--disable-web-resources",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-site-isolation-trials",
                ],
            )
            logger.info("✓ Browser launched successfully")
            
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="UTC",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            logger.info("✓ Browser context created")
            
            pages = {}
            authenticated = {}

            if "linkedin" in platforms:
                print("📖 Opening LinkedIn login page...")
                logger.info("Opening LinkedIn login page")
                page = await context.new_page()
                await page.goto("https://www.linkedin.com/login", wait_until="load")
                pages["linkedin"] = page
                authenticated["linkedin"] = False
                logger.info("✓ LinkedIn page loaded")

            if "wellfound" in platforms:
                print("📖 Opening Wellfound login page...")
                logger.info("Opening Wellfound login page")
                page = await context.new_page()
                await page.goto("https://wellfound.com/login", wait_until="load")
                pages["wellfound"] = page
                authenticated["wellfound"] = False
                logger.info("✓ Wellfound page loaded")

            print("\n" + "-"*60)
            print("  Waiting for login... (auto-detecting)")
            print("-"*60)
            
            # Monitor for successful authentication
            max_wait = 300  # 5 minutes
            elapsed = 0
            check_interval = 2  # Check every 2 seconds
            
            while elapsed < max_wait:
                # Check LinkedIn
                if "linkedin" in pages and not authenticated["linkedin"]:
                    if await check_linkedin_authenticated(pages["linkedin"]):
                        authenticated["linkedin"] = True
                        print("✅ LinkedIn: Successfully authenticated!")
                        logger.info("LinkedIn authentication detected")
                
                # Check Wellfound
                if "wellfound" in pages and not authenticated["wellfound"]:
                    if await check_wellfound_authenticated(pages["wellfound"]):
                        authenticated["wellfound"] = True
                        print("✅ Wellfound: Successfully authenticated!")
                        logger.info("Wellfound authentication detected")
                
                # If all required platforms are authenticated, we can exit
                all_platforms_done = all(
                    authenticated.get(platform, False) for platform in pages.keys()
                )
                if all_platforms_done and len(pages) > 0:
                    print("\n✓ All platforms authenticated! Saving session...")
                    logger.info("All platforms authenticated, proceeding with session save")
                    await asyncio.sleep(1)
                    break
                
                elapsed += check_interval
                await asyncio.sleep(check_interval)
                
                if elapsed % 30 == 0 and elapsed > 0:
                    status = ", ".join([f"{p}: {'✓' if authenticated.get(p) else '⏳'}" 
                                       for p in pages.keys()])
                    print(f"⏱️  {status}")
                    logger.debug(f"Auth status: {status}")

            try:
                print("📝 Capturing browser session...")
                logger.info("Capturing session state...")
                storage_state_dict = await context.storage_state()
                
                if not storage_state_dict:
                    logger.warning("Session state is empty!")
                    print("⚠️  Warning: Session state is empty")
                else:
                    cookies = len(storage_state_dict.get("cookies", []))
                    origins = len(storage_state_dict.get("origins", []))
                    msg = f"📊 Captured: {cookies} cookies, {origins} origins"
                    print(msg)
                    logger.info(msg)
                    
                    # Log which platforms are authenticated
                    auth_status = "Authenticated: " + ", ".join(
                        p.upper() for p in pages.keys() if authenticated.get(p)
                    )
                    print(f"✓ {auth_status}")
                    logger.info(auth_status)
                
                if user_id:
                    logger.info(f"Saving to database for {user_id}...")
                    success = await save_to_database(user_id, storage_state_dict)
                    if success:
                        logger.info("✓ Saved to database successfully")
                    else:
                        print("Saving to local file as fallback...")
                        with open("data/browser_state.json", "w") as f:
                            json.dump(storage_state_dict, f, indent=2)
                        logger.info("Saved to local file")
                else:
                    with open("data/browser_state.json", "w") as f:
                        json.dump(storage_state_dict, f, indent=2)
                    logger.info("Saved to local file")
                    
            except Exception as e:
                logger.error(f"Error saving session: {e}", exc_info=True)
                print(f"❌ Error: {e}")
                raise
            
            await browser.close()
            logger.info("✓ Browser closed")
            print("\n✓ Done! Session is ready.")
            print("="*60 + "\n")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"❌ ERROR: {e}")
        raise


def main():
    try:
        logger.info("=== MAIN STARTED ===")
        parser = argparse.ArgumentParser(description="Authenticate with job platforms")
        parser.add_argument("--platforms", nargs="+", default=["linkedin", "wellfound"],
                          choices=["linkedin", "wellfound"])
        parser.add_argument("--user-id", type=str, help="User ID for database storage")
        
        args = parser.parse_args()
        logger.info(f"Args: platforms={args.platforms}, user_id={args.user_id}")
        
        asyncio.run(run(platforms=args.platforms, user_id=args.user_id))
        logger.info("✓ Success")
        
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        print("\n⚠️  Cancelled.")
    except Exception as e:
        logger.error(f"CRITICAL: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Top-level error: {e}", exc_info=True)
        sys.exit(1)
