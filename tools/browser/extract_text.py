import re

from playwright.async_api import Page

CONTENT_SELECTORS = {
    "linkedin": [
        ".job-view-layout",
        ".jobs-description",
        ".job-details-jobs-unified-top-card__job-title",
    ],
    "indeed": [
        "#jobDescriptionText",
        ".jobsearch-JobComponent",
        ".job_seen_beacon",
    ],
    "reddit": [
        "[data-testid='post-container']",
        ".Post",
        "shreddit-post",
    ],
    "generic": ["main", "article", "body"],
}


async def extract_text(page: Page, platform: str = "generic") -> str:

    selectors = CONTENT_SELECTORS.get(platform, CONTENT_SELECTORS["generic"])
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return _clean_text(text)
        except Exception:
            continue

    text = await page.inner_text("body")
    return _clean_text(text)


async def extract_html(page: Page, platform: str = "generic") -> str:

    selectors = CONTENT_SELECTORS.get(platform, CONTENT_SELECTORS["generic"])

    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                html = await element.inner_html()
                return html
        except Exception:
            continue

    return await page.content()


def _clean_text(text: str) -> str:

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
