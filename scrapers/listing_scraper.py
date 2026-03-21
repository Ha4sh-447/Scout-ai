"""
Platform-specific listing scrapers for LinkedIn, Indeed, and Glassdoor.

Extracts individual job cards from listing pages using CSS selectors.
Each card becomes a separate RawJobData object.
"""

import logging
import re

from playwright.async_api import Page

from models.jobs import RawJobData
from tools.browser.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

LINKEDIN_LISTING_RE = re.compile(r"https?://(www\.)?linkedin\.com/jobs/")
INDEED_LISTING_RE = re.compile(r"https?://(www\.|[a-z]{2}\.)?indeed\.(com|co\.\w+)")
GLASSDOOR_LISTING_RE = re.compile(r"https?://(www\.)?glassdoor\.(com|co\.\w+)")
WELLFOUND_LISTING_RE = re.compile(r"https?://(www\.)?wellfound\.com/")


def is_linkedin_listing(url: str) -> bool:
    return bool(LINKEDIN_LISTING_RE.match(url))


def is_indeed_listing(url: str) -> bool:
    return bool(INDEED_LISTING_RE.match(url))


def is_glassdoor_listing(url: str) -> bool:
    return bool(GLASSDOOR_LISTING_RE.match(url))


def is_wellfound_listing(url: str) -> bool:
    return bool(WELLFOUND_LISTING_RE.match(url))


def is_single_job_url(url: str) -> bool:
    """Check if the URL is an individual job posting (not a search/listing page)."""
    if "linkedin.com/jobs/view/" in url or "currentJobId=" in url:
        return True
    if "indeed" in url and ("viewjob" in url or "rc/clk" in url or "vjcmp" in url):
        return True
    if "glassdoor" in url and ("jobListing.htm" in url or "partner/jobListing.htm" in url):
        return True
    if "wellfound.com/jobs/" in url and any(char.isdigit() for char in url.split("/")[-1]):
        return True
    return False


def is_known_listing(url: str) -> bool:
    if is_single_job_url(url):
        return False
    return is_linkedin_listing(url) or is_indeed_listing(url) or is_glassdoor_listing(url) or is_wellfound_listing(url)


def _normalize_linkedin_url(url: str, query: str = "", freshness: str = "default") -> str:
    """
    Convert any LinkedIn jobs URL to the public guest search endpoint.
    Includes freshness filters: f_TPR=r604800 (past week), f_TPR=r86400 (past 24h)
    """
    freshness_map = {
        "past_week": "&f_TPR=r604800",
        "past_24h": "&f_TPR=r86400",
        "default": ""
    }
    suffix = freshness_map.get(freshness, "")

    if "/jobs/search/" in url and "keywords=" in url:
        # If it already has parameters, append the freshness if not present
        if "&f_TPR=" not in url:
            return url + suffix
        return url

    encoded = query.replace(" ", "+")
    return f"https://www.linkedin.com/jobs/search/?keywords={encoded}&location=India{suffix}"


def _normalize_indeed_url(url: str, query: str = "") -> str:
    """Convert Indeed homepage to a search URL if needed."""
    if "/jobs?" in url and "q=" in url:
        return url
    match = re.match(r"(https?://[^/]+)", url)
    domain = match.group(1) if match else "https://in.indeed.com"
    encoded = query.replace(" ", "+")
    return f"{domain}/jobs?q={encoded}"


def _normalize_glassdoor_url(url: str, query: str = "") -> str:
    """Convert Glassdoor index to a search URL if needed."""
    if "SRCH" in url or "jobs-SRCH" in url:
        return url
    match = re.match(r"(https?://[^/]+)", url)
    domain = match.group(1) if match else "https://www.glassdoor.co.in"
    encoded = query.replace(" ", "+")
    return f"{domain}/Job/jobs.htm?sc.keyword={encoded}"


