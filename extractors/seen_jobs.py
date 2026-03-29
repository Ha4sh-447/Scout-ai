"""
Cross-run seen-jobs persistence.

Stores source URLs of previously scraped raw jobs in a JSON file.
On future runs, jobs already in the store are filtered out so the user
only sees new listings. Works with RawJobData before parsing for efficient comparison.
Entries older than 30 days are auto-pruned.
"""

import json
import logging
import os
from datetime import datetime, timedelta

from models.jobs import RawJobData

logger = logging.getLogger(__name__)

PRUNE_AFTER_DAYS = 30


def _load_store(path: str) -> dict:
    """Load the seen-jobs JSON file. Returns {} if missing or corrupt."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning(f"[seen_jobs] Corrupt store at {path}, starting fresh")
        return {}


def _save_store(path: str, store: dict) -> None:
    """Save the seen-jobs store to disk."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(store, f, indent=2)


def _prune_old_entries(store: dict) -> dict:
    """Remove entries older than PRUNE_AFTER_DAYS."""
    cutoff = (datetime.now() - timedelta(days=PRUNE_AFTER_DAYS)).isoformat()
    pruned = {
        h: info for h, info in store.items()
        if info.get("first_seen", "") >= cutoff
    }
    removed = len(store) - len(pruned)
    if removed > 0:
        logger.info(f"[seen_jobs] Pruned {removed} entries older than {PRUNE_AFTER_DAYS} days")
    return pruned


def filter_new_raw_jobs(raw_jobs: list[RawJobData], seen_path: str) -> list[RawJobData]:
    """
    Filter out raw jobs already scraped in previous runs.
    Uses source_url as the unique key for comparison.
    Returns only raw jobs whose source_url is not in the seen store.
    
    This filtering happens BEFORE parsing, saving expensive LLM calls.
    """
    store = _load_store(seen_path)
    store = _prune_old_entries(store)

    new_raw_jobs = []
    for raw_job in raw_jobs:
        url_key = raw_job.source_url.lower().strip()
        if url_key not in store:
            new_raw_jobs.append(raw_job)

    skipped = len(raw_jobs) - len(new_raw_jobs)
    if skipped > 0:
        logger.info(f"[seen_jobs] Filtered out {skipped} previously seen raw jobs (by source_url)")

    return new_raw_jobs


def mark_seen_raw_jobs(raw_jobs: list[RawJobData], seen_path: str) -> None:
    """
    Mark raw jobs as seen by storing their source URLs in the seen store.
    This approach is simpler and faster than parsing-based comparison.
    """
    store = _load_store(seen_path)
    now = datetime.now().isoformat()

    for raw_job in raw_jobs:
        url_key = raw_job.source_url.lower().strip()
        if url_key not in store:
            store[url_key] = {
                "url": raw_job.source_url,
                "platform": raw_job.source_platform,
                "first_seen": now,
            }

    _save_store(seen_path, store)
    logger.info(f"[seen_jobs] Raw job store now has {len(store)} entries (saved to {seen_path})")


# Keep legacy parsed job functions for backward compatibility
def filter_new_jobs(jobs, seen_path: str):
    """
    Legacy: Filter parsed jobs against the seen store.
    Now uses raw job keys internally, but accepts parsed Job objects.
    """
    store = _load_store(seen_path)
    store = _prune_old_entries(store)

    new_jobs = []
    for job in jobs:
        # For parsed jobs, we try to match by URL if available, otherwise skip
        url_key = getattr(job, 'source_url', '').lower().strip() if hasattr(job, 'source_url') else None
        if url_key and url_key not in store:
            new_jobs.append(job)

    skipped = len(jobs) - len(new_jobs)
    if skipped > 0:
        logger.info(f"[seen_jobs] Filtered out {skipped} previously seen parsed jobs")

    return new_jobs


def mark_seen(jobs, seen_path: str) -> None:
    """
    Legacy: Mark parsed jobs as seen.
    Now uses raw job approach (source_url as key).
    """
    store = _load_store(seen_path)
    now = datetime.now().isoformat()

    for job in jobs:
        # Try to use source_url if available
        url_key = getattr(job, 'source_url', '').lower().strip() if hasattr(job, 'source_url') else None
        if url_key and url_key not in store:
            store[url_key] = {
                "url": url_key,
                "title": getattr(job, 'title', ''),
                "first_seen": now,
            }

    _save_store(seen_path, store)
    logger.info(f"[seen_jobs] Store now has {len(store)} entries (saved to {seen_path})")
