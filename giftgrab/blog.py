"""Blog content generation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .models import Product
from .text import IntroParams, MetaParams, make_intro, make_meta
from .utils import parse_price_string


@dataclass
class GeneratedContent:
    summary: str
    html: str


def _normalized_words(value: str) -> str:
    return " ".join(value.split())


def _article(word: str) -> str:
    return "an" if word[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


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
    highlight_items = _unique_items(features)
    highlight_sentence = ""
    if highlight_items:
        fragments = [
            _to_sentence_fragment(
                _truncate_highlight(item.rstrip(". "))
            )
            for item in highlight_items[:3]
            if item
        ]
        cleaned_fragments = [fragment for fragment in fragments if fragment]
        if cleaned_fragments:
            highlight_sentence = (
                f"Standout details include {_join_with_and(cleaned_fragments)}."
            )
    elif product.keywords:
        keyword_items = [
            keyword.lower()
            for keyword in _unique_items(product.keywords)[:3]
            if keyword
        ]
        if keyword_items:
            highlight_sentence = (
                f"It leans into {_join_with_and(keyword_items)}."
            )
    rating_sentence = ""
    if product.rating and product.total_reviews:
        rating_sentence = (
            f"Amazon shoppers currently rate it {product.rating:.1f} stars across {product.total_reviews:,} reviews."
        )
    closing_sentence = "Check the listing for the latest details before you add it to cart."
    sentences = [intro_line, highlight_sentence, rating_sentence, closing_sentence]
    return " ".join(sentence.strip() for sentence in sentences if sentence.strip())


def _build_highlights(product: Product, features: Sequence[str]) -> List[str]:
    highlights = _unique_items(features)
    if not highlights:
        highlights = _unique_items(product.keywords)
    cleaned: List[str] = []
    for item in highlights:
        trimmed = _truncate_highlight(item.rstrip(". "), limit=80)
        if trimmed:
            cleaned.append(trimmed)
        if len(cleaned) >= 5:
            break
    return cleaned


def _render_highlights(items: Sequence[str]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{item}</li>" for item in items)
    return (
        "<section class=\"highlights\">"
        "<h3>Highlights</h3>"
        f"<ul class=\"feature-list\">{lis}</ul>"
        "</section>"
    )


def _contains_keyword(values: Iterable[str], keywords: Sequence[str]) -> bool:
    for value in values:
        lower = value.lower()
        for keyword in keywords:
            if keyword.lower() in lower:
                return True
    return False


def _build_pros(
    product: Product, highlights: Sequence[str], price: str | None
) -> List[str]:
    pros: List[str] = []
    for highlight in highlights[:3]:
        fragment = highlight.rstrip(". ")
        if fragment:
            pros.append(f"{fragment} stands out on this pick.")
    if product.brand:
        pros.append(f"Made by {product.brand.strip()} with Amazon-ready convenience.")
    if product.rating and product.total_reviews:
        pros.append(
            f"Backed by a {product.rating:.1f}-star average from {product.total_reviews:,} Amazon reviews."
        )
    if price:
        pros.append(f"Captured at {price.strip()} when listed; competitive for the category.")
    seen: set[str] = set()
    deduped: List[str] = []
    for item in pros:
        normalized = " ".join(item.split())
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped[:4]


def _build_cons(product: Product, features: Sequence[str]) -> List[str]:
    texts = list(features) + list(product.keywords)
    cons: List[str] = []
    if product.rating is None or product.total_reviews is None:
        cons.append("Not enough Amazon reviews yet to gauge long-term satisfaction.")
    else:
        cons.append("Read the latest Amazon reviews to confirm it still meets expectations.")
    if product.price:
        cons.append("Pricing and availability can change quickly on Amazon—double-check before checkout.")
    else:
        cons.append("Check the Amazon listing for current pricing and stock details.")
    if _contains_keyword(texts, ["usb"]):
        cons.append("Requires access to USB power during use.")
    if _contains_keyword(texts, ["battery"]):
        cons.append("May need charged or replaced batteries right out of the box.")
    if _contains_keyword(texts, ["outdoor", "weather"]):
        cons.append("Verify the weather-readiness specs before planning outdoor use.")
    seen: set[str] = set()
    deduped: List[str] = []
    for item in cons:
        normalized = " ".join(item.split())
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
        if len(deduped) >= 5:
            break
    return deduped


def _render_pros_cons(pros: Sequence[str], cons: Sequence[str]) -> str:
    if not pros and not cons:
        return ""
    blocks: List[str] = []
    if pros:
        lis = "".join(f"<li>{item}</li>" for item in pros)
        blocks.append(f"<div class=\"pros\"><h3>Pros</h3><ul>{lis}</ul></div>")
    if cons:
        lis = "".join(f"<li>{item}</li>" for item in cons)
        blocks.append(f"<div class=\"cons\"><h3>Cons</h3><ul>{lis}</ul></div>")
    inner = "".join(blocks)
    return f"<section class=\"pros-cons\">{inner}</section>"


def _build_usage_tips(
    product: Product, category_name: str, features: Sequence[str]
) -> List[str]:
    texts = list(features) + list(product.keywords)
    tips: List[str] = []
    use_hint = _category_use_hint(category_name, product)
    if use_hint:
        tips.append(
            f"Pair it with other {use_hint} finds to round out your gift list."
        )
    if _contains_keyword(texts, ["usb"]):
        tips.append("Set it up near a USB power source or adapter for the best experience.")
    if _contains_keyword(texts, ["battery"]):
        tips.append("Charge or install batteries before wrapping so it's ready to go.")
    if _contains_keyword(texts, ["kit", "set"]):
        tips.append("Lay out all pieces before use to make sure nothing is missing.")
    if _contains_keyword(texts, ["outdoor", "weather"]):
        tips.append("Check Amazon's care instructions for outdoor or weather considerations.")
    tips.append("Review Amazon's product description for full specifications and sizing details.")
    tips.append("Use the Amazon Q&A section if you need clarification from recent buyers.")
    seen: set[str] = set()
    deduped: List[str] = []
    for tip in tips:
        normalized = " ".join(tip.split())
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
        if len(deduped) >= 5:
            break
    return deduped


def _render_usage_tips(tips: Sequence[str]) -> str:
    if not tips:
        return ""
    lis = "".join(f"<li>{tip}</li>" for tip in tips)
    return (
        "<section class=\"usage-tips\">"
        "<h3>Usage tips</h3>"
        f"<ul>{lis}</ul>"
        "</section>"
    )


def _good_for_text(category_name: str, product: Product) -> str:
    normalized = _normalized_words(category_name).strip()
    if normalized.lower().startswith("for "):
        audience = normalized[len("for ") :].strip().lower()
        if audience:
            return f"People shopping for {audience}."
    if normalized:
        return f"{normalized} shoppers looking for a reliable Amazon find."
    if product.keywords:
        keyword_list = ", ".join(_unique_items(product.keywords)[:2])
        if keyword_list:
            return f"Fans of {keyword_list.lower()} looking for a ready-to-gift pick."
    return "Shoppers who appreciate practical, well-reviewed finds."


def _render_good_for(text: str) -> str:
    return f"<p class=\"good-for\"><strong>Good for:</strong> {text}</p>"


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
    price_line = _price_line(product)
    review_line = _review_line(product)
    overview_parts = [f"<p>{intro}</p>"]
    if price_line:
        overview_parts.append(price_line)
    if review_line:
        overview_parts.append(review_line)
    overview_html = (
        "<section class=\"product-overview\">"
        "<h2>Overview</h2>"
        f"{''.join(overview_parts)}"
        "</section>"
    )
    highlights = _build_highlights(product, features)
    highlights_html = _render_highlights(highlights)
    pros = _build_pros(product, highlights, product.price)
    cons = _build_cons(product, features)
    pros_cons_html = _render_pros_cons(pros, cons)
    usage_tips_html = _render_usage_tips(
        _build_usage_tips(product, category_name, features)
    )
    good_for_html = _render_good_for(_good_for_text(category_name, product))
    sections = [
        overview_html,
        highlights_html,
        pros_cons_html,
        usage_tips_html,
        good_for_html,
    ]
    html = "".join(section for section in sections if section)
    return GeneratedContent(summary=summary, html=html)
