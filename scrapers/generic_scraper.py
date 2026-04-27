"""generic_scraper.py"""

import json
import logging
import os
import re
import asyncio
import random
from urllib.parse import urlparse
from urllib.parse import urljoin

from playwright.async_api import Page

from models.jobs import RawJobData
from tools.browser.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

_GENERIC_LLM_MAX_RETRIES = 4


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg and "limit" in msg:
        return True
    status_code = getattr(exc, "status_code", None)
    return status_code == 429


def _infer_generic_platform(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    if not host:
        return "generic"

    host = re.sub(r"^(www\.|m\.|jobs\.|careers\.)", "", host)
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "edu"}:
        site = parts[-3]
    elif len(parts) >= 2:
        site = parts[-2]
    else:
        site = parts[0]

    site = re.sub(r"[^a-z0-9]+", "_", site).strip("_")
    return site or "generic"

NAV_EXCLUSIONS = {
    "student", "employer", "login", "register", "signup", "about us", "contact us", "terms", "privacy",
    "rules", "company", "companies", "hire", "post job", "recruiter", "pricing", "help", "blog", "careers",
    "view and apply", "learn more", "sign in", "join now", "register now", "compliance", "internships",
    "internship", "jobs", "job", "dashboard", "profile", "settings", "notifications", "support", "help center"
}

_GENERIC_TITLE_BLOCKLIST = {
    "student", "students", "employer", "employers", "about us", "contact us", "privacy",
    "terms", "login", "log in", "sign in", "signup", "sign up", "register", "dashboard",
    "profile", "settings", "notifications", "support", "help", "blog", "careers"
}

