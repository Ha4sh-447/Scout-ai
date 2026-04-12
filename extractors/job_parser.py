"""job_parser.py"""
import asyncio
import json
import logging
import os
import re
import random
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator

from core.llm_router import get_router, PROVIDERS
from core.llm_sanitizer import sanitize_job_text, MAX_TOKENS_HIGH, MAX_TOKENS_LOW
from extractors.company_sanitizer import sanitise_company_name, sanitise_job_description
from models.jobs import Job, JobType, PosterType, RecruiterInfo

logger = logging.getLogger(__name__)


PARSER_SYSTEM_PROMPT = """\
You are a precise job posting parser. You will receive one or more job postings \
wrapped in <job_posting> XML tags.

For EACH job, return a JSON object with EXACTLY these fields:
{
  "index": <integer matching the index attribute>,
  "title": "exact job title",
  "company": "company name",
  "location": "city, country or 'Remote'",
  "salary": "salary range or null",
  "experience": "required experience (e.g. '2+ years') or null",
  "min_years_experience": <integer or null>,
  "skills": ["skill1", "skill2"],
  "description": "key responsibilities — 2-3 sentences max",
  "about_company": "1-2 sentence summary or null",
  "job_type": ["remote", "full_time"],
  "poster_type": "direct_hire" | "agency_recruiter" | "unknown",
  "recruiter": {"name": null, "email": null, "linkedin_url": null, "profile_url": null} | null
}

Rules:
- skills: technical skills only; normalise variants (ReactJS→React, Node.js→Node)
- job_type array: values from {remote, on_site, hybrid, full_time, part_time, contract, internship, unknown}
- poster_type: agency_recruiter if posted by a staffing firm
- description: prioritise responsibilities over marketing fluff
- Return a JSON ARRAY of objects, one per job, in the same index order
- NO markdown, NO explanation — raw JSON array only\
"""


class _RecruiterSchema(BaseModel):
    name:         Optional[str] = None
    email:        Optional[str] = None
    linkedin_url: Optional[str] = None
    profile_url:  Optional[str] = None

