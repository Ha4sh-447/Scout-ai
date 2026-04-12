"""job_discovery/agent.py"""

from models.config import ResumeMatchingConfig
from models.config import QdrantConfig
import logging
import os
import re

from agents.job_discovery.state import JobDiscoveryState
from extractors.deduplicator import deduplicate_within_batch, deduplicate_raw_jobs, semantic_deduplicate
from extractors.job_parser import parse_jobs_batch
from extractors.seen_jobs import filter_new_raw_jobs, mark_seen_raw_jobs
from models.config import ScraperConfig
from scrapers.page_loader import load_job_pages
from tools.browser.browser_manager import BrowserManager
from agents.resume_matching.agent import resume_matching_node as _run_matching

logger = logging.getLogger(__name__)


async def scrape_node(state: JobDiscoveryState) -> dict:
    """Scrape job URLs."""
    logger.info(
        f"[scrapper node] scrapping {len(state['urls'])} URLs for user {state['user_id']}"
    )

    config = state.get("scraper_config") or ScraperConfig()

    # Use session from DB if available, else fallback to config file path
    storage_state = state.get("browser_session") or config.browser_state_path
    
    # Initialize adaptive freshness state if missing
    freshness = state.get("freshness", "default")
    retry_count = state.get("retry_count", 0)
    platforms = state.get("platforms", ["linkedin"])
    location = state.get("location")

    async with BrowserManager(headless=True, storage_state=storage_state) as bm:
        search_queries = state.get("search_queries", [])
        raw_jobs, errors = await load_job_pages(
            bm, state["urls"], search_queries=search_queries, config=config, 
            freshness=freshness, platforms=platforms, location=location
        )

    logger.info(f"[scrapper node] Got {len(raw_jobs)} pages, {len(errors)} errors")

    return {
        "raw_jobs": raw_jobs,
        "errors": errors,
        "status": "scraping_done",
        "freshness": freshness,
        "retry_count": retry_count,
        "platforms": platforms,
        "location": location
    }


async def deduplicate_raw_node(state: JobDiscoveryState) -> dict:
    """Deduplicate raw jobs before parsing."""
    scraped_raw_jobs = state.get("raw_jobs", [])
    config = state.get("scraper_config") or ScraperConfig()
    
    logger.info(f"[deduplicate_raw node] ===== START RAW DEDUPLICATION =====")
    logger.info(f"[deduplicate_raw node] Input: {len(scraped_raw_jobs)} scraped raw jobs")

    if not scraped_raw_jobs:
        logger.info(f"[deduplicate_raw node] No raw jobs to process, skipping")
        return {"raw_jobs": [], "status": "raw_dedup_done"}

    deduplicated_raw_jobs = deduplicate_raw_jobs(scraped_raw_jobs)
    batch_dups_removed = len(scraped_raw_jobs) - len(deduplicated_raw_jobs)
    logger.info(f"[deduplicate_raw node] URL dedup: Removed {batch_dups_removed} duplicates. Remaining: {len(deduplicated_raw_jobs)}")

    user_id = state.get("user_id", "")
    unique_raw_jobs_for_parsing = await filter_new_raw_jobs(deduplicated_raw_jobs, user_id)
    previously_seen = len(deduplicated_raw_jobs) - len(unique_raw_jobs_for_parsing)
    logger.info(f"[deduplicate_raw node] Seen filter: Filtered {previously_seen} previously seen URLs. Remaining: {len(unique_raw_jobs_for_parsing)}")

    if unique_raw_jobs_for_parsing:
        await mark_seen_raw_jobs(unique_raw_jobs_for_parsing, user_id)
        logger.info(f"[deduplicate_raw node] Marked {len(unique_raw_jobs_for_parsing)} unique jobs as SEEN")

    logger.info(f"[deduplicate_raw node] ===== END RAW DEDUPLICATION =====")
    logger.info(f"[deduplicate_raw node] OUTPUT: {len(unique_raw_jobs_for_parsing)} unique raw jobs → PASS TO PARSE NODE")

    return {
        "raw_jobs": unique_raw_jobs_for_parsing,  # Only unique raw jobs passed to parse_node
        "status": "raw_dedup_done",
    }


