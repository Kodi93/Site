"""Quality gates to keep generated SEO copy within acceptable bounds."""
from __future__ import annotations

import re
from dataclasses import dataclass


_BAD_TITLE_PATTERNS = re.compile(r"buy now|best|🔥", re.IGNORECASE)


@dataclass
class SeoPayload:
    title: str
    description: str
    body: str | None = None


def passes_seo(payload: SeoPayload) -> bool:
    """Return True when the payload meets the guardrails for SEO pages."""

    title = (payload.title or "").strip()
    description = (payload.description or "").strip()
    body = (payload.body or "").strip()
    if not title or len(title) > 60 or _BAD_TITLE_PATTERNS.search(title):
        return False
    if len(description) < 140 or len(description) > 160:
        return False
    if len(body.split()) < 120:
        return False
    return True