class _ParsedJobSchema(BaseModel):
    index:               int
    title:               str
    company:             str
    location:            str = "Unknown"
    salary:              Optional[str] = None
    experience:          Optional[str] = None
    min_years_experience: Optional[int] = None
    skills:              list[str] = []
    description:         str = ""
    about_company:       Optional[str] = None
    job_type:            list[str] = ["unknown"]
    poster_type:         str = "unknown"
    recruiter:           Optional[_RecruiterSchema] = None

    @field_validator("skills", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v or []


async def parse_jobs_batch(raw_jobs) -> tuple[list[Job], list[str]]:
    """
    Parse a list of RawJobData using the LLM router.
    Batches up to max_batch jobs per call (provider-dependent).
    Returns (parsed_jobs, errors).
    """
    parsed: list[Job] = []
    errors:  list[str] = []

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    router    = await get_router(redis_url)

    max_batch = 10  # router picks the right size per provider internally

    # Split into chunks
    chunks = [raw_jobs[i:i+max_batch] for i in range(0, len(raw_jobs), max_batch)]

    for chunk in chunks:
        chunk_errors = await _parse_chunk(chunk, router, parsed)
        errors.extend(chunk_errors)

    logger.info(
        "[job_parser] Parsed %d/%d jobs (%d errors)",
        len(parsed), len(raw_jobs), len(errors)
    )
    return parsed, errors


async def parse_jobs_batch_for_user(raw_jobs, user_id: str) -> tuple[list[Job], list[str]]:
    """Same as parse_jobs_batch but enforces per-user quota tracking."""
    parsed: list[Job] = []
    errors:  list[str] = []

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    router    = await get_router(redis_url)

    chunks = [raw_jobs[i:i+10] for i in range(0, len(raw_jobs), 10)]
    for chunk in chunks:
        chunk_errors = await _parse_chunk(chunk, router, parsed, user_id=user_id)
        errors.extend(chunk_errors)

    return parsed, errors



async def _parse_chunk(
    raw_jobs,
    router,
    parsed_out: list[Job],
    user_id: str | None = None,
) -> list[str]:
    """Build one batch prompt, call router, parse each job in the response."""
    errors: list[str] = []

    parts = []
    for idx, raw in enumerate(raw_jobs):
        safe_text = sanitize_job_text(raw.raw_text, token_budget=MAX_TOKENS_HIGH)
        parts.append(
            f'<job_posting index="{idx}">\n'
            f'<url>{raw.source_url}</url>\n'
            f'<text>{safe_text}</text>\n'
            f'</job_posting>'
        )
    user_prompt = "\n\n".join(parts)

    cache_key = ":".join(r.source_url for r in raw_jobs)

    for attempt in range(1, 4):
        try:
            raw_json = await router.complete(
                system       = PARSER_SYSTEM_PROMPT,
                user_content = user_prompt,
                user_id      = user_id,
                cache_key    = cache_key,
                response_format={"type": "json_object"} if len(raw_jobs) == 1 else None,
                max_tokens   = 1024 * len(raw_jobs),
            )

            raw_json = _strip_markdown_fences(raw_json)

            data = json.loads(raw_json)
            if isinstance(data, dict):
                # Single job came back as object — wrap in list
                data = [data]

            for item in data:
                try:
                    schema = _ParsedJobSchema(**item)
                    idx    = schema.index
                    if idx >= len(raw_jobs):
                        continue
                    raw = raw_jobs[idx]
                    job = _schema_to_job(schema, raw)
                    if job:
                        parsed_out.append(job)
                except Exception as ve:
                    errors.append(f"Schema validation error: {ve}")

            return errors

        except json.JSONDecodeError as e:
            if attempt < 3:
                await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
            else:
                errors.append(f"JSON decode failed after retries: {e}")
        except RuntimeError as e:
            if "rate" in str(e).lower() or "429" in str(e):
                if attempt < 3:
                    await asyncio.sleep(3 ** attempt + random.uniform(1, 3))
                else:
                    errors.append(f"All providers rate-limited: {e}")
            else:
                errors.append(str(e))
                break
        except Exception as e:
            errors.append(str(e))
            break

    return errors


def _schema_to_job(schema: _ParsedJobSchema, raw) -> Job | None:
    """Convert validated schema + original raw data → Job model."""
    try:
        try:
            poster_type = PosterType(schema.poster_type)
        except ValueError:
            poster_type = PosterType.unknown

        job_type_list = [JobType.unknown]
        if schema.job_type:
            resolved = []
            for jt in schema.job_type:
                try:
                    resolved.append(JobType(jt))
                except ValueError:
                    pass
            if resolved:
                job_type_list = resolved

        recruiter = None
        if schema.recruiter:
            recruiter = RecruiterInfo(**schema.recruiter.model_dump())

        company     = sanitise_company_name(schema.company)
        description = sanitise_job_description(schema.description or "")

        return Job(
            title                = schema.title or "Unknown Title",
            company              = company,
            location             = schema.location,
            salary               = getattr(raw, "salary", None) or schema.salary,
            experience           = schema.experience,
            min_years_experience = schema.min_years_experience,
            skills               = schema.skills,
            source_url           = raw.source_url,
            source_platform      = raw.source_platform,
            description          = description,
            about_company        = schema.about_company,
            job_type             = job_type_list,
            poster_type          = poster_type,
            recruiter            = recruiter or (
                RecruiterInfo(
                    name        = getattr(raw, "recruiter_name", None),
                    profile_url = getattr(raw, "recruiter_link", None),
                ) if getattr(raw, "recruiter_name", None) else None
            ),
            posted_at_text = getattr(raw, "posted_at_text", None),
        )
    except Exception as e:
        logger.warning("[job_parser] Failed to build Job object: %s", e)
        return None


def _strip_markdown_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
