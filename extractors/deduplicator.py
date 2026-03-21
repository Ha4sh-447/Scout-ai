import hashlib
import json
import re

from mistralai.client.sdk import Mistral

from models.jobs import Job


def compute_content_hash(job: Job) -> str:
    """
    Create a fingerprint from title + company + location.
    Used for exact deduplication (same job posted twice).
    """
    fingerprint = f"{job.title.lower().strip()}|{job.company.lower().strip()}|{job.location.lower().strip()}"
    return hashlib.md5(fingerprint.encode()).hexdigest()


def deduplicate_jobs(
    jobs: list[Job], seen_hashes: set[str] | None = None
) -> tuple[list[Job], set[str]]:
    """
    Remove duplicate jobs from a list.

    Args:
        jobs: list of parsed Job objects
        seen_hashes: optional set of hashes already processed in previous runs
                     (pass from Redis cache in production)

    Returns:
        (unique_jobs, updated_seen_hashes)
    """
    if seen_hashes is None:
        seen_hashes = set()

    unique = []

    for job in jobs:
        content_hash = compute_content_hash(job)
        job.content_hash = content_hash

        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique.append(job)

    return unique, seen_hashes


def deduplicate_within_batch(jobs: list[Job]) -> list[Job]:
    """
    Simpler version — just dedup within a single batch, no external state.
    Good for the graph node where you don't have Redis yet.
    """
    unique, _ = deduplicate_jobs(jobs)
    return unique


async def semantic_deduplicate(jobs: list[Job]) -> list[Job]:
    """
    Use Mistral to catch near-duplicates that hash-based dedup misses.
    """
    if len(jobs) <= 1:
        return jobs
    client = Mistral() 

    job_summaries = "\n".join(
        f"{i}. {j.title} at {j.company} ({j.location}) — {j.source_url}"
        for i, j in enumerate(jobs)
    )

    prompt = f"""Given these job listings, identify which ones are duplicates of each other (same role at same company).

{job_summaries}

Return a JSON array of arrays, where each inner array contains the indices of duplicate jobs.
Only include groups with 2+ duplicates. If no duplicates, return [].
Example: [[0, 3], [1, 5, 7]] means jobs 0&3 are duplicates, and 1, 5 & 7 are duplicates.
Return raw JSON only."""

    try:
        response = await client.chat.complete_async(
            model="mistral-small-latest",  
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=512,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        parsed = json.loads(raw)

        if isinstance(parsed, dict):
            duplicate_groups: list[list[int]] = next(iter(parsed.values()))
        else:
            duplicate_groups = parsed

        indices_to_remove = set()
        for group in duplicate_groups:
            indices_to_remove.update(group[1:])  

        return [j for i, j in enumerate(jobs) if i not in indices_to_remove]

    except Exception:
        return jobs
