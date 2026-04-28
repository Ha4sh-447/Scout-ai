"""listing_scraper.py"""

import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.async_api import Page

from models.jobs import RawJobData
from tools.browser.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

LINKEDIN_LISTING_RE = re.compile(r"https?://(www\.)?linkedin\.com/jobs/")
INDEED_LISTING_RE = re.compile(r"https?://(www\.|[a-z]{2}\.)?indeed\.(com|co\.\w+)")
GLASSDOOR_LISTING_RE = re.compile(r"https?://(www\.)?glassdoor\.(com|co\.\w+)")


def is_linkedin_listing(url: str) -> bool:
    return bool(LINKEDIN_LISTING_RE.match(url))


def is_indeed_listing(url: str) -> bool:
    return bool(INDEED_LISTING_RE.match(url))


def is_glassdoor_listing(url: str) -> bool:
    return bool(GLASSDOOR_LISTING_RE.match(url))


def is_single_job_url(url: str) -> bool:
    """Check if the URL is an individual job posting (not a search/listing page)."""
    if "linkedin.com/jobs/view/" in url or "currentJobId=" in url:
        return True
    if "indeed" in url and ("viewjob" in url or "rc/clk" in url or "vjcmp" in url):
        return True
    if "glassdoor" in url and ("jobListing.htm" in url or "partner/jobListing.htm" in url):
        return True
    return False


def is_known_listing(url: str) -> bool:
    if is_single_job_url(url):
        return False
    return is_linkedin_listing(url) or is_indeed_listing(url) or is_glassdoor_listing(url)


