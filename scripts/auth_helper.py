"""
Browser session authentication helper.
Opens a browser for user to log into LinkedIn and saves the session.
"""
import asyncio
import os
import sys
import json
import argparse
import time
from pathlib import Path

# ── Fix 1: Force UTF-8 on Windows console before anything else ──────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
# ─────────────────────────────────────────────────────────────────────────────

from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from dotenv import load_dotenv
import logging

from core.console import ColorFormatter, print_status

# Add project root to Python path so we can import db module
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ── Fix 2: Load .env from project root explicitly ────────────────────────────
# The script lives in scripts/, but .env is at the project root.
# Passing the explicit path ensures it's always found regardless of cwd.
load_dotenv(dotenv_path=os.path.join(project_root, ".env"))
# ─────────────────────────────────────────────────────────────────────────────

# Setup logging to file - do this FIRST before any other operations
log_path = "data/auth_helper.log"
os.makedirs("data", exist_ok=True)

# Force recreate basicConfig with proper handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# ── Fix 1 (cont): UTF-8 StreamHandler for browser-session output ────────────
_file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
_stream_handler = logging.StreamHandler(stream=sys.stdout)
_stream_handler.setFormatter(ColorFormatter())

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[_file_handler, _stream_handler],
    force=True
)
logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────────

# Log startup
logger.info("="*70)
logger.info("auth_helper.py STARTED")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Project root: {project_root}")
logger.info("="*70)


def _build_db_url() -> str:
    """
    Return a usable async DATABASE_URL for the local host.
    - Ensures the asyncpg driver prefix is present.
    - Replaces the Docker service hostname 'db' with 'localhost' so the
      script can reach Postgres when run directly on the host machine.
    """
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return url
    # Normalise driver prefix
    url = url.replace("postgres://", "postgresql+asyncpg://")
    url = url.replace("postgresql://", "postgresql+asyncpg://")
    # Replace Docker-internal hostname with localhost
    if "@db:" in url:
        url = url.replace("@db:", "@localhost:")
    return url


