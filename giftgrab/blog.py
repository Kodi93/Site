"""Blog content generation helpers."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List

from .models import Product

INTRO_TEMPLATES = [
    "Looking for {category_phrase}? Meet <strong>{title}</strong>, a standout find that instantly caught our eye.",
    "Stop the endless scrolling—<strong>{title}</strong> is the kind of {category_phrase} that deserves a permanent spot on your wishlist.",
    "Need {category_phrase}? {title} delivers the wow factor without the guesswork.",
]

FEATURE_INTROS = [
    "Why we're obsessed:",
    "Unwrap the highlights:",
    "Reasons it'll be a hit:",
]

OUTRO_TEMPLATES = [
    "Snag <strong>{title}</strong> now and be the gifting hero who always knows what's trending.",
    "Ready to upgrade your gift game? Tap that buy button and let <strong>{title}</strong> do the bragging.",
    "Trust us—<strong>{title}</strong> is the kind of present that earns repeat high fives.",
]

CTA_TEMPLATES = [
    "<a class=\"cta-button\" href=\"{link}\" target=\"_blank\" rel=\"noopener sponsored\">Check it out on Amazon</a>",
    "<a class=\"cta-button\" href=\"{link}\" target=\"_blank\" rel=\"noopener sponsored\">See the latest price on Amazon</a>",
]


@dataclass
class GeneratedContent:
    summary: str
    html: str


def build_category_phrase(category_name: str) -> str:
    category_name = category_name.lower()
    if category_name.startswith("gifts for"):
        return f"the perfect {category_name}"
    return f"a {category_name} gift"


def format_feature_list(features: Iterable[str]) -> str:
    items = [feature for feature in features if feature]
    if not items:
        return ""
    lis = "".join(f"<li>{feature}</li>" for feature in items)
    intro = random.choice(FEATURE_INTROS)
    return f"<h3>{intro}</h3><ul class=\"feature-list\">{lis}</ul>"


def generate_summary(product: Product, category_name: str) -> str:
    phrase = build_category_phrase(category_name)
    return f"{product.title} is {phrase} thanks to smart details like {', '.join(product.keywords[:3]) or 'thoughtful touches'}."


def generate_blog_post(product: Product, category_name: str, features: List[str]) -> GeneratedContent:
    phrase = build_category_phrase(category_name)
    intro = random.choice(INTRO_TEMPLATES).format(
        category_phrase=phrase,
        title=product.title,
    )
    summary = generate_summary(product, category_name)
    feature_html = format_feature_list(features)
    outro = random.choice(OUTRO_TEMPLATES).format(title=product.title)
    cta = random.choice(CTA_TEMPLATES).format(link=product.link)
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