def _normalize_wellfound_url(url: str, query: str = "", location: str = "") -> str:
    """
    Convert to Wellfound's role/location path format.
    Example: https://wellfound.com/role/l/ai-engineer/india
    """
    if "/role/" in url:
        return url
    
    def slugify(text: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

    role_slug = slugify(query or "software-engineer")
    loc_slug = slugify(location or "india")
    
    return f"https://wellfound.com/role/l/{role_slug}/{loc_slug}"


# ── Card extractors ──────────────────────────────────────────────────────────


async def _extract_linkedin_cards(page: Page, max_cards: int = 30) -> list[dict]:
    """Extract job cards from LinkedIn's public search page."""
    cards = await page.query_selector_all(".base-card")
    results = []

    for card in cards[:max_cards]:
        link_el = await card.query_selector("a")
        href = (await link_el.get_attribute("href")) if link_el else None
        
        raw_text = (await card.inner_text()).strip()
        
        # Try to find recency text (e.g. "2 hours ago", "1 day ago")
        posted_at_el = await card.query_selector(".job-search-card__listdate, .job-search-card__listdate--new, [datetime]")
        posted_at_text = (await posted_at_el.inner_text()).strip() if posted_at_el else None
        
        if href and raw_text:
            href = href.split("?")[0]
            results.append({
                "link": href, 
                "raw_text": raw_text,
                "posted_at_text": posted_at_text
            })

    return results


async def _extract_indeed_cards(page: Page, max_cards: int = 30) -> list[dict]:
    """Extract job cards from Indeed search results."""
    cards = await page.query_selector_all(".job_seen_beacon")
    results = []

    for card in cards[:max_cards]:
        link_el = (
            await card.query_selector(".jobTitle a")
            or await card.query_selector("a[data-jk]")
        )

        href = (await link_el.get_attribute("href")) if link_el else None

        if href and href.startswith("/"):
            base = await page.evaluate("window.location.origin")
            href = base + href
            
        raw_text = (await card.inner_text()).strip()
        
        # Try to find recency text on Indeed
        posted_at_el = await card.query_selector(".date, .myJobsState, [class*='date'], [class*='Date']")
        posted_at_text = (await posted_at_el.inner_text()).strip() if posted_at_el else None

        if href and raw_text:
            results.append({
                "link": href, 
                "raw_text": raw_text,
                "posted_at_text": posted_at_text
            })

    return results


async def _extract_wellfound_cards(page: Page, max_cards: int = 30) -> list[dict]:
    """Extract job cards from Wellfound's search results."""
    # Wellfound uses company-grouped results
    cards = await page.query_selector_all('[data-test="StartupResult"]')
    results = []

    for card in cards:
        if len(results) >= max_cards:
            break

        # Each company card can have multiple jobs
        job_rows = await card.query_selector_all('div.flex.flex-col.py-4, [class*="jobListing"]')
        
        for row in job_rows:
            if len(results) >= max_cards:
                break
                
            link_el = await row.query_selector('a[href*="/jobs/"]')
            if not link_el:
                continue
                
            href = await link_el.get_attribute("href")
            if href.startswith("/"):
                base = await page.evaluate("window.location.origin")
                href = base + href
            
            # Clean up the href (remove slugs etc if needed)
            href = href.split("?")[0]
            
            raw_text = (await row.inner_text()).strip()
            
            # Recency
            posted_at_el = await row.query_selector("div.flex.flex-wrap.items-center.gap-x-2.gap-y-1")
            posted_at_text = (await posted_at_el.inner_text()).strip() if posted_at_el else None
            if posted_at_text and "ago" not in posted_at_text.lower() and "today" not in posted_at_text.lower():
                posted_at_text = None

            results.append({
                "link": href, 
                "raw_text": raw_text,
                "posted_at_text": posted_at_text
            })

    return results


async def _scrape_wellfound_job_details(page: Page, url: str) -> dict:
    """Visit a Wellfound job page and extract recruiter + salary info."""
    import random
    await page.wait_for_timeout(random.randint(2000, 5000))
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await page.wait_for_timeout(1000)
        
        # Salary
        salary_el = await page.query_selector(".styles_compensation__29m6I")
        salary = (await salary_el.inner_text()).strip() if salary_el else None
        
        # Recruiter
        recruiter_name = None
        recruiter_link = None
        
        # Try Hiring Team section
        hiring_team_el = await page.query_selector('.styles_hiringTeam__B83_d, [data-test="HiringTeam"]')
        if hiring_team_el:
            name_el = await hiring_team_el.query_selector(".styles_name__3vN9N, h4")
            recruiter_name = (await name_el.inner_text()).strip() if name_el else None
            
            link_el = await hiring_team_el.query_selector('a[href^="/p/"]')
            if link_el:
                r_href = await link_el.get_attribute("href")
                if r_href.startswith("/"):
                    recruiter_link = "https://wellfound.com" + r_href
                else:
                    recruiter_link = r_href
                    
        return {
            "salary": salary,
            "recruiter_name": recruiter_name,
            "recruiter_link": recruiter_link
        }
    except Exception as e:
        logger.warning(f"[listing_scraper] Wellfound detail scrape failed for {url}: {e}")
        return {}


async def _extract_glassdoor_cards(page: Page, max_cards: int = 30) -> list[dict]:
    """Extract job cards from Glassdoor search results."""
    cards = await page.query_selector_all(".JobCard_jobCardContainer__arQlW")
    results = []

    for card in cards[:max_cards]:
        title_el = (
            await card.query_selector(".JobCard_jobTitle__GLyJ1 a")
            or await card.query_selector('a[data-test="job-link"]')
        )

        href = (await title_el.get_attribute("href")) if title_el else None

        if href and href.startswith("/"):
            base = await page.evaluate("window.location.origin")
            href = base + href
            
        raw_text = (await card.inner_text()).strip()

        if href and raw_text:
            results.append({"link": href, "raw_text": raw_text})

    return results

async def open_page(bm: BrowserManager, url: str, platform: str) -> Page:
    """Opens a new browser page and navigates to the given URL."""
    page = await bm.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
    return page


def _card_to_raw_job(card: dict, source_url: str, platform: str) -> RawJobData:
    """Convert an extracted card dict into a RawJobData object."""
    link = card.get("link") or source_url
    raw_text = card.get("raw_text") or ""
    posted_at_text = card.get("posted_at_text")
    
    return RawJobData(
        source_url=link,
        source_platform=platform,
        raw_text=raw_text,
        raw_html=None,
        posted_at_text=posted_at_text,
        salary=card.get("salary"),
        recruiter_name=card.get("recruiter_name"),
        recruiter_link=card.get("recruiter_link")
    )


async def scrape_listing_page(
    bm: BrowserManager, url: str, search_queries: list[str] | None = None, max_cards: int = 30, freshness: str = "default", location: str = "India"
) -> tuple[list[RawJobData], list[str]]:
    """
    Scrape a known job platform listing page.
    Extracts at most max_cards from the first page.
    The caller (page_loader) handles batching and delays.
    """
    errors: list[str] = []
    query = " ".join(search_queries) if search_queries else ""

    platform = "unknown"
    if is_linkedin_listing(url):
        platform = "linkedin"
        normalized = _normalize_linkedin_url(url, query, freshness=freshness)
        extract_fn = _extract_linkedin_cards
    elif is_indeed_listing(url):
        platform = "indeed"
        normalized = _normalize_indeed_url(url, query)
        extract_fn = _extract_indeed_cards
    elif is_glassdoor_listing(url):
        platform = "glassdoor"
        normalized = _normalize_glassdoor_url(url, query)
        extract_fn = _extract_glassdoor_cards
    elif is_wellfound_listing(url):
        platform = "wellfound"
        normalized = _normalize_wellfound_url(url, query, location=location)
        extract_fn = _extract_wellfound_cards
    else:
        return [], [f"Unsupported known listing: {url}"]

    try:
        page = await open_page(bm, normalized, platform=platform)

        # Let JS render job cards — fixed delay instead of networkidle (stealthier)
        await page.wait_for_timeout(3000)

        cards = await extract_fn(page, max_cards=max_cards)
        
        # Wellfound specific: Detailed scrape for each card to get recruiter/salary
        if platform == "wellfound" and cards:
            logger.info(f"[listing_scraper] Wellfound: starting detailed scrape for {len(cards)} jobs")
            for card in cards:
                details = await _scrape_wellfound_job_details(page, card["link"])
                card.update(details)
                
        await page.close()

        logger.info(f"[listing_scraper] {platform}: extracted {len(cards)} job cards (cap {max_cards}) from {normalized}")

        if not cards:
            errors.append(f"No job cards found on {platform} listing: {normalized}")
            return [], errors

        raw_jobs = [_card_to_raw_job(c, url, platform) for c in cards]
        return raw_jobs, errors

    except Exception as e:
        errors.append(f"Listing scraper failed for {platform} ({normalized}): {e}")
        return [], errors
