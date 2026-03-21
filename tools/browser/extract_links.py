import re
from urllib.parse import urljoin

from playwright.async_api import Page

# Patterns that indicate a URL is a job listing (not navigation/ads)
JOB_URL_PATTERNS = {
    "linkedin": r"linkedin\.com/jobs/view/\d+",
    "indeed": r"indeed\.com/viewjob\?jk=",
    "reddit": r"reddit\.com/r/(forhire|jobbit|remotework|jobs)/comments/",
    "generic": r"",
}


async def extract_links(page: Page, platform: str = "generic") -> list[str]:
    """
    Extract all job listing URLs from a search results or listing page.
    Filters to only links that look like individual job postings.
    """
    base_url = page.url
    all_anchors = await page.query_selector_all("a[href]")

    links = []
    for anchor in all_anchors:
        href = await anchor.get_attribute("href")
        if not href:
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)

        if _is_job_url(full_url, platform):
            links.append(full_url)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)

    return unique


def _is_job_url(url: str, platform: str) -> bool:
    pattern = JOB_URL_PATTERNS.get(platform, "")
    if pattern and re.search(pattern, url):
        return True

    # Generic heuristic: URL contains job-related keywords
    job_keywords = [
        "/job/",
        "/jobs/",
        "/posting/",
        "/position/",
        "/careers/",
        "viewjob",
    ]
    return any(kw in url.lower() for kw in job_keywords)