async def parse_node(state: JobDiscoveryState) -> dict:
    """Parse unique raw jobs into structured data."""
    unique_raw_jobs = state.get("raw_jobs", [])
    
    logger.info(f"[parse node] ===== START PARSING UNIQUE JOBS =====")
    logger.info(f"[parse node] Input: {len(unique_raw_jobs)} unique raw jobs (already deduplicated)")

    if not unique_raw_jobs:
        logger.info(f"[parse node] No jobs to parse, returning empty")
        return {"parsed_jobs": [], "status": "parse_done"}

    dev_mode = os.getenv("DEVELOPMENT_MODE", "false").lower() == "true"
    raw_jobs_to_parse = unique_raw_jobs
    if dev_mode and len(unique_raw_jobs) > 3:
        raw_jobs_to_parse = unique_raw_jobs[:3]
        logger.warning(f"⚠️ DEVELOPMENT MODE: Limiting LLM parsing to {len(raw_jobs_to_parse)} jobs (skipping {len(unique_raw_jobs) - len(raw_jobs_to_parse)} jobs)")

    logger.info(f"[parse node] Sending {len(raw_jobs_to_parse)} unique jobs to LLM for parsing...")
    parsed_jobs, errors = await parse_jobs_batch(raw_jobs_to_parse)
    
    logger.info(f"[parse node] ===== END PARSING =====")
    logger.info(f"[parse node] OUTPUT: {len(parsed_jobs)} successfully parsed, {len(errors)} errors")

    return {
        "parsed_jobs": parsed_jobs,
        "errors": errors,
        "status": "parse_done",
    }


async def deduplicate_node(state: JobDiscoveryState) -> dict:
    """Final filtering and semantic deduplication stage."""
    parsed_jobs = state["parsed_jobs"]
    config = state.get("scraper_config") or ScraperConfig()
    logger.info(f"[deduplication node] ===== START FINAL FILTERING (POST-PARSE) =====")
    logger.info(f"[deduplication node] Input: {len(parsed_jobs)} parsed jobs (from deduplicated raw jobs)")

    if not parsed_jobs:
        logger.info(f"[deduplication node] No jobs to filter, returning empty")
        return {"unique_jobs": [], "status": "done"}

    unique_jobs = deduplicate_within_batch(parsed_jobs)
    hash_dedup_removed = len(parsed_jobs) - len(unique_jobs)
    logger.info(f"[deduplication node] Hash dedup (safety check): Removed {hash_dedup_removed} duplicates. {len(unique_jobs)} remain")

    if len(unique_jobs) > 5:
        unique_jobs = await semantic_deduplicate(unique_jobs)
        logger.info(f"[deduplication node] After semantic dedup: {len(unique_jobs)} unique jobs")

    user_exp_str = state.get("experience_level")
    if user_exp_str and unique_jobs:
        u_min, u_max = _parse_exp_years(user_exp_str)
        allowed_min = max(0, u_min - 1)
        allowed_max = u_max + 1
        
        filtered_jobs = []
        senior_keywords = ["senior", "lead", "mgr", "manager", "staff", "principal", "head", "architect", "vp", "director"]
        
        for job in unique_jobs:
            title = job.title.lower()
            is_senior_title = any(kw in title for kw in senior_keywords)
            
            j_min = job.min_years_experience
            if j_min is None:
                j_min, _ = _parse_exp_years(job.experience)
            
            if allowed_max <= 2 and is_senior_title:
                if "fresher" not in title and (j_min is None or j_min > 2):
                    logger.info(f"[deduplication node] Filtering Senior role {job.title} for entry-level user")
                    continue

            if j_min is not None:
                if j_min > allowed_max:
                    logger.info(f"[deduplication node] Filtering {job.title} (Requires {j_min} exp) for user {user_exp_str}")
                    continue
            
            filtered_jobs.append(job)
        
        logger.info(f"[deduplication node] After strict experience filter: {len(filtered_jobs)}/{len(unique_jobs)} jobs remain")
        unique_jobs = filtered_jobs

    retry_count = state.get("retry_count", 0)
    tier_map = {0: 9999, 1: 24, 2: 15, 3: 10}
    hours_limit = tier_map.get(retry_count, 10)
    
    fresh_jobs = []
    for job in unique_jobs:
        if _is_within_hours(job.posted_at_text, hours_limit):
            fresh_jobs.append(job)
        else:
            logger.info(f"[deduplication node] Filtering out old job (Tier {retry_count}): {job.title} ({job.posted_at_text})")
    
    unique_jobs = fresh_jobs
    logger.info(f"[deduplication node] Tier {retry_count} ({hours_limit}h limit): found {len(unique_jobs)} fresh jobs")

    current_freshness = state.get("freshness", "default")
    retry_count = state.get("retry_count", 0)
    
    total_unique_count = len(state.get("unique_jobs", [])) + len(unique_jobs)
    logger.info(f"[deduplication node] Cumulative unique jobs: {total_unique_count}")

    if total_unique_count >= 10:
        logger.info(f"[deduplication node] Threshold met ({total_unique_count} >= 10). Finishing discovery.")
        return {"unique_jobs": unique_jobs, "status": "done"}

    if total_unique_count < 10 and retry_count < 3:
        next_freshness = "past_week" if current_freshness == "default" else "past_24h"
        
        logger.warning(f"[deduplication node] Need more jobs ({total_unique_count}/10 found). Retrying Tier {retry_count + 1} with {next_freshness}.")
        
        return {
            "unique_jobs": unique_jobs,
            "status": "retry_fresher",
            "freshness": next_freshness,
            "retry_count": retry_count + 1
        }

    return {"unique_jobs": unique_jobs, "status": "done"}


