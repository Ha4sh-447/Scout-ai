import asyncio
import json
import re
import random

import os
from mistralai.client import Mistral

from models.jobs import Job, JobType, PosterType, RecruiterInfo

from extractors.company_sanitizer import sanitise_company_name, sanitise_job_description

client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

PARSER_SYSTEM_PROMPT = """You are a job posting parser. Extract structured information from raw job posting text.

Return ONLY a valid JSON object with these exact fields:
{
  "title": "exact job title",
  "company": "company name",
  "location": "city, country or 'Remote'",
  "salary": "salary range or null if not mentioned",
  "experience": "required experience (e.g. '2+ years' or 'Fresher') or null",
  "min_years_experience": "integer value of the minimum required years of experience (e.g. 2, 0 for Fresher/Junior) or null",
  "skills": ["skill1", "skill2"],
  "description": "key responsibilities and brief description of the role",
  "about_company": "short summary about the company or null",
  "job_type": ["remote", "full_time"],
  "poster_type": "direct_hire" | "agency_recruiter" | "unknown",
  "recruiter": {
    "name": "name or null",
    "email": "email or null",
    "linkedin_url": "url or null",
    "profile_url": "url or null"
  } or null
}

Rules:
- skills: extract ONLY technical skills and tools, not soft skills. Normalise variants (ReactJS → React, Node.js → Node)
- experience: extract the years of experience or 'Fresher'/'Intern' if applicable
- description: prioritize key responsibilities over generic blurbs
- about_company: keep it to a short 1-2 sentence summary
- job_type: array of one or more from: "remote", "on_site", "hybrid", "full_time", "part_time", "contract", "internship", "unknown". A job can be both e.g. ["remote", "full_time"]
- poster_type: "agency_recruiter" if posted by a staffing/recruiting firm, "direct_hire" if by the company itself
- recruiter: only populate if there is an actual person's contact info in the posting (common on LinkedIn). Extract name, email, or LinkedIn profile URL if given.
- Return null for any field you cannot determine
- No markdown, no explanation — raw JSON only"""


async def parse_job(
    raw_text: str, 
    source_url: str, 
    source_platform: str, 
    posted_at_text: str | None = None,
    scraped_salary: str | None = None,
    scraped_recruiter_name: str | None = None,
    scraped_recruiter_link: str | None = None
) -> Job | None:
    """
    Use Mistral to parse raw job posting text into a structured Job model.
    Returns None if parsing fails.
    """
    # Truncate very long postings
    text = raw_text[:6000] if len(raw_text) > 6000 else raw_text

    try:
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PARSER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Parse this job posting:\n\nURL: {source_url}\n\n{text}",
                },
            ],
        )

        raw_json = response.choices[0].message.content.strip()
        raw_json = _strip_markdown_fences(raw_json)
        data = json.loads(raw_json)

        recruiter = None
        if data.get("recruiter"):
            recruiter = RecruiterInfo(**data["recruiter"])

        raw_poster_type = data.get("poster_type")
        try:
            poster_type = PosterType(raw_poster_type) if raw_poster_type else PosterType.unknown
        except ValueError:
            poster_type = PosterType.unknown

        raw_job_type = data.get("job_type")
        job_type_list = [JobType.unknown]
        if raw_job_type:
            if isinstance(raw_job_type, str):
                raw_job_type = [raw_job_type]
            if isinstance(raw_job_type, list):
                resolved = []
                for jt in raw_job_type:
                    try:
                        resolved.append(JobType(jt))
                    except ValueError:
                        pass
                if resolved:
                    job_type_list = resolved

        company = sanitise_company_name(data.get("company"))
        description = sanitise_job_description(data.get("description") or "")

        return Job(
            title=data.get("title") or "Unknown Title",
            company=company,
            location=data.get("location") or "Unknown",
            salary=scraped_salary or data.get("salary"),
            experience=data.get("experience"),
            min_years_experience=data.get("min_years_experience"),
            skills=data.get("skills") or [],
            source_url=source_url,
            source_platform=source_platform,
            description=description,
            about_company=data.get("about_company"),
            job_type=job_type_list,
            poster_type=poster_type,
            recruiter=recruiter or (RecruiterInfo(name=scraped_recruiter_name, profile_url=scraped_recruiter_link) if scraped_recruiter_name else None),
            posted_at_text=posted_at_text,
        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Mistral returned invalid JSON for {source_url}: {e}")
    except Exception as e:
        raise RuntimeError(f"Parser failed for {source_url}: {e}") from e


async def parse_jobs_batch(raw_jobs) -> tuple[list[Job], list[str]]:
    """
    Parse a list of RawJobData objects.
    Returns (parsed_jobs, errors).
    Includes exponential backoff retry for rate limits.
    """
    parsed = []
    errors = []

    semaphore = asyncio.Semaphore(2)

    async def parse_one(raw):
        async with semaphore:
            retries = 3
            for attempt in range(1, retries + 1):
                try:
                    safe_text = raw.raw_text[:8000]
                    job = await parse_job(
                        safe_text, 
                        raw.source_url, 
                        raw.source_platform, 
                        raw.posted_at_text,
                        scraped_salary=raw.salary,
                        scraped_recruiter_name=raw.recruiter_name,
                        scraped_recruiter_link=raw.recruiter_link
                    )
                    if job:
                        parsed.append(job)
                    return
                except RuntimeError as e:
                    if "429" in str(e) and attempt < retries:
                        delay = (3 ** attempt) + random.uniform(1, 3)
                        await asyncio.sleep(delay)
                    else:
                        errors.append(str(e))
                        return
                except Exception as e:
                    errors.append(str(e))
                    return

    await asyncio.gather(*[parse_one(r) for r in raw_jobs])
    return parsed, errors


def _strip_markdown_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