def _url_contains_query_terms(url: str, query: str) -> bool:
    """Return True when URL already appears to encode the requested search intent."""
    q = (query or "").strip().lower()
    if not q:
        return True

    decoded_url = (url or "").lower().replace("+", " ").replace("%20", " ")
    tokens = [t for t in re.split(r"\W+", q) if len(t) > 2]
    if not tokens:
        return q in decoded_url

    hits = sum(1 for t in tokens if t in decoded_url)
    required = max(1, len(tokens) // 2)
    return hits >= required


def _set_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[key] = [value]
    new_query = urlencode(params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _normalize_linkedin_url(url: str, query: str = "", freshness: str = "default") -> str:
    """
    Convert any LinkedIn jobs URL to the public guest search endpoint or respect auth collections.
    Includes freshness filters: f_TPR=r604800 (past week), f_TPR=r86400 (past 24h)
    """
    freshness_map = {
        "past_week": "&f_TPR=r604800",
        "past_24h": "&f_TPR=r86400",
        "default": ""
    }
    suffix = freshness_map.get(freshness, "")

    if "/jobs/collections/" in url or (url.endswith("/jobs/") and not query):
        return url

    if "/jobs/search/" in url and "keywords=" in url:
        if query and not _url_contains_query_terms(url, query):
            url = _set_query_param(url, "keywords", query)

        if "f_TPR=" not in url and suffix:
            joiner = "&" if "?" in url else "?"
            return url + joiner + suffix.lstrip("&")
        return url

    encoded = query.replace(" ", "+")
    return f"https://www.linkedin.com/jobs/search/?keywords={encoded}&location=India{suffix}"


def _normalize_indeed_url(url: str, query: str = "") -> str:
    """Convert Indeed homepage to a search URL if needed."""
    if "/jobs" in url and "q=" in url:
        if query and not _url_contains_query_terms(url, query):
            return _set_query_param(url, "q", query)
        return url
    match = re.match(r"(https?://[^/]+)", url)
    domain = match.group(1) if match else "https://in.indeed.com"
    encoded = query.replace(" ", "+")
    return f"{domain}/jobs?q={encoded}"


def _broaden_indeed_query(query: str) -> str:
    """Broaden terse/abbreviated queries that often return zero results on Indeed."""
    if not query:
        return query

    widened = query
    substitutions = [
        (r"\bswe\b", "software engineer"),
        (r"\bml\b", "machine learning"),
        (r"\bai\b", "artificial intelligence"),
        (r"\bintern\b", "internship"),
        (r"\bdev\b", "developer"),
    ]
    for pattern, replacement in substitutions:
        widened = re.sub(pattern, replacement, widened, flags=re.IGNORECASE)

    widened = re.sub(r"\s+", " ", widened).strip()
    return widened


def _normalize_glassdoor_url(url: str, query: str = "") -> str:
    """Convert Glassdoor index to a search URL if needed."""
    if "SRCH" in url or "jobs-SRCH" in url:
        if query and "sc.keyword=" in url and not _url_contains_query_terms(url, query):
            return _set_query_param(url, "sc.keyword", query)
        return url
    match = re.match(r"(https?://[^/]+)", url)
    domain = match.group(1) if match else "https://www.glassdoor.co.in"
    encoded = query.replace(" ", "+")
    return f"{domain}/Job/jobs.htm?sc.keyword={encoded}"







async def _safe_query_selector_all(page: Page, selector: str, max_retries: int = 2) -> list:
    """Query elements safely, handling 'Execution context was destroyed' errors."""
    for i in range(max_retries + 1):
        try:
            return await page.query_selector_all(selector)
        except Exception as e:
            if "destroyed" in str(e).lower() and i < max_retries:
                logger.warning(f"[listing_scraper] Navigation interrupted query for '{selector}', retrying ({i+1}/{max_retries})...")
                await page.wait_for_timeout(1000)
                continue
            raise e


async def _is_cloudflare_challenge(page: Page) -> bool:
    """Detect common Cloudflare interstitials that block scraping."""
    try:
        title = (await page.title()).lower()
    except Exception:
        title = ""

    try:
        body = (await page.evaluate("document.body.innerText.substring(0, 2000)")).lower()
    except Exception:
        body = ""

    signals = [
        "just a moment",
        "cloudflare",
        "additional verification required",
        "ray id",
        "checking your browser",
    ]
    haystack = f"{title}\n{body}"
    return any(s in haystack for s in signals)


async def _extract_linkedin_cards(page: Page, max_cards: int = 30) -> tuple[list[dict], bool]:
    """
    Extract job cards from LinkedIn search page.
    Returns (cards, is_guest_mode).
    Supports both guest/public view (.base-card) and authenticated view
    (scaffold-layout job cards) with automatic detection.
    """
    current_url = page.url
    page_title = await page.title()
    logger.info(f"[listing_scraper] LinkedIn page loaded: title='{page_title}', url={current_url}")

    try:
        await page.wait_for_load_state("load", timeout=5000)
    except:
        pass

    for attempt in range(2):
        try:
            cookies = await page.context.cookies()
            has_cookies = any("linkedin.com" in c["domain"] for c in cookies)
            if has_cookies:
                logger.info(f"[listing_scraper] LinkedIn: Session detected ({len(cookies)} cookies), waiting for AUTH view...")
                try:
                    await page.wait_for_selector("li.scaffold-layout__list-item .job-card-container, div.job-card-container", timeout=8000)
                except:
                    pass

            auth_cards = await _safe_query_selector_all(
                page,
                "li.scaffold-layout__list-item .job-card-container, "
                "li.jobs-search-results__list-item, "
                "div.job-card-container, "
                "li.scaffold-layout__list-item"
            )

            auth_cards = await _safe_query_selector_all(
                page,
                "li.scaffold-layout__list-item .job-card-container, "
                "li.jobs-search-results__list-item, "
                "div.job-card-container, "
                "li.scaffold-layout__list-item"
            )

            if auth_cards:
                logger.info(f"[listing_scraper] LinkedIn: detected AUTH view ({len(auth_cards)} job-card elements)")
                
                try:
                    list_el = await page.query_selector(".jobs-search-results-list, [data-test-results-container]")
                    if list_el:
                        logger.info("[listing_scraper] LinkedIn: Scrolling to load more jobs...")
                        for _ in range(3):
                            await list_el.evaluate("el => el.scrollTop = el.scrollHeight")
                            await page.wait_for_timeout(1000)
                        auth_cards = await _safe_query_selector_all(page, "li.scaffold-layout__list-item .job-card-container, li.jobs-search-results__list-item")
                        logger.info(f"[listing_scraper] LinkedIn: after scroll found {len(auth_cards)} jobs")
                except Exception as scroll_err:
                    logger.warning(f"[listing_scraper] Scroll failed: {scroll_err}")

                return await _extract_linkedin_auth_cards(auth_cards, max_cards), False

            cards = await _safe_query_selector_all(page, ".base-card")
            if cards:
                logger.info(f"[listing_scraper] LinkedIn: detected GUEST view ({len(cards)} .base-card elements)")
                return await _extract_linkedin_guest_cards(cards, max_cards), True

            job_links = await _safe_query_selector_all(page, 'a[href*="/jobs/view/"]')
            if job_links:
                logger.info(f"[listing_scraper] LinkedIn: fallback - found {len(job_links)} job links on page")
                return await _extract_linkedin_fallback_links(page, job_links, max_cards), True
            
            if attempt == 0:
                logger.info("[listing_scraper] LinkedIn: 0 cards found, waiting 3s for possible redirect/render...")
                await page.wait_for_timeout(3000)
                continue

        except Exception as e:
            if "destroyed" in str(e).lower() and attempt == 0:
                logger.warning(f"[listing_scraper] LinkedIn context destroyed during extraction, retrying... {e}")
                await page.wait_for_timeout(2000)
                continue
            logger.error(f"[listing_scraper] LinkedIn extraction error: {e}")
            break

    logger.warning(f"[listing_scraper] LinkedIn: 0 cards found with ALL selectors!")
    logger.warning(f"[listing_scraper] Page title: '{page_title}'")
    logger.warning(f"[listing_scraper] Final URL: {current_url}")
    try:
        body_text = await page.evaluate("document.body.innerText.substring(0, 1500)")
        logger.warning(f"[listing_scraper] Page body text (first 1500 chars):\n{body_text}")
    except Exception:
        pass
    try:
        html_snippet = await page.evaluate("document.body.innerHTML.substring(0, 3000)")
        logger.warning(f"[listing_scraper] Page HTML snippet (first 3000 chars):\n{html_snippet}")
    except Exception:
        pass

    return [], True


async def _extract_linkedin_guest_cards(cards, max_cards: int) -> list[dict]:
    """Extract from LinkedIn's public/guest search page (.base-card elements)."""
    results = []
    for card in cards[:max_cards]:
        link_el = await card.query_selector("a")
        href = (await link_el.get_attribute("href")) if link_el else None

        raw_text = (await card.inner_text()).strip()

        posted_at_el = await card.query_selector(
            ".job-search-card__listdate, .job-search-card__listdate--new, [datetime]"
        )
        posted_at_text = (await posted_at_el.inner_text()).strip() if posted_at_el else None

        if href and raw_text:
            href = href.split("?")[0]
            results.append({
                "link": href,
                "raw_text": raw_text,
                "posted_at_text": posted_at_text,
            })
    return results


async def _extract_linkedin_auth_cards(cards, max_cards: int) -> list[dict]:
    """Extract from LinkedIn's authenticated/logged-in job search view."""
    results = []
    for card in cards[:max_cards]:
        link_el = (
            await card.query_selector('a[href*="/jobs/view/"]')
            or await card.query_selector('a.job-card-container__link')
            or await card.query_selector('a.job-card-list__title')
            or await card.query_selector("a")
        )
        href = (await link_el.get_attribute("href")) if link_el else None

        raw_text = (await card.inner_text()).strip()

        posted_at_el = (
            await card.query_selector("time")
            or await card.query_selector('[class*="listed-at"], [class*="listdate"]')
            or await card.query_selector('[class*="time"]')
        )
        posted_at_text = None
        if posted_at_el:
            posted_at_text = await posted_at_el.get_attribute("datetime")
            if not posted_at_text:
                posted_at_text = (await posted_at_el.inner_text()).strip()

        if href and raw_text:
            if href.startswith("/"):
                href = "https://www.linkedin.com" + href
            href = href.split("?")[0]
            results.append({
                "link": href,
                "raw_text": raw_text,
                "posted_at_text": posted_at_text,
            })
    return results


async def _extract_linkedin_fallback_links(page: Page, job_links, max_cards: int) -> list[dict]:
    """Last-resort fallback: extract any /jobs/view/ links visible on page."""
    results = []
    seen_hrefs = set()
    for link in job_links[:max_cards]:
        href = await link.get_attribute("href")
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.linkedin.com" + href
        href = href.split("?")[0]
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        parent = await link.evaluate_handle("el => el.closest('li') || el.parentElement")
        raw_text = ""
        if parent:
            try:
                raw_text = (await parent.inner_text()).strip()
            except Exception:
                raw_text = (await link.inner_text()).strip()
        if not raw_text:
            raw_text = (await link.inner_text()).strip()

        if raw_text:
            results.append({
                "link": href,
                "raw_text": raw_text,
                "posted_at_text": None,
            })
    return results


async def _extract_indeed_cards(page: Page, max_cards: int = 30) -> list[dict]:
    """Extract job cards from Indeed search results."""
    selectors = [
        ".job_seen_beacon",
        "div[data-jk]",
        "div.jobsearch-SerpJobCard",
        "li div[data-testid='slider_item']",
        "main [data-testid='job-card']",
    ]

    cards = []
    for selector in selectors:
        cards = await page.query_selector_all(selector)
        if cards:
            logger.info(f"[listing_scraper] Indeed: matched {len(cards)} cards via selector '{selector}'")
            break

    if not cards:
        page_title = await page.title()
        current_url = page.url
        logger.warning(f"[listing_scraper] Indeed: 0 cards found. title='{page_title}', url={current_url}")
        try:
            body_preview = await page.evaluate("document.body.innerText.substring(0, 1500)")
            logger.warning(f"[listing_scraper] Indeed body text (first 1500 chars):\n{body_preview}")
        except Exception:
            pass
        return []

    results = []

    for card in cards[:max_cards]:
        link_el = (
            await card.query_selector(".jobTitle a")
            or await card.query_selector("a[data-jk]")
            or await card.query_selector("h2 a")
            or await card.query_selector("a[href*='/viewjob']")
        )

        href = (await link_el.get_attribute("href")) if link_el else None

        if href and href.startswith("/"):
            base = await page.evaluate("window.location.origin")
            href = base + href
            
        raw_text = (await card.inner_text()).strip()
        
        posted_at_el = await card.query_selector(".date, .myJobsState, [class*='date'], [class*='Date']")
        posted_at_text = (await posted_at_el.inner_text()).strip() if posted_at_el else None

        if href and raw_text:
            results.append({
                "link": href, 
                "raw_text": raw_text,
                "posted_at_text": posted_at_text
            })

    return results








async def _scrape_linkedin_job_details(page: Page, url: str) -> dict:
    """
    Visit a LinkedIn job page and extract recruiter info.
    
    Note: Recruiter contact info is typically only visible to authenticated users
    on LinkedIn. For guest users, we extract company info as a fallback.
    """
    import random
    await page.wait_for_timeout(random.randint(2000, 5000))
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await page.wait_for_timeout(1000)
        
        recruiter_name = None
        recruiter_email = None
        recruiter_link = None
        
        poster_el = await page.query_selector(".jobs-poster, .hirer-card__container")
        if poster_el:
            name_el = await poster_el.query_selector(".jobs-poster__name, .hirer-card__name, [class*='name']")
            if name_el:
                recruiter_name = (await name_el.inner_text()).strip()
            
            link_el = await poster_el.query_selector("a[href*='/in/']")
            if link_el:
                recruiter_link = await link_el.get_attribute("href")
            
            if recruiter_name:
                logger.info(f"[LinkedIn recruiter] Found via Strategy 0 (poster card): {recruiter_name}")

        posted_by_el = await page.query_selector("a[href*='/in/'][href*='miniProfile']")
        if not posted_by_el:
            posted_by_el = await page.query_selector("[class*='show-more-less-html__markup'] a[href*='/in/']")
        
        if posted_by_el:
            recruiter_name = (await posted_by_el.inner_text()).strip()
            recruiter_link = await posted_by_el.get_attribute("href")
            if recruiter_link and recruiter_link.startswith("/"):
                recruiter_link = "https://www.linkedin.com" + recruiter_link
            logger.info(f"[LinkedIn recruiter] Found via Strategy 1 (Posted by): {recruiter_name}")
        
        if not recruiter_name:
            job_details_section = await page.query_selector("[class*='description'] ~ div, [class*='top-card']")
            if job_details_section:
                recruiter_candidate = await job_details_section.query_selector("a[href*='/in/']")
                if recruiter_candidate:
                    recruiter_name = (await recruiter_candidate.inner_text()).strip()
                    recruiter_link = await recruiter_candidate.get_attribute("href")
                    logger.info(f"[LinkedIn recruiter] Found via Strategy 2 (metadata): {recruiter_name}")
        
        if not recruiter_name:
            about_section = await page.query_selector("[class*='about-the-job'], [class*='job-details']")
            if about_section:
                profile_link = await about_section.query_selector("a[href*='/in/']")
                if profile_link:
                    recruiter_name = (await profile_link.inner_text()).strip()
                    recruiter_link = await profile_link.get_attribute("href")
                    logger.info(f"[LinkedIn recruiter] Found via Strategy 3 (about): {recruiter_name}")
        
        if not recruiter_name:
            all_profile_links = await page.query_selector_all("a[href*='/in/']")
            logger.info(f"[LinkedIn recruiter] Strategy 4: found {len(all_profile_links)} profile links on page")
            for link in all_profile_links[2:5]:
                href = await link.get_attribute("href")
                if href and "/company/" not in href and "/jobs/" not in href:
                    recruiter_name = (await link.inner_text()).strip()
                    if recruiter_name and len(recruiter_name) > 0:
                        recruiter_link = href
                        logger.info(f"[LinkedIn recruiter] Found via Strategy 4 (fallback search): {recruiter_name}")
                        break
        
        if recruiter_link:
            if recruiter_link.startswith("/"):
                recruiter_link = "https://www.linkedin.com" + recruiter_link
            recruiter_link = recruiter_link.split("?")[0]
        
        
        if not recruiter_name:
            logger.info(f"[LinkedIn recruiter] No recruiter found (typical - requires authentication on LinkedIn)")
            logger.info(f"[LinkedIn recruiter] This is expected for guest/unauthenticated users")
        
        return {
            "recruiter_name": recruiter_name,
            "recruiter_email": recruiter_email,
            "recruiter_link": recruiter_link
        }
    except Exception as e:
        logger.warning(f"[listing_scraper] LinkedIn detail scrape failed for {url}: {e}")
        logger.info("[listing_scraper] Note: Recruiter info often requires LinkedIn authentication")
        return {}


async def _scrape_indeed_job_details(page: Page, url: str) -> dict:
    """Visit an Indeed job page and extract recruiter info."""
    import random
    await page.wait_for_timeout(random.randint(2000, 5000))
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await page.wait_for_timeout(1000)
        
        recruiter_name = None
        recruiter_email = None
        recruiter_link = None
        
        company_contact = await page.query_selector('[class*="contact"], [class*="company"]')
        if company_contact:
            recruiter_name = (await company_contact.inner_text()).strip()
        
        page_text = await page.inner_text("body")
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text)
        if email_match:
            recruiter_email = email_match.group(0)
        
        phone_link = await page.query_selector("a[href*='tel:']")
        if phone_link:
            recruiter_link = await phone_link.get_attribute("href")
        
        return {
            "recruiter_name": recruiter_name,
            "recruiter_email": recruiter_email,
            "recruiter_link": recruiter_link
        }
    except Exception as e:
        logger.warning(f"[listing_scraper] Indeed detail scrape failed for {url}: {e}")
        return {}


async def _extract_glassdoor_cards(page: Page, max_cards: int = 30) -> list[dict]:
    """Extract job cards from Glassdoor search results."""
    cards = await page.query_selector_all(".JobCard_jobCardContainer__arQlW")
    results = []

    for card in cards[:max_cards]:
        title_el = (
            await card.query_selector(".JobCard_jobTitle__GLyJ1 a")
            or await card.query_selector('a[data-test="job-link"]')
        )

        href = (await title_el.get_attribute("href")) if title_el else None

        if href and href.startswith("/"):
            base = await page.evaluate("window.location.origin")
            href = base + href
            
        raw_text = (await card.inner_text()).strip()

        if href and raw_text:
            results.append({"link": href, "raw_text": raw_text})

    return results

async def open_page(bm: BrowserManager, url: str, platform: str) -> Page:
    """Opens a new browser page and navigates to the given URL."""
    page = await bm.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
    return page


def _card_to_raw_job(card: dict, source_url: str, platform: str) -> RawJobData:
    """Convert an extracted card dict into a RawJobData object."""
    link = card.get("link") or source_url
    raw_text = card.get("raw_text") or ""
    posted_at_text = card.get("posted_at_text")
    
    return RawJobData(
        source_url=link,
        source_platform=platform,
        raw_text=raw_text,
        raw_html=None,
        posted_at_text=posted_at_text,
        salary=card.get("salary"),
        recruiter_name=card.get("recruiter_name"),
        recruiter_link=card.get("recruiter_link")
    )


async def scrape_listing_page(
    bm: BrowserManager, url: str, search_queries: list[str] | None = None, max_cards: int = 30, freshness: str = "default", location: str = "India"
) -> tuple[list[RawJobData], list[str]]:
    """
    Scrape a known job platform listing page.
    Extracts at most max_cards from the first page.
    The caller (page_loader) handles batching and delays.
    """
    errors: list[str] = []
    query = " ".join(search_queries) if search_queries else ""

    platform = "unknown"
    if is_linkedin_listing(url):
        platform = "linkedin"
        normalized = _normalize_linkedin_url(url, query, freshness=freshness)
        extract_fn = _extract_linkedin_cards
    elif is_indeed_listing(url):
        platform = "indeed"
        normalized = _normalize_indeed_url(url, query)
        extract_fn = _extract_indeed_cards
    elif is_glassdoor_listing(url):
        platform = "glassdoor"
        normalized = _normalize_glassdoor_url(url, query)
        extract_fn = _extract_glassdoor_cards
    else:
        return [], [f"Unsupported known listing: {url}"]

    try:
        page = await open_page(bm, normalized, platform=platform)

        wait_time = 5000 if platform == "linkedin" else 3000
        await page.wait_for_timeout(wait_time)

        if platform == "indeed":
            if await _is_cloudflare_challenge(page):
                logger.warning("[listing_scraper] Indeed challenge page detected, retrying once after short wait...")
                import random
                await page.wait_for_timeout(random.randint(4000, 7000))
                await page.reload(wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(3000)

            if await _is_cloudflare_challenge(page):
                errors.append(
                    "Indeed blocked by Cloudflare challenge (IP reputation / bot protection). "
                    "Try authenticated browser session or residential IP/VPN, or disable Indeed for this run."
                )
                logger.warning("[listing_scraper] Indeed challenge persisted after retry; skipping Indeed extraction")
                await page.close()
                return [], errors

        is_guest_mode = False
        if platform == "linkedin":
            cards, is_guest_mode = await extract_fn(page, max_cards=max_cards)
            if is_guest_mode:
                logger.info("[listing_scraper] LinkedIn GUEST mode — skipping recruiter detail scraping (requires auth)")
        else:
            cards = await extract_fn(page, max_cards=max_cards)

        if platform == "indeed" and not cards and query:
            try:
                body_preview = (await page.evaluate("document.body.innerText.substring(0, 2000)")).lower()
            except Exception:
                body_preview = ""

            if "did not match any jobs" in body_preview or "search suggestions" in body_preview:
                broader_query = _broaden_indeed_query(query)
                if broader_query and broader_query.lower() != query.lower():
                    broadened_url = _normalize_indeed_url(url, broader_query)
                    logger.info(
                        f"[listing_scraper] Indeed: retrying with broader query '{broader_query}' -> {broadened_url}"
                    )
                    await page.goto(broadened_url, wait_until="domcontentloaded", timeout=20_000)
                    await page.wait_for_timeout(2500)
                    cards = await _extract_indeed_cards(page, max_cards=max_cards)
                    if cards:
                        normalized = broadened_url
        
        await page.close()
        
        if platform == "linkedin" and cards and not is_guest_mode:
            logger.info(f"[listing_scraper] LinkedIn: starting recruiter detail scrape for {len(cards)} jobs")
            for i, card in enumerate(cards):
                try:
                    detail_page = await bm.new_page()
                    details = await _scrape_linkedin_job_details(detail_page, card["link"])
                    card.update(details)
                    await detail_page.close()
                except Exception as e:
                    logger.warning(f"[listing_scraper] Failed to scrape LinkedIn details for job {i}: {e}")
        elif platform == "indeed" and cards:
            logger.info(f"[listing_scraper] Indeed: starting recruiter detail scrape for {len(cards)} jobs")
            for i, card in enumerate(cards):
                try:
                    detail_page = await bm.new_page()
                    details = await _scrape_indeed_job_details(detail_page, card["link"])
                    card.update(details)
                    await detail_page.close()
                except Exception as e:
                    logger.warning(f"[listing_scraper] Failed to scrape Indeed details for job {i}: {e}")
                
        logger.info(f"[listing_scraper] {platform}: extracted {len(cards)} job cards (cap {max_cards}) from {normalized}")

        if not cards:
            errors.append(f"No job cards found on {platform} listing: {normalized}")
            return [], errors

        raw_jobs = [_card_to_raw_job(c, url, platform) for c in cards]
        return raw_jobs, errors

    except Exception as e:
        errors.append(f"Listing scraper failed for {platform} ({normalized}): {e}")
        return [], errors