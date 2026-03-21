"""
Central page loader — routes URLs to the right scraper and handles
batched extraction with anti-detection delays.

Extraction strategy:
- First page only (no pagination)
- Max 30 jobs per URL
- Processed in batches of 10 with random 3-8s delays between batches
"""

import asyncio
import logging
import random
import re
from typing import List

from models.config import ScraperConfig
from models.jobs import RawJobData
from scrapers.generic_scraper import scrape_generic_listing
from scrapers.listing_scraper import is_known_listing, is_single_job_url, scrape_listing_page
from scrapers.reddit_scraper import is_subreddit_listing, scrape_reddit_listing
from tools.browser.browser_manager import BrowserManager
from tools.browser.extract_text import extract_html, extract_text
from tools.browser.open_page import open_page

logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    """Detect job platform from URL."""
    if "linkedin.com" in url:
        return "linkedin"
    if "indeed.com" in url:
        return "indeed"
    if "reddit.com" in url:
        return "reddit"
    if "glassdoor.com" in url or "glassdoor.co" in url:
        return "glassdoor"
    if "wellfound.com" in url:
        return "wellfound"
    return "generic"


def normalize_single_job_url(url: str) -> str:
    """Normalize single job URLs (e.g., converting LinkedIn to guest view)."""
    if "linkedin.com" in url and "currentJobId=" in url:
        match = re.search(r"currentJobId=(\d+)", url)
        if match:
            return f"https://www.linkedin.com/jobs/view/{match.group(1)}/"
    return url


async def _scrape_single_job(bm: BrowserManager, url: str) -> RawJobData | None:
    """Visit an individual job URL and extract full text."""
    platform = detect_platform(url)
    url = normalize_single_job_url(url)
    try:
        page = await open_page(bm, url, platform=platform)
        text = await extract_text(page, platform=platform)
        html = await extract_html(page, platform=platform)
        await page.close()

        if not text or len(text) < 100:
            return None

        return RawJobData(
            source_url=url,
            source_platform=platform,
            raw_text=text,
            raw_html=html,
        )
    except Exception as e:
        logger.error(f"Failed to scrape single job {url}: {e}")
        return None


def _batch_jobs(
    all_jobs: list[RawJobData],
    config: ScraperConfig
) -> list[list[RawJobData]]:
    """Split a list of jobs into batches, capped at max_jobs total."""
    capped = all_jobs[:config.max_jobs_per_url]
    return [capped[i : i + config.batch_size] for i in range(0, len(capped), config.batch_size)]


async def load_job_pages(
    bm: BrowserManager, 
    urls: List[str], 
    search_queries: list[str] | None = None,
    config: ScraperConfig | None = None,
    freshness: str = "default",
    platforms: List[str] | None = None,
    location: str | None = None
) -> tuple[List[RawJobData], List[str]]:
    """
    Scrape multiple URLs with hybrid routing and batched extraction.

    Flow per URL:
    1. Route to appropriate scraper (Reddit JSON / CSS listing / LLM generic / Playwright)
    2. All cards from first page are collected
    3. Capped at MAX_JOBS_PER_URL (30)
    4. Yielded in batches of BATCH_SIZE (10) with random delays between batches
    5. Random delay before moving to the next URL
    """
    all_results: list[RawJobData] = []
    all_errors: list[str] = []

    if config is None:
        config = ScraperConfig()

    # If no URLs provided but search queries exist, generate platform-specific search URLs
    if not urls and search_queries:
        platforms = platforms or ["linkedin"]
        logger.info(f"[page_loader] Generating search URLs for {len(search_queries)} queries on {platforms} in {location or 'default location'}")
        
        generated_urls = []
        loc_suffix = ""
        if location:
            from urllib.parse import quote_plus
            loc_q = quote_plus(location)
            
        for q in search_queries:
            from urllib.parse import quote_plus
            encoded_q = quote_plus(q)
            
            if "linkedin" in platforms:
                url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_q}"
                if location: url += f"&location={quote_plus(location)}"
                generated_urls.append(url)
                
            if "indeed" in platforms:
                # Indeed India default if no location
                url = f"https://in.indeed.com/jobs?q={encoded_q}"
                if location: url += f"&l={quote_plus(location)}"
                generated_urls.append(url)
                
            if "glassdoor" in platforms:
                url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={encoded_q}"
                if location: url += f"&location={quote_plus(location)}"
                generated_urls.append(url)

            if "wellfound" in platforms:
                def slugify(text: str) -> str:
                    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
                role_slug = slugify(q)
                loc_slug = slugify(location or "india")
                generated_urls.append(f"https://wellfound.com/role/l/{role_slug}/{loc_slug}")
        
        urls = generated_urls

    for i, url in enumerate(urls):
        platform = detect_platform(url)
        logger.info(f"[page_loader] ({i+1}/{len(urls)}) Scraping {platform}: {url}")

        try:
            if is_subreddit_listing(url):
                raw_jobs, errors = await scrape_reddit_listing(url, limit=config.max_jobs_per_url)
                all_errors.extend(errors)
                if not raw_jobs:
                    continue
                batches = _batch_jobs(raw_jobs, config)
                for b_idx, batch in enumerate(batches):
                    logger.info(f"[{platform}] batch {b_idx+1}/{len(batches)}: processed {len(batch)} jobs")
                    all_results.extend(batch)
                    if b_idx < len(batches) - 1:
                        await asyncio.sleep(random.uniform(*config.batch_delay_range))

            elif is_known_listing(url):
                raw_jobs, errors = await scrape_listing_page(
                    bm, url, search_queries=search_queries, max_cards=config.max_jobs_per_url, freshness=freshness, location=location
                )
                all_errors.extend(errors)
                if not raw_jobs:
                    continue
                    
                batches = _batch_jobs(raw_jobs, config)
                for b_idx, batch in enumerate(batches):
                    logger.info(f"[{platform}] batch {b_idx+1}/{len(batches)}: processed {len(batch)} jobs")
                    all_results.extend(batch)
                    if b_idx < len(batches) - 1:
                        await asyncio.sleep(random.uniform(*config.batch_delay_range))

            else:
                raw_jobs = []
                if not is_single_job_url(url):
                    raw_jobs, errors = await scrape_generic_listing(bm, url)
                    all_errors.extend(errors)
                
                if not raw_jobs and is_single_job_url(url):
                    job_data = await _scrape_single_job(bm, url)
                    if job_data:
                        raw_jobs = [job_data]
                    else:
                        all_errors.append(f"No content extracted from single job: {url}")
                        continue
                        
                if not raw_jobs:
                    continue
                    
                batches = _batch_jobs(raw_jobs, config)
                for b_idx, batch in enumerate(batches):
                    logger.info(f"[{platform}] batch {b_idx+1}/{len(batches)}: processed {len(batch)} jobs")
                    all_results.extend(batch)
                    if b_idx < len(batches) - 1:
                        await asyncio.sleep(random.uniform(*config.batch_delay_range))

        except Exception as e:
            all_errors.append(f"Scraper failed for {url}: {e}")
            logger.error(f"[page_loader] Error scraping {url}: {e}")

        # Random delay between URLs (skip after last URL)
        if i < len(urls) - 1:
            delay = random.uniform(*config.url_delay_range)
            logger.info(f"[page_loader] Waiting {delay:.1f}s before next URL")
            await asyncio.sleep(delay)

    logger.info(
        f"[page_loader] Total: {len(all_results)} jobs from {len(urls)} URLs, "
        f"{len(all_errors)} errors"
    )
    return all_results, all_errors
