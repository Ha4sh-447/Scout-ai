"""
Generic LLM-based listing scraper for unknown job portals.

When we don't have platform-specific CSS selectors, we use Mistral
to split the page text into individual job postings.
"""

import json
import logging
import os
import re

from playwright.async_api import Page

from models.jobs import RawJobData
from tools.browser.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

LISTING_SPLITTER_PROMPT = """You are a job listing page analyzer. Given the text content of a job listing webpage, extract each individual job posting.

Return a JSON object with a "jobs" key containing an array. Each element should have:
{
  "jobs": [
    {
      "title": "job title",
      "company": "company name",
      "location": "location or Remote",
      "description": "brief description of the role (2-3 sentences max)"
    }
  ]
}

Rules:
- Extract ONLY actual job postings, not navigation text, ads, or page boilerplate
- If the page contains no job postings, return {"jobs": []}
- Extract at most 30 jobs
- Return raw JSON only, no markdown fences or explanations"""


async def scrape_generic_listing(
    bm: BrowserManager, url: str
) -> tuple[list[RawJobData], list[str]]:
    """
    Scrape an unknown job portal by sending page text to Mistral
    to identify and split individual job postings.

    Returns (raw_jobs, errors).
    """
    from mistralai.client import Mistral

    errors: list[str] = []

    try:
        page = await bm.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await page.wait_for_timeout(3000)

        page_text = await page.inner_text("body")
        await page.close()

        if not page_text or len(page_text) < 100:
            errors.append(f"No meaningful content extracted from {url}")
            return [], errors

        page_text = page_text[:8000]

        logger.info(
            f"[generic_scraper] Extracted {len(page_text)} chars from {url}, sending to LLM"
        )

        client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

        response = await client.chat.complete_async(
            model="mistral-large-latest",
            max_tokens=4096,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": LISTING_SPLITTER_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract job postings from this page:\n\nURL: {url}\n\n{page_text}",
                },
            ],
        )

        raw_json = response.choices[0].message.content.strip()
        raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json)
        raw_json = re.sub(r"\s*```$", "", raw_json)
        data = json.loads(raw_json)

        if isinstance(data, dict):
            jobs_list = data.get("jobs", [])
        elif isinstance(data, list):
            jobs_list = data
        else:
            jobs_list = []

        logger.info(f"[generic_scraper] LLM identified {len(jobs_list)} job postings from {url}")

        raw_jobs = []
        for job in jobs_list:
            title = job.get("title") or "Unknown Title"
            company = job.get("company") or "Unknown"
            location = job.get("location") or "Unknown"
            description = job.get("description") or ""

            raw_text = (
                f"Job Title: {title}\n"
                f"Company: {company}\n"
                f"Location: {location}\n"
                f"Description: {description}\n"
                f"Source: {url}"
            )

            raw_jobs.append(
                RawJobData(
                    source_url=url,
                    source_platform="generic",
                    raw_text=raw_text,
                    raw_html=None,
                )
            )

        return raw_jobs, errors

    except json.JSONDecodeError as e:
        errors.append(f"LLM returned invalid JSON for {url}: {e}")
        return [], errors
    except Exception as e:
        errors.append(f"Generic scraper failed for {url}: {e}")
        return [], errors
