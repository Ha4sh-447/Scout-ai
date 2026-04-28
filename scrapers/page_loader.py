"""page_loader.py"""

import asyncio
import logging
import random
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
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

    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""

    if not host:
        return "generic"

    host = re.sub(r"^(www\.|m\.|jobs\.|careers\.)", "", host)
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "edu"}:
        site = parts[-3]
    elif len(parts) >= 2:
        site = parts[-2]
    else:
        site = parts[0]

    site = re.sub(r"[^a-z0-9]+", "_", site).strip("_")
    return site or "generic"


def normalize_single_job_url(url: str) -> str:
    """Normalize single job URLs (e.g., converting LinkedIn to guest view)."""
    if "linkedin.com" in url and "currentJobId=" in url:
        match = re.search(r"currentJobId=(\d+)", url)
        if match:
            return f"https://www.linkedin.com/jobs/view/{match.group(1)}/"
    return url


def _url_contains_query_terms(url: str, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True

    decoded_url = (url or "").lower().replace("+", " ").replace("%20", " ")
    tokens = [t for t in re.split(r"\W+", q) if len(t) > 2]
    if not tokens:
        return q in decoded_url

    hits = sum(1 for t in tokens if t in decoded_url)
    required = max(1, len(tokens) // 2)
    return hits >= required


def _url_has_search_param(url: str) -> bool:
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
    except Exception:
        return False

    search_keys = {
        "q", "query", "keyword", "keywords", "search", "searchtext", "k", "term", "text", "wd", "what", "roles", "skills", "title", "position", "job_title"
    }
    return any(k.lower() in search_keys for k in params.keys())


def _pick_search_param_key(params: dict[str, list[str]]) -> str | None:
    """Pick the most likely existing query-intent key from URL params."""
    if not params:
        return None

    priority_keys = [
        "q", "query", "keyword", "keywords", "search", "searchtext", "k", "term", "text", "wd", "what",
        "roles", "skills", "title", "position", "job_title",
    ]

    lower_to_original = {k.lower(): k for k in params.keys()}
    for key in priority_keys:
        if key in lower_to_original:
            return lower_to_original[key]

    for original_key in params.keys():
        k = original_key.lower()
        if any(token in k for token in ["query", "search", "keyword", "role", "skill", "title", "position", "term"]):
            return original_key

    return None


def _inject_query_if_missing(url: str, query: str) -> str:
    if not query:
        return url

    if _url_contains_query_terms(url, query):
        return url

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    existing_key = _pick_search_param_key(params)
    if existing_key:
        current_value = " ".join(params.get(existing_key, []))
        if not _url_contains_query_terms(current_value, query):
            params[existing_key] = [query]

        if existing_key.lower() in {"roles", "skills", "title", "position", "job_title"}:
            params.pop("q", None)

        new_query = urlencode(params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    params["q"] = [query]
    new_query = urlencode(params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


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
    """Scrape multiple URLs with hybrid routing."""
    all_results: list[RawJobData] = []
    all_errors: list[str] = []

    if config is None:
        config = ScraperConfig()

    if not urls and search_queries:
        platforms = platforms or ["linkedin"]
        generated_urls = []
        for q in search_queries:
            from urllib.parse import quote_plus
            encoded_q = quote_plus(q)
            if "linkedin" in platforms:
                url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_q}"
                if location: url += f"&location={quote_plus(location)}"
                generated_urls.append(url)
            if "indeed" in platforms:
                url = f"https://in.indeed.com/jobs?q={encoded_q}"
                if location: url += f"&l={quote_plus(location)}"
                generated_urls.append(url)
            if "glassdoor" in platforms:
                url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={encoded_q}"
                if location: url += f"&location={quote_plus(location)}"
                generated_urls.append(url)
        urls = generated_urls

    for i, url in enumerate(urls):
        query_hint = " ".join(search_queries or []).strip()
        if query_hint and not is_single_job_url(url):
            maybe_updated = _inject_query_if_missing(url, query_hint)
            if maybe_updated != url:
                logger.info(f"[page_loader] Added missing query to URL: {url} -> {maybe_updated}")
                url = maybe_updated

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
                if errors:
                    for e in errors:
                        logger.warning(f"[page_loader] ⚠️ {platform} scrape issue: {e}")
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
            logger.error(f"[page_loader] ❌ Error scraping {platform} ({url}): {e}", exc_info=True)

        if i < len(urls) - 1:
            delay = random.uniform(*config.url_delay_range)
            logger.info(f"[page_loader] Waiting {delay:.1f}s before next URL")
            await asyncio.sleep(delay)

    logger.info(
        f"[page_loader] Total: {len(all_results)} jobs from {len(urls)} URLs, "
        f"{len(all_errors)} errors"
    )
    return all_results, all_errors
