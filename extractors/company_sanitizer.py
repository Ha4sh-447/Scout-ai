import re


def sanitise_company_name(raw: str | None) -> str:
    """
    Strip artifacts that LinkedIn's "How you match" section and other
    UI elements inject into the page text.
    """
    if not raw:
        return "Unknown"

    company = raw

    company = re.sub(r"\s*Match:\s*.*$", "", company, flags=re.IGNORECASE | re.DOTALL)

    company = re.sub(r"\s*·\s*(1st|2nd|3rd|Follow|Message|Connect|Promoted)\b.*$", "", company, flags=re.IGNORECASE)

    company = re.sub(r"\s*·\s*\d+\s+(applicants|employees|followers).*$", "", company, flags=re.IGNORECASE)

    company = " ".join(company.split())

    return company.strip() or "Unknown"


def sanitise_job_description(text: str | None) -> str:
    """
    Cleans the job description to remove navigation artifacts and
    LinkedIn's 'Match: resume_name' text which can bias embeddings.
    """
    if not text:
        return ""
    
    text = re.sub(r"\bMatch:\s*\S+", "", text, flags=re.IGNORECASE)
    
    text = re.sub(r"·\s*(1st|2nd|3rd|Follow|Message|Connect)\b", "", text, flags=re.IGNORECASE)
    
    return text.strip()