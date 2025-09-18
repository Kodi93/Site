"""Utility helpers for generating professional SEO-friendly copy."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


_BAD_PHRASES = re.compile(
    r"(\bfree shipping\b|\bbuy now\b|\bbest\b|🔥|💥|⭐️|🚀)",
    re.IGNORECASE,
)


def clamp(value: str, limit: int) -> str:
    """Trim the string to the desired limit without splitting words when possible."""

    if len(value) <= limit:
        return value
    trimmed = value[:limit].rstrip()
    last_space = trimmed.rfind(" ")
    if last_space > 40:  # prefer to cut on whitespace when the chunk is long enough
        trimmed = trimmed[:last_space]
    return trimmed.rstrip(" ,.;:!")


def title_case(value: str) -> str:
    """Convert the provided string into simple title case."""

    def _convert(word: str) -> str:
        if not word:
            return word
        return word[0].upper() + word[1:].lower()

    words = re.split(r"(\s+|-)", value)
    converted: List[str] = []
    for token in words:
        if token.strip() and not token.isspace() and token != "-":
            converted.append(_convert(token))
        else:
            converted.append(token)
    return "".join(converted)


def dedupe_brand(name: str, brand: Optional[str]) -> str:
    """Ensure the brand is only mentioned once in the rendered name."""

    if not brand:
        return name
    pattern = re.compile(rf"\b{re.escape(brand)}\b", re.IGNORECASE)
    if pattern.search(name):
        return name
    return f"{brand} {name}".strip()


def clean_text(value: str) -> str:
    """Collapse whitespace and remove banned phrases or emoji."""

    collapsed = re.sub(r"\s+", " ", value or "").strip()
    cleaned = _BAD_PHRASES.sub("", collapsed)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class TitleParams:
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    use: Optional[str] = None


def make_title(params: TitleParams) -> str:
    """Generate a concise, professional SEO title."""

    category = params.category or params.use or "Gadget"
    name = dedupe_brand(params.name, params.brand)
    model = f" {params.model}" if params.model else ""
    base = f"{category}: {name}{model}".strip()
    return clamp(title_case(clean_text(base)), 60)


@dataclass
class MetaParams:
    name: str
    price: Optional[float] = None
    currency: Optional[str] = None
    specs: Optional[Sequence[str]] = None
    use: Optional[str] = None


def make_meta(params: MetaParams) -> str:
    """Construct a meta description with specs and a price anchor."""

    specs = [clean_text(spec) for spec in (params.specs or []) if clean_text(spec)]
    spec_text = ", ".join(specs[:3]) if specs else "key features"
    if params.price is not None:
        rounded_price = int(round(params.price))
        price_text = f"{rounded_price} {params.currency or 'USD'}"
    else:
        price_text = "current price"
    use_prefix = f"For {clean_text(params.use or '').lower()}. " if params.use else ""
    description = (
        f"{use_prefix}{clean_text(params.name)} — {spec_text}. "
        f"Check {price_text} and details before you buy. "
        "Confirm stock and fit before you launch."
    )
    return clamp(clean_text(description), 160)


@dataclass
class IntroParams:
    title: str
    use: Optional[str] = None
    price: Optional[float] = None


def make_intro(params: IntroParams) -> str:
    """Return a short intro line referencing use-case and price."""

    use_fragment = f" for {clean_text(params.use).lower()}" if params.use else ""
    price_fragment = (
        f" around ${int(round(params.price))}"
        if params.price is not None
        else ""
    )
    return (
        f"{clean_text(params.title)} is a practical pick{use_fragment}{price_fragment}. "
        "Highlights below with honest trade-offs."
    )