LISTING_SPLITTER_PROMPT = """You are a job listing page analyzer. Given the text content and candidate links from a job listing webpage, extract each individual job posting.

Return a JSON object with a "jobs" key containing an array. Each element should have:
{
  "jobs": [
    {
      "title": "job title",
      "company": "company name",
      "location": "location or Remote",
      "description": "brief description of the role (2-3 sentences max)",
      "source_url": "best matching job URL if present, else null"
    }
  ]
}

Rules:
- Extract ONLY actual job postings.
- CRITICAL: Skip navigation links, user menu items, footer links, and page boilerplate (e.g., "Student", "Fresher", "Company", "Register", "Login", "About Us").
- If the title is just a single generic word like "Student", "Employer", or "Internal", it is NOT a job.
- If the page contains no job postings, return {"jobs": []}
- Extract at most 30 jobs
- Use provided candidate links to map each posting to a likely source_url whenever possible
- Return raw JSON only, no markdown fences or explanations"""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _normalize_job_url(base_url: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    cleaned = maybe_url.strip()
    if not cleaned:
        return None
    if cleaned.startswith("javascript:"):
        return None
    return urljoin(base_url, cleaned)


def _fallback_job_url(base_url: str, idx: int, title: str, company: str) -> str:
    title_slug = _slugify(title) or f"job-{idx + 1}"
    company_slug = _slugify(company)
    suffix = f"{title_slug}-{company_slug}" if company_slug else title_slug
    return f"{base_url}#job-{idx + 1}-{suffix}"


def _is_viable_title(title: str) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return False
    if t in _GENERIC_TITLE_BLOCKLIST:
        return False
    if len(t) < 4:
        return False
    if len(t.split()) < 2:
        return False
    if re.search(r"\b(job|intern|engineer|developer|scientist|analyst|manager|designer|consultant|specialist|architect|lead)\b", t):
        return True
    return len(t.split()) >= 3


def _is_blocked_candidate_url(base_url: str, href: str | None) -> bool:
    href_l = (href or "").strip().lower()
    if not href_l:
        return False

    blocked_substrings = [
        "trainings.internshala.com",
        "utm_source=is_web_internshala-menu-dropdown",
        "utm_source=is_web_job-menu-dropdown",
        "utm_source=is_web_internship-menu-dropdown",
        "/registration/",
        "/login/get_google",
        "/terms",
        "/privacy",
    ]
    if any(s in href_l for s in blocked_substrings):
        return True

    base_host = (urlparse(base_url).hostname or "").lower()
    if "internshala.com" in base_host:
        return not ("/internship/detail/" in href_l or "/job/detail/" in href_l)

    return False


def _is_internshala_listing_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    path = (urlparse(url).path or "").lower()
    return "internshala.com" in host and ("/internships" in path or "/jobs" in path)


async def _dismiss_listing_popups(page: Page) -> None:
    """Best-effort dismissal of signup/offer overlays that hide job cards."""
    close_selectors = [
        "[role='dialog'] button[aria-label*='close' i]",
        "[role='dialog'] [class*='close' i]",
        ".modal button[aria-label*='close' i]",
        ".modal [class*='close' i]",
        ".popup [class*='close' i]",
        ".overlay [class*='close' i]",
        "button[aria-label='Close']",
        "button[title='Close']",
    ]

    for selector in close_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.count() > 0:
                await btn.click(timeout=1200)
                await page.wait_for_timeout(250)
        except Exception:
            continue

    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)
    except Exception:
        pass


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
        await _dismiss_listing_popups(page)

        # Scroll once to trigger lazy-loaded cards on infinite-scroll portals.
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        page_text = await page.inner_text("body")
        internshala_mode = _is_internshala_listing_url(url)

        candidate_links = await page.evaluate(
            f"""
                        (payload) => {{
                            const navExclusions = payload?.navExclusions || [];
                            const internshalaMode = !!payload?.internshalaMode;
                            const roleSuffixes = [
                                "engineer", "developer", "scientist", "analyst", "manager", "designer",
                                "consultant", "specialist", "architect", "lead", "intern", "internship"
                            ];
                            const rolePrefixes = ["senior", "sr", "junior", "jr", "staff", "principal", "associate", "ai", "ml", "software", "data"];
              const anchors = Array.from(document.querySelectorAll('a[href]'));
                            const cardNodes = Array.from(document.querySelectorAll(
                                'article, [data-job-id], [data-jobid], .job-card, .job_card, .job-listing, .job-listing-card, .job-list-item, .job-item, .position, .opening, .opportunity, .individual_internship, .internship_meta'
                            ));
              const out = [];
              const seen = new Set();
              const domainToken = window.location.hostname.split('.').reverse()[1] || '';

                            if (internshalaMode) {{
                                const detailAnchors = Array.from(document.querySelectorAll('a[href*="/internship/detail/"], a[href*="/job/detail/"]'));
                                for (const a of detailAnchors) {{
                                    const href = a.getAttribute('href') || '';
                                    if (!href || href.startsWith('javascript:')) continue;
                                    if (a.closest('header,nav,footer,[role="dialog"],.modal,.popup,.overlay')) continue;

                                    const text = (a.textContent || '').trim();
                                    const row = (a.closest('article,li,section,div')?.textContent || '').trim().slice(0, 380);
                                    const key = `${{href}}::${{text}}`;
                                    if (seen.has(key)) continue;
                                    seen.add(key);

                                    out.push({{ href, text: text.slice(0, 140), snippet: row }});
                                    if (out.length >= 60) break;
                                }}
                            }}
              
                            const normalize = (s) => (s || '').toLowerCase().replace(/\s+/g, ' ').trim();
                            const isRoleLikeTitle = (s) => {{
                                const lower = normalize(s);
                                if (!lower) return false;
                                const words = lower.split(' ').filter(Boolean);
                                if (words.length < 2) return false;

                                const hasSuffix = roleSuffixes.some((suffix) => words.includes(suffix) || lower.endsWith(' ' + suffix));
                                const hasPrefix = rolePrefixes.some((prefix) => words.includes(prefix));

                                if (hasSuffix) return true;
                                return hasPrefix && words.length >= 3;
                            }};

              // Only consider 'intern' a keyword if it's NOT just part of the domain name
              const looksLikeJob = (s, href) => {{
                if (!s) return false;
                const lower = s.toLowerCase();
                
                // Exclude common navigation terms
                if (navExclusions.some(term => lower === term || lower.includes(" " + term) || lower.startsWith(term + " "))) {{
                    return false;
                }}

                const keywords = ["job", "intern", "opportunit", "opening", "position", "career", "vacanc", "apply"];
                
                // If the only match is 'intern' and it's also in the domain name, be more skeptical
                const hasKeyword = keywords.some(k => lower.includes(k));
                const hasJobishHref = /\/job(s)?\b|\/intern(ship|ships)?\b|\/careers?\b|\/opening(s)?\b|\/position(s)?\b/.test((href || '').toLowerCase());
                const hasRoleTitle = isRoleLikeTitle(lower);
                if (!hasKeyword && !hasJobishHref && !hasRoleTitle) return false;
                
                if (lower.includes("intern") && domainToken.includes("intern") && !keywords.some(k => k !== "intern" && lower.includes(k))) {{
                    // If 'intern' is the only keyword and it matches domain, check if it's just 'internshala'
                    if (href.includes(domainToken) && !lower.includes("ship") && !lower.includes(" engineer") && !lower.includes(" developer")) {{
                        return false;
                    }}
                }}
                
                return true;
              }};

              for (const a of anchors) {{
                                if (out.length >= 40) break;
                const href = a.getAttribute('href') || '';
                const text = (a.textContent || '').trim();
                const row = (a.closest('li,article,div,section')?.textContent || '').trim().slice(0, 320);
                if (!href || href.startsWith('javascript:')) continue;

                                // Ignore links from global chrome/popups where job ads and CTAs live.
                                if (a.closest('header,nav,footer,[role="dialog"],.modal,.popup,.overlay')) continue;

                const combined = `${{href}} ${{text}} ${{row}}`;
                if (!looksLikeJob(combined, href)) continue;

                const key = `${{href}}::${{text}}`;
                if (seen.has(key)) continue;
                seen.add(key);

                out.push({{ href, text: text.slice(0, 120), snippet: row }});
                if (out.length >= 40) break;
              }}

                            // Card-first fallback for sites with JS-routed listings and weak anchor text.
                            for (const card of cardNodes) {{
                                if (out.length >= 40) break;
                                const heading = card.querySelector('h1,h2,h3,h4,[data-testid*="title"],.title,.job-title,.profile') || null;
                                const primaryLink = card.querySelector('a[href]') || null;

                                const title = normalize((heading?.textContent || primaryLink?.textContent || '').trim()).slice(0, 140);
                                const href = primaryLink?.getAttribute('href') || '';
                                const snippet = normalize((card.textContent || '').trim()).slice(0, 500);

                                if (!snippet || snippet.length < 40) continue;
                                if (!isRoleLikeTitle(title) && !looksLikeJob(`${{title}} ${{snippet}}`, href)) continue;

                                const key = `${{href || 'nohref'}}::${{title}}`;
                                if (seen.has(key)) continue;
                                seen.add(key);

                                out.push({{
                                    href,
                                    text: title || (primaryLink?.textContent || '').trim().slice(0, 120),
                                    snippet,
                                }});
                            }}

              return out;
            }}
            """,
                        {
                                "navExclusions": list(NAV_EXCLUSIONS),
                                "internshalaMode": internshala_mode,
                        },
        )

        if candidate_links and len(candidate_links) >= 2:
            raw_jobs = []
            source_platform = _infer_generic_platform(url)
            for idx, c in enumerate(candidate_links[:30]):
                title = (c.get("text") or "").strip()
                if not _is_viable_title(title) or title.lower() in NAV_EXCLUSIONS:
                    continue

                snippet = (c.get("snippet") or "").strip()
                if not snippet or len(snippet) < 30:
                    continue

                job_url = _normalize_job_url(url, c.get("href")) or _fallback_job_url(url, idx, title, "")
                if _is_blocked_candidate_url(url, job_url):
                    continue

                raw_text = (
                    f"Job Title: {title}\n"
                    f"Description: {snippet}\n"
                    f"Source: {job_url}"
                )

                raw_jobs.append(
                    RawJobData(
                        source_url=job_url,
                        source_platform=source_platform,
                        raw_text=raw_text,
                        raw_html=None,
                    )
                )

            await page.close()
            logger.info(
                f"[generic_scraper] Heuristic extraction identified {len(raw_jobs)} job-like links from {url}"
            )
            return raw_jobs, errors

        await page.close()

        if not page_text or len(page_text) < 100:
            errors.append(f"No meaningful content extracted from {url}")
            return [], errors

        page_text = page_text[:12000]
        candidate_links_json = json.dumps(candidate_links[:30] if candidate_links else [], ensure_ascii=True)

        logger.info(
            f"[generic_scraper] Extracted {len(page_text)} chars from {url}, candidate_links={len(candidate_links or [])}, sending to LLM"
        )

        client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

        response = None
        last_llm_error: Exception | None = None
        for attempt in range(1, _GENERIC_LLM_MAX_RETRIES + 1):
            try:
                response = await client.chat.complete_async(
                    model="mistral-large-latest",
                    max_tokens=4096,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": LISTING_SPLITTER_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Extract job postings from this page:\n\n"
                                f"URL: {url}\n\n"
                                f"Candidate links JSON:\n{candidate_links_json}\n\n"
                                f"Page text:\n{page_text}"
                            ),
                        },
                    ],
                )
                break
            except Exception as e:
                last_llm_error = e
                if _is_rate_limit_error(e) and attempt < _GENERIC_LLM_MAX_RETRIES:
                    delay = (2 ** (attempt - 1)) + random.uniform(0.4, 1.2)
                    logger.warning(
                        f"[generic_scraper] Rate-limited by LLM on attempt {attempt}/{_GENERIC_LLM_MAX_RETRIES} for {url}; retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        if response is None:
            raise RuntimeError(f"LLM returned no response for {url}: {last_llm_error}")

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
        source_platform = _infer_generic_platform(url)

        raw_jobs = []
        for idx, job in enumerate(jobs_list):
            title = job.get("title") or "Unknown Title"
            company = job.get("company") or "Unknown"
            location = job.get("location") or "Unknown"
            description = job.get("description") or ""
            job_url = _normalize_job_url(url, job.get("source_url")) or _fallback_job_url(url, idx, title, company)

            raw_text = (
                f"Job Title: {title}\n"
                f"Company: {company}\n"
                f"Location: {location}\n"
                f"Description: {description}\n"
                f"Source: {job_url}"
            )

            raw_jobs.append(
                RawJobData(
                    source_url=job_url,
                    source_platform=source_platform,
                    raw_text=raw_text,
                    raw_html=None,
                )
            )

        return raw_jobs, errors

    except json.JSONDecodeError as e:
        errors.append(f"LLM returned invalid JSON for {url}: {e}")
        return [], errors
    except Exception as e:
        logger.error(f"[generic_scraper] Failed for {url}: {e}", exc_info=True)
        errors.append(f"Generic scraper failed for {url}: {e}")
        return [], errors
