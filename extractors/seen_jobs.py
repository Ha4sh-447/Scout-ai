"""
Cross-run seen-jobs persistence.

Stores content hashes of previously scraped jobs in a JSON file.
On future runs, jobs already in the store are filtered out so the user
only sees new listings. Entries older than 30 days are auto-pruned.
"""

import json
import logging
import os
from datetime import datetime, timedelta

from models.jobs import Job

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


def filter_new_jobs(jobs: list[Job], seen_path: str) -> list[Job]:
    """
    Filter out jobs that were already scraped in previous runs.
    Returns only jobs whose content_hash is not in the seen store.
    """
    store = _load_store(seen_path)
    store = _prune_old_entries(store)

    new_jobs = []
    for job in jobs:
        if job.content_hash and job.content_hash in store:
            continue
        new_jobs.append(job)

    skipped = len(jobs) - len(new_jobs)
    if skipped > 0:
        logger.info(f"[seen_jobs] Filtered out {skipped} previously seen jobs")

    return new_jobs


def mark_seen(jobs: list[Job], seen_path: str) -> None:
    """
    Mark jobs as seen by saving their content hashes to the store.
    """
    store = _load_store(seen_path)
    now = datetime.now().isoformat()

    for job in jobs:
        if job.content_hash and job.content_hash not in store:
            store[job.content_hash] = {
                "title": job.title,
                "company": job.company,
                "first_seen": now,
            }

    _save_store(seen_path, store)
    logger.info(f"[seen_jobs] Store now has {len(store)} entries (saved to {seen_path})")
