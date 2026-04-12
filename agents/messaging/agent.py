"""messaging/agent.py"""
import asyncio
import logging
import os

from agents.messaging.state import MessagingState
from core.llm_router import get_router
from core.llm_sanitizer import sanitize_resume_summary
from models.resume import MatchedJob

logger = logging.getLogger(__name__)

_CONCURRENCY = 5


_EMAIL_SYSTEM_PROMPT = """\
You are a professional career coach writing cold outreach emails to recruiters.

Write a concise, personalized cold email (STRICT MAX 120 words) that:
- Opens with a specific hook about the role or company (never generic)
- Highlights 2-3 relevant skills matching the job
- Ends with a clear, low-friction call to action
- Sounds human and direct — not templated

Return ONLY the email body. No subject. No placeholders like [Your Name].
Sign off with just "Best," on its own line.

EXAMPLE OUTPUT (use this tone and length, not this exact text):
---
Hi Sarah,

I noticed Stripe is expanding its distributed infrastructure team — the Kafka-based
pipeline work caught my attention. I've spent the past two years building exactly that:
async event processors handling 50K msg/sec at my current role, using Python and Go.

Would love to explore if there's a fit. Happy to share a portfolio or jump on a 20-min call.

Best,
---
"""

_LINKEDIN_SYSTEM_PROMPT = """\
You are a professional career coach writing LinkedIn connection request messages.

Write a connection message (STRICT MAX 280 characters — count carefully) that:
- Names the specific role or company
- States one concrete reason to connect (a relevant skill or shared interest)
- Ends with a natural, non-pushy invitation
- Reads like a real person, not a template

Return ONLY the message. No placeholder like "Hi [Name]".

EXAMPLE OUTPUT (255 chars):
"Came across the Backend Engineer role at Stripe — your work on distributed systems
caught my eye. I've built async data pipelines at scale with Kafka+Python. Would love
to connect and learn more!"
"""


async def messaging_node(state: MessagingState) -> dict:
    jobs    = state.get("ranked_jobs", [])
    user_id = state["user_id"]

    needs_outreach = [j for j in jobs if _detect_contact_type(j) is not None]
    no_outreach    = [j for j in jobs if _detect_contact_type(j) is None]

    logger.info(
        "[messaging_node] %d jobs have contact info for user %s",
        len(needs_outreach), user_id
    )

    if not needs_outreach:
        return {"jobs_with_drafts": jobs, "status": "messaging_done"}

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    router    = await get_router(redis_url)

    semaphore = asyncio.Semaphore(_CONCURRENCY)
    errors: list[str] = []

    async def draft_one(job: MatchedJob) -> None:
        async with semaphore:
            try:
                await _draft_for_job(job, job.resume_summary or "", router, user_id)
            except Exception as e:
                errors.append(f"Draft failed for {job.source_url}: {e}")
                logger.warning("[messaging_node] Draft failed for %s: %s", job.title, e)

    await asyncio.gather(*[draft_one(j) for j in needs_outreach])

    email_count    = sum(1 for j in needs_outreach if j.outreach_email_draft)
    linkedin_count = sum(1 for j in needs_outreach if j.outreach_linkedin_draft)
    logger.info(
        "[messaging_node] Drafted %d emails, %d LinkedIn messages",
        email_count, linkedin_count
    )

    all_jobs = needs_outreach + no_outreach
    all_jobs.sort(key=lambda j: j.rank)
    return {"jobs_with_drafts": all_jobs, "errors": errors, "status": "messaging_done"}



def _detect_contact_type(job: MatchedJob) -> str | None:
    if not job.recruiter:
        return None
    r = job.recruiter
    if r.get("email"):
        return "email"
    if r.get("linkedin_url") or r.get("profile_url"):
        return "linkedin"
    return None


async def _draft_for_job(
    job: MatchedJob, resume_summary: str, router, user_id: str
) -> None:
    r              = job.recruiter or {}
    recruiter_name = r.get("name") or "the recruiter"
    safe_summary   = sanitize_resume_summary(resume_summary)

    skills_str = (
        ", ".join(job.top_matching_skills[:4])
        if job.top_matching_skills
        else ", ".join(job.skills[:4])
    )

    if r.get("email"):
        job.outreach_email_draft = await _draft_email(
            job, recruiter_name, skills_str, safe_summary, router, user_id
        )

    if r.get("linkedin_url") or r.get("profile_url"):
        job.outreach_linkedin_draft = await _draft_linkedin_message(
            job, recruiter_name, skills_str, safe_summary, router, user_id
        )


async def _draft_email(
    job: MatchedJob, recruiter_name: str,
    skills_str: str, resume_summary: str,
    router, user_id: str,
) -> str:
    user_prompt = (
        f"<job_context>\n"
        f"Role: {job.title} at {job.company}\n"
        f"Recruiter: {recruiter_name}\n"
        f"Top matching skills: {skills_str}\n"
        f"Location: {job.location}\n"
        f"</job_context>\n\n"
        f"<candidate_background>\n"
        f"{resume_summary}\n"
        f"</candidate_background>\n\n"
        f"Write the email body only."
    )

    return await router.complete(
        system       = _EMAIL_SYSTEM_PROMPT,
        user_content = user_prompt,
        user_id      = user_id,
        cache_key    = f"email:{job.source_url}",
        max_tokens   = 300,
    )


async def _draft_linkedin_message(
    job: MatchedJob, recruiter_name: str,
    skills_str: str, resume_summary: str,
    router, user_id: str,
) -> str:
    bg_sentence = resume_summary.split(".")[0] + "." if resume_summary else ""

    user_prompt = (
        f"<job_context>\n"
        f"Role: {job.title} at {job.company}\n"
        f"Top matching skills: {skills_str}\n"
        f"</job_context>\n\n"
        f"<candidate_background>\n"
        f"{bg_sentence}\n"
        f"</candidate_background>\n\n"
        f"STRICT LIMIT: 280 characters total. Count carefully."
    )

    draft = await router.complete(
        system       = _LINKEDIN_SYSTEM_PROMPT,
        user_content = user_prompt,
        user_id      = user_id,
        cache_key    = f"linkedin:{job.source_url}",
        max_tokens   = 100,
    )

    if len(draft) > 280:
        draft = draft[:277].rstrip() + "..."

    return draft