async def get_existing_session(user_id: str):
    """Check if user already has a saved browser session in the database."""
    logger.debug(f"Checking for existing session for user {user_id}")
    database_url = _build_db_url()

    if not database_url:
        logger.warning("DATABASE_URL not set")
        return None

    engine = None
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
                logger.info(f"Found existing session for user {user_id}")
                return settings.browser_session
            logger.debug(f"No existing session found for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"Failed to check existing session: {e}", exc_info=True)
        print_status("WARN", f"Failed to check existing session: {e}", "yellow")
        return None
    finally:
        if engine is not None:
            await engine.dispose()


async def save_to_database(user_id: str, storage_state: dict):
    """Save browser session to database for the user."""
    logger.debug(f"Saving session to database for user {user_id}")
    database_url = _build_db_url()

    if not database_url:
        logger.error("DATABASE_URL not set in environment")
        print_status("ERROR", "DATABASE_URL not set in environment", "red")
        return False

    engine = None
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
                user = User(
                    id=user_id,
                    email=f"user_{user_id}@job-finder.local",
                    hashed_password="",
                    is_active=True
                )
                session.add(user)
                await session.flush()

            # Get or create user settings
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()

            if not settings:
                logger.debug(f"Creating new UserSettings for {user_id}")
                settings = UserSettings(user_id=user_id)
                session.add(settings)

            settings.browser_session = storage_state
            await session.commit()

            logger.info(f"Browser session saved to database for user {user_id}")
            print_status("OK", f"Browser session saved to database for user {user_id}", "green")
            return True
    except Exception as e:
        logger.error(f"Failed to save to database: {e}", exc_info=True)
        print_status("ERROR", f"Failed to save to database: {e}", "red")
        return False
    finally:
        if engine is not None:
            await engine.dispose()


async def check_linkedin_authenticated(page):
    """Check if user is authenticated on LinkedIn by looking for profile indicator."""
    try:
        await asyncio.sleep(1)
        current_url = page.url

        if "linkedin.com/login" not in current_url and "linkedin.com" in current_url:
            logger.info(f"LinkedIn navigation detected: {current_url}")
            return True

        try:
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

async def check_linkedin_verification_challenge(page) -> bool:
    """Detect if LinkedIn is showing a mobile app verification challenge."""
    try:
        body_text = await page.inner_text("body")
        challenge_phrases = [
            "Check your LinkedIn app",
            "We sent a notification to your signed in devices",
            "Open your LinkedIn app and tap Yes",
            "Verify using SMS",
        ]
        return any(phrase in body_text for phrase in challenge_phrases)
    except Exception:
        return False

async def check_indeed_authenticated(page):
    """Check if user is authenticated on Indeed."""
    try:
        await asyncio.sleep(1)
        current_url = page.url

        if "/login" not in current_url and "indeed.com" in current_url:
            try:
                has_account_nav = await page.query_selector('[data-testid="AccountNav-AccountDropdown"]') is not None
                has_profile_btn = await page.query_selector('a[href*="/myjobs"], button[aria-label*="Account"]') is not None
                if has_account_nav or has_profile_btn:
                    logger.info("Indeed: Found account/profile indicators")
                    return True
            except:
                pass

            if "/jobs" in current_url:
                logger.info(f"Indeed job search view detected: {current_url}")
                return True

        return False
    except Exception as e:
        logger.debug(f"Indeed auth check error: {e}")
        return False


async def run(platforms: list | None = None, user_id: str | None = None):
    """
    Launch browser for user to login to job platforms.
    Auto-detects successful login and saves session for authenticated platforms only.

    Args:
        platforms: List of platforms to login to (default: ["linkedin", "indeed"])
        user_id: User ID for database storage (if provided, saves to DB instead of file)
    """
    try:
        if platforms is None:
            platforms = ["linkedin", "indeed"]

        logger.info(f"=== Starting authentication for user {user_id} ===")
        logger.info(f"Platforms: {platforms}")

        print("\n" + "="*60)
        print_status("INFO", "JOB FINDER - BROWSER SESSION AUTHENTICATION", "blue")
        print("="*60)
        print_status("INFO", f"Platforms: {', '.join(p.upper() for p in platforms)}", "blue")
        print_status("INFO", f"Storage: {'Database' if user_id else 'Local File'}", "blue")

        if user_id:
            print_status("INFO", f"User ID: {user_id}", "blue")

        # Check if user already has a saved session
        existing_session = None
        if user_id:
            print_status("INFO", "Checking for existing browser session...", "blue")
            logger.info(f"Checking for existing session for user {user_id}")
            existing_session = await get_existing_session(user_id)

            if existing_session:
                cookies = existing_session.get("cookies", [])
                has_linkedin = any("linkedin" in c.get("domain", "").lower() for c in cookies)
                has_indeed = any("indeed" in c.get("domain", "").lower() for c in cookies)

                missing_platforms = []
                if "linkedin" in platforms and not has_linkedin:
                    missing_platforms.append("linkedin")
                if "indeed" in platforms and not has_indeed:
                    missing_platforms.append("indeed")

                if not missing_platforms:
                    print_status("OK", "Browser session already saved for all requested platforms!", "green")
                    print("\n" + "-"*60)
                    print_status("INFO", "EXISTING SESSION FULLY MATCHES REQUEST", "blue")
                    print("-"*60)
                    print_status("INFO", "Your browser session is already saved for:", "blue")
                    for p in platforms:
                        print(f"  - {p.title()}")
                    print_status("INFO", "You don't need to log in again. Use 'Clear Saved Session' if you want to force re-authentication.", "blue")
                    print("="*60 + "\n")
                    logger.info("Returning early - existing session fully covers requested platforms")
                    return True
                else:
                    print_status("INFO", f"Found session, but missing cookies for: {', '.join(missing_platforms).title()}", "blue")
                    platforms = missing_platforms

        print_status("INFO", "Simply log in to the platforms in the browser tabs", "blue")
        print_status("INFO", "Authentication will be detected automatically", "blue")
        print_status("INFO", "Session will be saved when you're done", "blue")
        logger.info("Opening browser for new authentication")

        os.makedirs("data", exist_ok=True)

        async with async_playwright() as p:
            logger.info("Launching Chromium browser...")
            print_status("INFO", "Launching browser...", "blue")

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
            logger.info("Browser launched successfully")

            context_args = {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
                "timezone_id": "UTC",
                "extra_http_headers": {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            }
            if existing_session is not None:
                context_args["storage_state"] = existing_session
                logger.info("Injecting existing session state into new browser context")

            context = await browser.new_context(**context_args)
            logger.info("Browser context created")

            pages = {}
            authenticated = {}

            if "linkedin" in platforms:
                print_status("INFO", "Opening LinkedIn login page...", "blue")
                logger.info("Opening LinkedIn login page")
                page = await context.new_page()
                await page.goto("https://www.linkedin.com/login", wait_until="load")
                pages["linkedin"] = page
                authenticated["linkedin"] = False
                logger.info("LinkedIn page loaded")

            if "indeed" in platforms:
                print_status("INFO", "Opening Indeed login page...", "blue")
                logger.info("Opening Indeed login page")
                page = await context.new_page()
                await page.goto("https://in.indeed.com/", wait_until="load")
                pages["indeed"] = page
                authenticated["indeed"] = False
                logger.info("Indeed page loaded")

            print("\n" + "-"*60)
            print_status("INFO", "Waiting for login... (auto-detecting)", "blue")
            print("-"*60)

            max_wait = 300  # 5 minutes
            elapsed = 0
            check_interval = 2

            while elapsed < max_wait:
                if "linkedin" in pages and not authenticated["linkedin"]:
                    if await check_linkedin_verification_challenge(pages["linkedin"]):
                        print_status("WARN", "LINKEDIN MOBILE VERIFICATION REQUIRED", "yellow")
                        print_status("WARN", "LinkedIn has sent a push notification to your phone.", "yellow")
                        print_status("WARN", "Open your LinkedIn app and tap 'Yes' to approve.", "yellow")
                        print_status("WARN", "The session will be saved automatically once confirmed.", "yellow")
                        logger.warning("LinkedIn mobile verification challenge detected — waiting for user approval")
                        # Hold the browser open and keep polling; do NOT mark as authenticated yet
                    elif await check_linkedin_authenticated(pages["linkedin"]):
                        authenticated["linkedin"] = True
                        print_status("OK", "LinkedIn: Successfully authenticated!", "green")
                        logger.info("LinkedIn authentication detected")
                        # Extra 15s buffer so all session cookies fully settle
                        print_status("INFO", "Holding session open for 15 seconds to let cookies settle...", "blue")
                        logger.info("Holding browser open 15s post-auth for cookie stabilisation")
                        await asyncio.sleep(15)
                        print_status("OK", "Session capture window closed.", "green")
                        
                if "indeed" in pages and not authenticated["indeed"]:
                    if await check_indeed_authenticated(pages["indeed"]):
                        authenticated["indeed"] = True
                        print_status("OK", "Indeed: Successfully authenticated!", "green")
                        logger.info("Indeed authentication detected")

                all_platforms_done = all(
                    authenticated.get(platform, False) for platform in pages.keys()
                )
                if all_platforms_done and len(pages) > 0:
                    print_status("OK", "All platforms authenticated! Saving session...", "green")
                    logger.info("All platforms authenticated, proceeding with session save")
                    await asyncio.sleep(1)
                    break

                elapsed += check_interval
                await asyncio.sleep(check_interval)

                if elapsed % 30 == 0 and elapsed > 0:
                    status = ", ".join([f"{p}: {'authenticated' if authenticated.get(p) else 'waiting'}"
                                       for p in pages.keys()])
                    print_status("INFO", status, "blue")
                    logger.debug(f"Auth status: {status}")

            try:
                print_status("INFO", "Capturing browser session...", "blue")
                logger.info("Capturing session state...")
                storage_state_dict = await context.storage_state()

                if not storage_state_dict:
                    logger.warning("Session state is empty!")
                    print_status("WARN", "Warning: Session state is empty", "yellow")
                else:
                    cookies = len(storage_state_dict.get("cookies", []))
                    origins = len(storage_state_dict.get("origins", []))
                    msg = f"Captured: {cookies} cookies, {origins} origins"
                    print_status("INFO", msg, "blue")
                    logger.info(msg)

                    auth_status = "Authenticated: " + ", ".join(
                        p.upper() for p in pages.keys() if authenticated.get(p)
                    )
                    print_status("OK", auth_status, "green")
                    logger.info(auth_status)

                if user_id:
                    logger.info(f"Saving to database for {user_id}...")
                    success = await save_to_database(user_id, storage_state_dict)
                    if success:
                        logger.info("Saved to database successfully")
                    else:
                        print_status("INFO", "Saving to local file as fallback...", "blue")
                        with open("data/browser_state.json", "w", encoding="utf-8") as f:
                            json.dump(storage_state_dict, f, indent=2)
                        logger.info("Saved to local file")
                else:
                    with open("data/browser_state.json", "w", encoding="utf-8") as f:
                        json.dump(storage_state_dict, f, indent=2)
                    logger.info("Saved to local file")

            except Exception as e:
                logger.error(f"Error saving session: {e}", exc_info=True)
                print_status("ERROR", f"Error: {e}", "red")
                raise

            await browser.close()
            logger.info("Browser closed")
            print_status("OK", "Done! Session is ready.", "green")
            print("="*60 + "\n")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print_status("ERROR", f"ERROR: {e}", "red")
        raise


def main():
    try:
        logger.info("=== MAIN STARTED ===")
        parser = argparse.ArgumentParser(description="Authenticate with job platforms")
        parser.add_argument("--platforms", nargs="+", default=["linkedin", "indeed"],
                          choices=["linkedin", "indeed"])
        parser.add_argument("--user-id", type=str, help="User ID for database storage")

        args = parser.parse_args()
        logger.info(f"Args: platforms={args.platforms}, user_id={args.user_id}")

        asyncio.run(run(platforms=args.platforms, user_id=args.user_id))
        logger.info("Success")

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        print_status("WARN", "Cancelled.", "yellow")
    except Exception as e:
        logger.error(f"CRITICAL: {e}", exc_info=True)
        print_status("ERROR", f"Error: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Top-level error: {e}", exc_info=True)
        sys.exit(1)