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
    """Convert the provided string into accessible title case."""

    def _convert(word: str) -> str:
        if not word:
            return word
        # Preserve existing interior capitalization (e.g., iPhone, PlayStation)
        if any(ch.isupper() for ch in word[1:]):
            return word
        # Keep acronyms (USB, OLED) untouched
        if word.isupper() and len(word) > 1:
            return word
        return word[0].upper() + word[1:].lower()

    words = re.split(r"(\s+|-|/)", value)
    converted: List[str] = []
    for token in words:
        if token.strip() and not token.isspace() and token not in {"-", "/"}:
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


def _short_model(model: Optional[str]) -> str:
    if not model:
        return ""
    trimmed = clean_text(model)
    return trimmed if len(trimmed) <= 18 else ""


def make_title(params: TitleParams) -> str:
    """Generate a concise, professional SEO title."""

    name = clean_text(dedupe_brand(params.name, params.brand))
    model_fragment = _short_model(params.model)
    if model_fragment:
        name_with_model = f"{name} {model_fragment}".strip()
    else:
        name_with_model = name
    category_hint = clean_text(params.use or params.category or "Gift Idea")
    if category_hint:
        composed = f"{name_with_model} — {category_hint}"
    else:
        composed = name_with_model
    return clamp(title_case(composed), 60)


@dataclass
class MetaParams:
    name: str
    price: Optional[float] = None
    currency: Optional[str] = None
    specs: Optional[Sequence[str]] = None
    use: Optional[str] = None


def _summarize_specs(specs: Sequence[str]) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for spec in specs:
        normalized = clean_text(spec)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized.rstrip(". "))
        if len(cleaned) == 2:
            break
    return cleaned


def make_meta(params: MetaParams) -> str:
    """Construct a meta description with specs and a price anchor."""

    subject = clean_text(params.name)
    spec_items = _summarize_specs(params.specs or [])
    spec_summary = ", ".join(spec_items) if spec_items else "key features"
    if params.price is not None:
        rounded_price = int(round(params.price))
        price_text = f"{rounded_price} {params.currency or 'USD'}"
    else:
        price_text = "the current price"
    use_clause = clean_text(params.use or "").lower()
    use_prefix = f"For {use_clause}. " if use_clause else ""
    description = clean_text(
        f"{use_prefix}{subject} — {spec_summary}. Check {price_text} before you buy."
    )
    extras = [
        "See highlights inside.",
        "We outline trade-offs.",
        "Learn more inside.",
    ]
    for extra in extras:
        if len(description) >= 140:
            break
        candidate = clean_text(f"{description} {extra}")
        if len(candidate) <= 155:
            description = candidate
    if len(description) > 155:
        description = clamp(description, 155)
    if not description.endswith("."):
        candidate = f"{description}."
        description = candidate if len(candidate) <= 155 else clamp(candidate, 155)
    if len(description) < 140:
        for extra in extras:
            candidate = clean_text(f"{description} {extra}")
            if len(candidate) <= 155:
                description = candidate
                break
        if len(description) < 140:
            description = clamp(
                clean_text(f"{description} Explore buyer context inside."), 155
            )
    return description


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
        "Highlights and trade-offs below."
    )


def title_roundup(topic: str, cap: int) -> str:
    return clamp(clean_text(f"Top 10 {topic} Under ${cap}"), 60)


def desc_roundup(topic: str, cap: int) -> str:
    copy = clean_text(
        f"Ten {topic} under ${cap}. Curated picks with quick blurbs and retailer search links."
    )
    return clamp(copy, 155)


def intro_roundup(topic: str, cap: int) -> str:
    topic_clean = clean_text(topic)
    return (
        f"Looking for {topic_clean.lower()} under ${cap}? "
        "Here are ten solid ideas with quick blurbs and links to check current prices."
    )


def title_breakdown(name: str, topic: str | None = None, cap: int | None = None) -> str:
    parts = [clean_text(name)]
    if topic:
        parts.append(clean_text(topic))
    title = " – ".join(parts)
    if cap is not None:
        title = f"{title} under ${cap}"
    return clamp(title, 60)


def desc_breakdown(name: str) -> str:
    base = clean_text(
        f"{name}: key details, uses, and honest trade-offs. Check current price on Amazon."
    )
    return clamp(base, 155)


def intro_breakdown(name: str, cap: int | None = None) -> str:
    name_clean = clean_text(name)
    price_fragment = f" under ${cap}" if cap is not None else ""
    return (
        f"{name_clean} is a practical pick{price_fragment}. "
        "Highlights and trade-offs below."
    )
