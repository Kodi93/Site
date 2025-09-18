"""Blog content generation helpers."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .models import Product

INTRO_TEMPLATES = [
    "Searching for {category_phrase}? <strong>{title}</strong> delivers a polished answer.",
    "Need {category_phrase}? <strong>{title}</strong> balances thoughtful design with everyday utility.",
    "Reviewing {category_phrase}? Shortlist <strong>{title}</strong> for a dependable win.",
]

FEATURE_INTROS = [
    "Key details:",
    "Highlights worth noting:",
    "What stands out:",
]

OUTRO_TEMPLATES = [
    "Count on <strong>{title}</strong> to leave a refined impression when it's unwrapped.",
    "Gift <strong>{title}</strong> with confidence—it's built to be appreciated long after the occasion.",
    "Let <strong>{title}</strong> deliver the thoughtful finish while you take credit for the savvy pick.",
]

CTA_TEMPLATES = [
    "<a class=\"cta-button\" href=\"{link}\" target=\"_blank\" rel=\"noopener sponsored\">View full details on Amazon</a>",
    "<a class=\"cta-button\" href=\"{link}\" target=\"_blank\" rel=\"noopener sponsored\">Check current pricing on Amazon</a>",
]


@dataclass
class GeneratedContent:
    summary: str
    html: str


def _normalized_words(value: str) -> str:
    return " ".join(value.split())


def _deterministic_choice(options: Sequence[str], seed: str) -> str:
    if not options:
        raise ValueError("No options supplied")
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % len(options)
    return options[index]


def _article(word: str) -> str:
    return "an" if word[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def build_category_phrase(category_name: str) -> str:
    normalized = _normalized_words(category_name or "").strip()
    if not normalized:
        return "a standout gift"
    lower = normalized.lower()

    audience_rewrites = {
        "fandom": "devoted superfans",
        "the fandom": "devoted superfans",
        "a techy": "tech enthusiasts",
        "techy": "tech enthusiasts",
        "techies": "tech enthusiasts",
    }

    def _audience_phrase(audience: str) -> str:
        normalized_audience = _normalized_words(audience).strip()
        if not normalized_audience:
            return ""
        replacement = audience_rewrites.get(normalized_audience.lower(), normalized_audience.lower())
        return f"the perfect gift for {replacement}"

    if lower.startswith("gifts for "):
        audience = normalized[len("gifts for ") :].strip()
        phrase = _audience_phrase(audience)
        if phrase:
            return phrase
    if lower.startswith("for "):
        audience = normalized[len("for ") :].strip()
        phrase = _audience_phrase(audience)
        if phrase:
            return phrase
    if lower.endswith(" upgrades"):
        base = lower[: -len(" upgrades")].strip()
        if base:
            return f"{_article(base)} {base} upgrade they'll appreciate"
    if lower.endswith(" power-ups"):
        base = lower[: -len(" power-ups")].strip()
        if base:
            return f"{_article(base)} {base} power-up worth gifting"
    if lower.endswith(" essentials"):
        base = lower[: -len(" essentials")].strip()
        if base:
            return f"{_article(base)} {base} essential they will actually use"
    if lower.endswith(" warriors"):
        base = lower[: -len(" warriors")].strip()
        if base:
            return f"the perfect gift for {base} warriors"
    if lower.endswith(" time"):
        base = lower[: -len(" time")].strip()
        if base:
            return f"a thoughtful pick for {base} time together"

    polished_defaults = {
        "family time": "a thoughtful pick for family time together",
        "homebody upgrades": "a homebody upgrade they'll appreciate",
    }
    if lower in polished_defaults:
        return polished_defaults[lower]

    base_words = normalized.split()
    article_target = base_words[0].lower()
    descriptor = lower
    return f"{_article(article_target)} {descriptor} pick worth gifting"


def _unique_items(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if not value:
            continue
        normalized = _normalized_words(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def format_feature_list(features: Iterable[str], seed: str) -> str:
    items = _unique_items(features)
    if not items:
        return ""
    lis = "".join(f"<li>{feature}</li>" for feature in items)
    intro = _deterministic_choice(FEATURE_INTROS, seed)
    return f"<h3>{intro}</h3><ul class=\"feature-list\">{lis}</ul>"


def _truncate_highlight(value: str, limit: int = 60) -> str:
    if len(value) <= limit:
        return value
    trimmed = value[: limit - 1].rstrip(",;:- ")
    return f"{trimmed}…"


def _to_sentence_fragment(value: str) -> str:
    if not value:
        return value
    first = value[0]
    if first.isalpha() and len(value) > 1 and not value[1].isupper():
        return first.lower() + value[1:]
    if first.isalpha() and len(value) == 1:
        return first.lower()
    return value


def _join_with_and(items: Sequence[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def generate_summary(product: Product, category_name: str, features: Iterable[str]) -> str:
    phrase = build_category_phrase(category_name)
    highlight_source = _unique_items(features)
    highlights_from_features = bool(highlight_source)
    if not highlight_source:
        highlight_source = _unique_items(product.keywords)
    if not highlight_source:
        base_sentence = f"{product.title} delivers {phrase}."
        return f"{base_sentence} Expect thoughtful touches throughout."

    highlights: List[str] = []
    for item in highlight_source[:3]:
        trimmed = _truncate_highlight(item.rstrip(". "))
        highlights.append(_to_sentence_fragment(trimmed))
    highlight_phrase = _join_with_and(highlights)
    lead_in = "Standout details include" if highlights_from_features else "Key themes include"
    return f"{product.title} delivers {phrase}. {lead_in} {highlight_phrase}."


def generate_blog_post(product: Product, category_name: str, features: List[str]) -> GeneratedContent:
    phrase = build_category_phrase(category_name)
    seed = product.asin or product.title
    intro_template = _deterministic_choice(INTRO_TEMPLATES, f"{seed}:intro")
    intro = intro_template.format(
        category_phrase=phrase,
        title=product.title,
    )
    summary = generate_summary(product, category_name, features)
    feature_html = format_feature_list(features, f"{seed}:features")
    outro_template = _deterministic_choice(OUTRO_TEMPLATES, f"{seed}:outro")
    outro = outro_template.format(title=product.title)
    cta_template = _deterministic_choice(CTA_TEMPLATES, f"{seed}:cta")
    cta = cta_template.format(link=product.link)
    price_line = (
        f"<p class=\"price-callout\">Typically sells for <strong>{product.price}</strong>.</p>"
        if product.price
        else ""
    )
    review_line = (
        f"<p class=\"review-callout\">Rated {product.rating:.1f} stars by {product.total_reviews:,} shoppers.</p>"
        if product.rating and product.total_reviews
        else ""
    )
    html = (
        f"<p>{intro}</p>"
        f"{price_line}"
        f"{review_line}"
        f"{feature_html}"
        f"<p>{outro}</p>"
        f"<p class=\"cta-row\">{cta}</p>"
    )
    return GeneratedContent(summary=summary, html=html)
