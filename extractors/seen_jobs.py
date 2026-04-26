"""
Cross-run seen-jobs persistence using Redis.

Stores source URLs of previously scraped raw jobs in a Redis SET per user.
On future runs, jobs already in the store are filtered out so the user
only sees new listings.
Entries older than 30 days are auto-pruned via Redis key expiry tracking (renewed per user).
"""

import os
import logging
from redis.asyncio import Redis

from models.jobs import RawJobData

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _get_redis_client() -> Redis:
    # Run in different loopss
    return Redis.from_url(REDIS_URL, decode_responses=True)

async def filter_new_raw_jobs(raw_jobs: list[RawJobData], user_id: str) -> list[RawJobData]:
    """
    Filter out raw jobs already scraped in previous runs using Redis.
    Key: seen_jobs:{user_id}
    """
    if not user_id or not raw_jobs:
        return raw_jobs

    new_raw_jobs = []
    key = f"seen_jobs:{user_id}"

    redis_client = _get_redis_client()
    try:
        pipe = redis_client.pipeline()
        for raw_job in raw_jobs:
            url_key = raw_job.source_url.lower().strip()
            pipe.sismember(key, url_key)

        results = await pipe.execute()

        for raw_job, is_member in zip(raw_jobs, results):
            if not is_member:
                new_raw_jobs.append(raw_job)
    finally:
        await redis_client.aclose()

    skipped = len(raw_jobs) - len(new_raw_jobs)
    if skipped > 0:
        logger.info(f"[seen_jobs] Filtered out {skipped} previously seen raw jobs for {user_id}")

    return new_raw_jobs


async def mark_seen_raw_jobs(raw_jobs: list[RawJobData], user_id: str) -> None:
    """
    Mark raw jobs as seen in Redis.
    """
    if not user_id or not raw_jobs:
        return
        
    key = f"seen_jobs:{user_id}"
    url_keys = [raw_job.source_url.lower().strip() for raw_job in raw_jobs]

    redis_client = _get_redis_client()
    try:
        if url_keys:
            await redis_client.sadd(key, *url_keys)
            # Keep tracking jobs for 30 days for this user
            await redis_client.expire(key, 2592000)
    finally:
        await redis_client.aclose()

    logger.info(f"[seen_jobs] Marked {len(url_keys)} raw jobs as seen for {user_id}")
