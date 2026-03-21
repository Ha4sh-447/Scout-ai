import asyncio
import logging
import os

from mistralai.client import Mistral

from agents.messaging.state import MessagingState
from models.resume import MatchedJob

logger = logging.getLogger(__name__)

_client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

_CONCURRENCY = 5

# System prompts 

_EMAIL_SYSTEM_PROMPT = """You are a professional career coach helping someone write cold outreach emails to recruiters.

Write a concise, personalized cold email (max 120 words) that:
- Opens with a specific hook about the role or company (not generic)
- Highlights 2-3 relevant skills that match the job
- Ends with a clear, low-friction call to action
- Sounds human and direct — not like a template

Return ONLY the email body text. No subject line, no placeholders like [Your Name].
Sign off with just "Best," on its own line."""

_LINKEDIN_SYSTEM_PROMPT = """You are a professional career coach helping someone write LinkedIn connection request messages.

Write a concise LinkedIn connection message (STRICT MAX 280 characters) that:
- Mentions the specific role or company by name
- States one concrete reason to connect (a relevant skill or shared interest)
- Ends with a natural, non-pushy invitation to connect
- Reads like a real person wrote it, not a template

Return ONLY the message text. No greeting like "Hi [Name]", no placeholders.
The recipient's name will be added separately."""


async def messaging_node(state: MessagingState) -> dict:
    jobs           = state.get("ranked_jobs", [])
    user_id        = state["user_id"]

    needs_outreach = [j for j in jobs if _detect_contact_type(j) is not None]
    no_outreach    = [j for j in jobs if _detect_contact_type(j) is None]

    logger.info(
        f"[messaging_node] {len(needs_outreach)} jobs have actionable contact info "
        f"({len(no_outreach)} don't) for user {user_id}"
    )

    if not needs_outreach:
        return {"jobs_with_drafts": jobs, "status": "messaging_done"}

    semaphore = asyncio.Semaphore(_CONCURRENCY)
    errors: list[str] = []

    async def draft_one(job: MatchedJob) -> None:
        async with semaphore:
            try:
                await _draft_for_job(job, job.resume_summary or "")
            except Exception as e:
                errors.append(f"Draft failed for {job.source_url}: {e}")
                logger.warning(f"[messaging_node] Draft failed for {job.title}: {e}")

    await asyncio.gather(*[draft_one(j) for j in needs_outreach])

    email_count    = sum(1 for j in needs_outreach if j.outreach_email_draft)
    linkedin_count = sum(1 for j in needs_outreach if j.outreach_linkedin_draft)
    logger.info(
        f"[messaging_node] Drafted {email_count} emails, "
        f"{linkedin_count} LinkedIn messages"
    )

    all_jobs = needs_outreach + no_outreach
    all_jobs.sort(key=lambda j: j.rank)

    logger.info(f"[messaging_node] Returning {len(all_jobs)} total jobs in jobs_with_drafts")
    return {
        "jobs_with_drafts": all_jobs,
        "errors": errors,
        "status": "messaging_done",
    }

def _detect_contact_type(job: MatchedJob) -> str | None:
    """
    Returns the contact channel to use, in priority order:
        "email"    — recruiter has an email address
        "linkedin" — recruiter has a LinkedIn or profile URL
        None       — no actionable contact channel (name only, or no recruiter)
    """
    if not job.recruiter:
        return None

    r = job.recruiter

    if r.get("email"):
        return "email"

    if r.get("linkedin_url") or r.get("profile_url"):
        return "linkedin"

    return None

async def _draft_for_job(job: MatchedJob, resume_summary: str) -> None:
    """
    Detects contact type and calls the right draft function.
    Sets outreach_email_draft or outreach_linkedin_draft on the job in-place.
    A job could have both email AND linkedin_url — drafts both in that case.
    """
    r = job.recruiter or {}
    recruiter_name = r.get("name") or "the recruiter"

    skills_str = (
        ", ".join(job.top_matching_skills[:4])
        if job.top_matching_skills
        else ", ".join(job.skills[:4])
    )

    if r.get("email"):
        job.outreach_email_draft = await _draft_email(
            job, recruiter_name, skills_str, resume_summary
        )

    if r.get("linkedin_url") or r.get("profile_url"):
        job.outreach_linkedin_draft = await _draft_linkedin_message(
            job, recruiter_name, skills_str, resume_summary
        )

async def _draft_email(
    job: MatchedJob,
    recruiter_name: str,
    skills_str: str,
    resume_summary: str,
) -> str:
    user_prompt = f"""Draft a cold outreach email for this job opportunity:

Role: {job.title} at {job.company}
Recruiter: {recruiter_name}
Top matching skills: {skills_str}
Location: {job.location}

My background:
{resume_summary}

Write the email body only."""

    response = await _client.chat.complete_async(
        model="mistral-small-latest",
        max_tokens=300,
        messages=[
            {"role": "system", "content": _EMAIL_SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()


async def _draft_linkedin_message(
    job: MatchedJob,
    recruiter_name: str,
    skills_str: str,
    resume_summary: str,
) -> str:
    user_prompt = f"""Write a LinkedIn connection request message for this opportunity:

Role: {job.title} at {job.company}
Top matching skills: {skills_str}
My background (one sentence): {resume_summary.split('.')[0]}.

STRICT LIMIT: 280 characters total. Count carefully."""

    response = await _client.chat.complete_async(
        model="mistral-small-latest",
        max_tokens=100,
        messages=[
            {"role": "system", "content": _LINKEDIN_SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
    )

    draft = response.choices[0].message.content.strip()

    if len(draft) > 280:
        draft = draft[:277].rstrip() + "..."

    return draft