def _is_within_hours(posted_at_text: str | None, max_hours: int) -> bool:
    """Tiered recency filter."""
    if not posted_at_text:
        return True  # If unknown, keep it for safety
    
    s = posted_at_text.lower()
    
    # Detect hours
    match_hours = re.search(r"(\d+)\s*(h|hour|hr)", s)
    if match_hours:
        val = int(match_hours.group(1))
        return val <= max_hours
    
    # Detect minutes/seconds/just now
    if any(kw in s for kw in ["minute", "min", "sec", "just now", "moment"]):
        return True

    # Detect days/yesterday
    if any(kw in s for kw in ["day", "yesterday"]):
        return max_hours >= 24

    # Detect weeks/months/years
    if any(kw in s for kw in ["week", "month", "year"]):
        return max_hours > 100

    # Default value True
    return True


def _parse_exp_years(exp_str: str | None) -> tuple[float, float]:
    """Parse experience string into (min_years, max_years)."""
    if not exp_str:
        return 0, 99
    
    s = exp_str.lower().strip()
    if "fresher" in s or "intern" in s or "graduate" in s:
        return 0, 1
    
    # Try to find numbers
    nums = re.findall(r"(\d+)", s)
    if not nums:
        if "senior" in s or "lead" in s or "staff" in s:
            return 5, 20
        return 0, 99
    
    ints = [int(n) for n in nums]
    if len(ints) >= 2:
        return float(min(ints)), float(max(ints))
    
    # Single number: "2+ years" -> [2, 12] or just "3 years" -> [3, 3]
    val = float(ints[0])
    if "+" in s or "above" in s or "more" in s:
        return val, val + 10
        
    return val, val

async def resume_matching_node(state: JobDiscoveryState) -> dict:
    """
    Bridges JobDiscoveryState into ResumeMatchingState, runs the matching
    agent, and merges results back into JobDiscoveryState.
    """
    from agents.resume_matching.state import ResumeMatchingState
 
    matching_state: ResumeMatchingState = {
        "user_id":      state["user_id"],
        "unique_jobs":  state.get("unique_jobs", []),
        "qdrant_cfg":   state.get("qdrant_cfg")   or QdrantConfig(),
        "matching_cfg": state.get("matching_cfg") or ResumeMatchingConfig(),
        "matched_jobs": [],
        "errors":       [],
        "status":       "starting",
    }
 
    result = await _run_matching(matching_state)
 
    return {
        "matched_jobs": result.get("matched_jobs", []),
        "errors":       result.get("errors", []),
        "status":       result.get("status", "matching_done"),
    }

