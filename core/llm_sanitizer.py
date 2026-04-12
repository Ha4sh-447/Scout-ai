"""
llm_sanitizer.py
"""
import re

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"disregard\s+(all\s+)?(prior|previous)\s+instructions?",
    r"<\|im_(start|end)\|>",
    r"\[INST\]",
    r"###\s*(system|instruction|prompt|human|assistant)",
    r"<\s*(system|instruction|assistant|human)\s*>",
    r"you\s+are\s+now\s+(a\s+)?different",
    r"new\s+instructions?:",
    r"override\s+(previous|all)\s+instructions?",
    r"forget\s+(everything|all|your)",
    r"admin\s+(override|mode|access)",
    r"jailbreak",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

MAX_TOKENS_HIGH = 1400   # llama-3.3-70b-versatile — ~2000 tokens, well within 12K TPM
MAX_TOKENS_LOW  = 700    # llama-3.1-8b — ~1000 tokens, fits in 6K TPM per single call


def sanitize_job_text(text: str, token_budget: int = MAX_TOKENS_HIGH) -> str:
    """
    Sanitize job text by stripping injections and truncating to budget.
    """
    if not text:
        return ""

    for pattern in _COMPILED:
        text = pattern.sub(" ", text)

    text = " ".join(text.split())

    words = text.split()
    return " ".join(words[:token_budget])


def sanitize_resume_summary(text: str) -> str:
    """Sanitize user-provided resume summaries — shorter budget."""
    return sanitize_job_text(text, token_budget=300)
