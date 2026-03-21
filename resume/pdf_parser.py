# Section header patterns — matched case-insensitively against short lines
import re
from pathlib import Path

import pdfplumber
import logging

from models.config import ResumeMatchingConfig
from models.resume import Resume, ResumeChunk

_SECTION_PATTERNS = {
    "experience": r"\b(experience|work history|employment|professional background|work experience)\b",
    "skills": r"\b(skills|technical skills|core competencies|technologies|tech stack)\b",
    "education": r"\b(education|academic|qualifications|degrees?)\b",
    "achievements": r"\b(achievements|honors|awards|accomplishments)\b",
    "certifications": r"\b(certifications?|licenses?|courses?)\b",
    "summary": r"\b(summary|objective|profile|about me|overview|introduction)\b",
    "projects": r"\b(projects?|personal projects?|academic projects?|side projects?)\b",
}

logger = logging.getLogger(__name__)


def parse_pdf(path: str | Path, user_id: str, cfg: ResumeMatchingConfig) -> Resume:
    """
    Parse the resume
    Extract the text
    Divide into chunks
    Return the resume object
    """

    cfg = cfg or ResumeMatchingConfig()

    raw_text = _extract_text(path)

    if not raw_text or len(raw_text) < 100:
        raise ValueError(f" No usable text extracted from {path}")

    chunks = _build_chunks(raw_text, user_id, cfg)

    return Resume(
        user_id=user_id,
        raw_text=raw_text,
        chunks=chunks,
    )


def _extract_text(path: str | Path) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if text:
                pages.append(text)
    return _clean("\n\n".join(pages))


def _detect_section(line: str) -> str | None:
    """
    Return section name if the line looks like a section header, else None.
    A header is a short line (< 60 chars) that matches one of the patterns.
    """
    if len(line.strip()) > 60:
        return None
    line_lower = line.lower()
    for section, pattern in _SECTION_PATTERNS.items():
        if re.search(pattern, line_lower):
            return section
    return None


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Split resume text into [(section_name, section_text), ...].
    Falls back to [("other", full_text)] if no headers detected.
    """
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_section = "summary"
    current_lines: list[str] = []

    for line in lines:
        detected = _detect_section(line)
        if detected:
            if current_lines:
                sections.append((current_section, "\n".join(current_lines)))
            current_section = detected
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_section, "\n".join(current_lines)))

    logger.info(f"[pdf_parser] Split into {len(sections)} sections: {[s[0] for s in sections]}")
    return sections if sections else [("other", text)]


# Chunking
def _build_chunks(
    raw_text: str, user_id: str, cfg: ResumeMatchingConfig
) -> list[ResumeChunk]:
    sections = _split_into_sections(raw_text)
    chunks: list[ResumeChunk] = []
    idx = 0

    for section_name, section_text in sections:
        sub_texts = _sliding_window(section_text, cfg.chunk_size, cfg.overlap_count)
        for sub_text in sub_texts:
            if len(sub_text.strip()) < 50:
                continue
            chunks.append(
                ResumeChunk(
                    chunk_id=f"{user_id}_{idx}",
                    user_id=user_id,
                    text=sub_text.strip(),
                    section=section_name,
                    chunk_index=idx,
                )
            )
            idx += 1
    
    logger.info(f"[pdf_parser] Created {len(chunks)} chunks for user {user_id}")
    return chunks


def _sliding_window(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping windows. Returns [text] if short enough."""
    if len(text) <= size:
        return [text]

    chunks, start = [], 0
    while start < len(text):
        end = start + size
        # Prefer breaking at sentence boundary
        if end < len(text):
            boundary = text.rfind(".", start, end)
            if boundary > start + size // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
