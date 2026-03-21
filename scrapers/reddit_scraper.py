"""
Reddit JSON API scraper.

Uses Reddit's public .json endpoint to fetch posts from subreddit listings.
Much faster and more reliable than browser scraping for listing pages.
"""

import logging
import re

import httpx

from models.jobs import RawJobData

logger = logging.getLogger(__name__)

REDDIT_HEADERS = {
    "User-Agent": "AgenticJobFinder/1.0 (job-discovery-bot)",
}

# Matches subreddit listing URLs like /r/MachineLearningJobs/ (no /comments/ path)
SUBREDDIT_LISTING_RE = re.compile(
    r"^https?://(www\.)?reddit\.com/r/([^/]+)/?(\?.*)?$"
)


def is_subreddit_listing(url: str) -> bool:
    """Check if a URL is a Reddit subreddit listing (not an individual post)."""
    return bool(SUBREDDIT_LISTING_RE.match(url))


async def scrape_reddit_listing(
    url: str, limit: int = 50
) -> tuple[list[RawJobData], list[str]]:
    """
    Fetch posts from a subreddit listing using the JSON API.

    Returns (raw_jobs, errors).
    Each post becomes a separate RawJobData object.
    Stickied posts are skipped (they're usually meta/rules).
    """
    # Build the JSON API URL
    match = SUBREDDIT_LISTING_RE.match(url)
    if not match:
        return [], [f"Not a valid subreddit listing URL: {url}"]

    subreddit = match.group(2)
    json_url = f"https://www.reddit.com/r/{subreddit}.json?limit={limit}"

    raw_jobs: list[RawJobData] = []
    errors: list[str] = []

    try:
        async with httpx.AsyncClient(
            headers=REDDIT_HEADERS, follow_redirects=True, timeout=15.0
        ) as client:
            response = await client.get(json_url)
            response.raise_for_status()
            data = response.json()

        posts = data.get("data", {}).get("children", [])
        logger.info(f"[reddit_scraper] Fetched {len(posts)} posts from r/{subreddit}")

        for post in posts:
            post_data = post.get("data", {})

            # Skip stickied / pinned posts (usually rules / meta)
            if post_data.get("stickied", False):
                continue

            title = post_data.get("title", "")
            selftext = post_data.get("selftext", "")
            permalink = post_data.get("permalink", "")

            # Skip posts with no body text (link-only posts or image posts)
            if not selftext or len(selftext.strip()) < 30:
                continue

            post_url = f"https://www.reddit.com{permalink}"
            raw_text = f"{title}\n\n{selftext}"

            raw_jobs.append(
                RawJobData(
                    source_url=post_url,
                    source_platform="reddit",
                    raw_text=raw_text,
                    raw_html=None,
                )
            )

        logger.info(
            f"[reddit_scraper] Extracted {len(raw_jobs)} job posts from r/{subreddit} "
            f"(skipped stickied and empty posts)"
        )

    except httpx.HTTPStatusError as e:
        errors.append(f"Reddit API error for r/{subreddit}: HTTP {e.response.status_code}")
    except Exception as e:
        errors.append(f"Reddit scraper failed for r/{subreddit}: {e}")

    return raw_jobs, errors
