"""Blog content generation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .models import Product
from .text import IntroParams, MetaParams, make_intro, make_meta
from .utils import parse_price_string

CTA_TEMPLATE = (
    "<a class=\"cta-button\" href=\"{link}\" target=\"_blank\" rel=\"noopener sponsored\">Review the listing on Amazon</a>"
)


@dataclass
class GeneratedContent:
    summary: str
    html: str


def _normalized_words(value: str) -> str:
    return " ".join(value.split())


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


def _price_components(price: str | None) -> tuple[float | None, str | None]:
    parsed = parse_price_string(price)
    if not parsed:
        return None, None
    return parsed


def _category_use_hint(category_name: str, product: Product) -> str | None:
    normalized = _normalized_words(category_name).strip()
    if normalized:
        lower = normalized.lower()
        if lower.startswith("for "):
            candidate = normalized[len("for ") :].strip()
            if candidate:
                return candidate.lower()
        return lower
    if product.keywords:
        return str(product.keywords[0]).lower()
    return None


def _collect_specs(features: Iterable[str], keywords: Iterable[str]) -> List[str]:
    feature_items = _unique_items(features)
    source = feature_items if feature_items else _unique_items(keywords)
    specs: List[str] = []
    for item in source:
        trimmed = _truncate_highlight(item.rstrip(". "), limit=70)
        if trimmed:
            specs.append(trimmed)
        if len(specs) >= 3:
            break
    if not feature_items and len(specs) > 2:
        return [specs[0], specs[-1]]
    return specs


def _compose_intro_paragraph(
    product: Product,
    category_name: str,
    features: Sequence[str],
    price_value: float | None,
) -> str:
    use_hint = _category_use_hint(category_name, product)
    intro_line = make_intro(
        IntroParams(title=product.title, use=use_hint, price=price_value)
    ).strip()
    highlight_items = [
        _to_sentence_fragment(_truncate_highlight(item.rstrip(". ")))
        for item in _unique_items(features)[:3]
    ]
    if highlight_items:
        highlight_phrase = _join_with_and(highlight_items)
        highlight_sentence = (
            f"It emphasizes {highlight_phrase} so campaign briefs stay credible and easy to action."
        )
    else:
        highlight_sentence = (
            "It emphasizes practical touches so campaign briefs stay credible and easy to action."
        )
    rating_sentence = (
        f"Recent Amazon feedback averages {product.rating:.1f} stars across {product.total_reviews:,} reviews, signalling dependable satisfaction."
        if product.rating and product.total_reviews
        else "Revisit the Amazon listing before launch to confirm specifications and creative requirements for your teams."
    )
    closing_sentence = (
        "Use the checklist below to validate pricing, positioning, and caveats before you pitch or publish."
    )
    sentences = [intro_line, highlight_sentence, rating_sentence, closing_sentence]
    return " ".join(sentence.strip() for sentence in sentences if sentence.strip())


def _build_bullet_points(
    product: Product,
    category_name: str,
    features: Sequence[str],
    price: str | None,
) -> List[str]:
    bullets: List[str] = []
    for feature in _unique_items(features)[:4]:
        cleaned = _truncate_highlight(feature.rstrip(". "))
        if cleaned:
            bullets.append(f"Key spec: {cleaned}.")
    if product.brand:
        bullets.append(f"Brand: {product.brand.strip()}.")
    if price:
        bullets.append(f"Typical price: {price.strip()} (subject to change).")
    if product.rating and product.total_reviews:
        bullets.append(
            f"Feedback: {product.rating:.1f}-star average across {product.total_reviews:,} Amazon reviews."
        )
    bullets.append(f"Category fit: {category_name.strip()}.")
    fallback = [
        "Availability: Monitor the listing and confirm stock before campaign launch.",
        "Positioning: Works in curated guides, email features, and remarketing without heavy edits.",
        "Compliance: Include pricing disclaimers and confirm assets prior to creative handoff.",
    ]
    deduped: List[str] = []
    seen: set[str] = set()
    for bullet in bullets + fallback:
        normalized = " ".join(bullet.split())
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
        if len(deduped) >= 7:
            break
    return deduped[:7]


def _render_bullet_list(items: Sequence[str]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{item}</li>" for item in items)
    return f"<h3>Key takeaways</h3><ul class=\"feature-list\">{lis}</ul>"


def _good_for_text(category_name: str, product: Product) -> str:
    use_hint = _category_use_hint(category_name, product) or "versatile gifting"
    return (
        f"{use_hint.capitalize()} who appreciate practical, well-reviewed finds.".replace("  ", " ")
    )


def _consider_points() -> List[str]:
    return [
        "Confirm availability, shipping windows, and region-specific details before finalizing campaigns.",
        "Double-check compatibility, sizing, or installation needs to avoid customer support surprises.",
    ]


def _render_good_for(text: str) -> str:
    return f"<p class=\"good-for\"><strong>Good for:</strong> {text}</p>"


def _render_consider(points: Sequence[str]) -> str:
    if not points:
        return ""
    lis = "".join(f"<li>{point}</li>" for point in points)
    return f"<div class=\"consider-block\"><strong>Consider:</strong><ul>{lis}</ul></div>"


def _price_line(product: Product) -> str:
    if not product.price:
        return ""
    return (
        f"<p class=\"price-callout\">Typically sells for <strong>{product.price}</strong>.</p>"
    )


def _review_line(product: Product) -> str:
    if not (product.rating and product.total_reviews):
        return ""
    return (
        f"<p class=\"review-callout\">Rated {product.rating:.1f} stars by {product.total_reviews:,} shoppers.</p>"
    )


def _cta(product: Product) -> str:
    return CTA_TEMPLATE.format(link=product.link)


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
    specs = _collect_specs(features, product.keywords)
    price_value, currency = _price_components(product.price)
    use_hint = _category_use_hint(category_name, product)
    meta = make_meta(
        MetaParams(
            name=product.title,
            price=price_value,
            currency=currency,
            specs=specs,
            use=use_hint,
        )
    )
    return meta


def generate_blog_post(product: Product, category_name: str, features: List[str]) -> GeneratedContent:
    summary = generate_summary(product, category_name, features)
    price_value, _currency = _price_components(product.price)
    intro = _compose_intro_paragraph(product, category_name, features, price_value)
    bullet_html = _render_bullet_list(
        _build_bullet_points(product, category_name, features, product.price)
    )
    good_for_html = _render_good_for(_good_for_text(category_name, product))
    consider_html = _render_consider(_consider_points())
    price_line = _price_line(product)
    review_line = _review_line(product)
    cta = _cta(product)
    html = (
        f"<p>{intro}</p>"
        f"{price_line}"
        f"{review_line}"
        f"{bullet_html}"
        f"{good_for_html}"
        f"{consider_html}"
        f"<p class=\"cta-row\">{cta}</p>"
    )
    return GeneratedContent(summary=summary, html=html)
