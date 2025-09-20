"""Lightweight text helpers used when describing products."""
from __future__ import annotations

from typing import Iterable

from .models import Product

_OPENERS = (
    "Great pick for",
    "Solid choice if you're into",
    "Smart grab for",
    "Nice upgrade for",
    "Reliable find for",
)

_CLOSERS = (
    "Easy win for gifting.",
    "Keeps your setup feeling tidy.",
    "Makes quick gifts feel thoughtful.",
    "A dependable add-on to round out a list.",
    "Plays nicely with last-minute gifting.",
)

_PADDING = (
    "It feels ready to hand off without extra fuss",
    "Quick to recommend when you're curating gifts",
    "Keeps the unboxing moment feeling polished",
    "Still light enough to toss into a weekend roundup",
)

_CATEGORY_FOCUS_OVERRIDES = {
    "fandom": "fandom superfans",
    "homebody upgrades": "homebodies",
    "productivity power ups": "productivity power-ups",
}

_DESCRIPTOR_FOCUS_OVERRIDES = {
    "family time": "keeps family hangouts feeling intentional",
    "a techy": "layers in gadget-lover polish",
    "adventurers": "packs weekend-warrior utility",
    "fandom superfans": "brings fandom-grade flair",
    "gamers": "levels up play sessions",
    "her": "feels like a thoughtful-for-her upgrade",
    "him": "lands with him without feeling cliché",
    "homebodies": "makes cozy nights even better",
    "productivity power-ups": "sharpens productivity routines",
    "wellness warriors": "supports wellness rituals",
    "gift hunters": "stays useful for last-minute gift hunters",
}

_PRICE_THRESHOLDS = (
    (25, "stays under $25"),
    (50, "lands under $50"),
    (100, "sits below $100"),
)


def _pick(seed: str, options: Iterable[str]) -> str:
    choices = tuple(options)
    if not choices:
        return ""
    index = sum(ord(char) for char in seed) % len(choices)
    return choices[index]


def _price_phrase(product: Product) -> str | None:
    if product.price is None:
        return None
    for threshold, phrase in _PRICE_THRESHOLDS:
        if product.price <= threshold:
            return phrase
    if product.price_text:
        return f"arrives around {product.price_text}".strip()
    return None


def _descriptor(product: Product, focus: str) -> str:
    brand = product.brand
    if brand:
        cleaned = " ".join(str(brand).split()).strip()
        if cleaned:
            return f"leans on {cleaned} craftsmanship"
    focus_key = focus.lower().strip()
    override = _DESCRIPTOR_FOCUS_OVERRIDES.get(focus_key)
    if override:
        return override
    if focus_key:
        return f"brings a {focus_key} twist"
    if product.price_text:
        return f"keeps the price anchored around {product.price_text}"
    return "packs in useful details"


def _focus_target(product: Product) -> str:
    """Return a focus phrase tuned for the product's category or brand."""

    category = product.category
    if category:
        cleaned = " ".join(str(category).split()).strip()
        lowered = cleaned.lower()
        for prefix in ("for ", "the "):
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix) :].lstrip()
                lowered = cleaned.lower()
        lowered = cleaned.lower()
        if not lowered:
            return "gift hunters"
        override = _CATEGORY_FOCUS_OVERRIDES.get(lowered)
        if override:
            return override
        return lowered

    brand = product.brand
    if brand:
        return " ".join(str(brand).split()).strip()

    return "gift hunters"


def polish(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return "Gift-ready pick that keeps things simple."
    if not cleaned.endswith("."):
        cleaned = f"{cleaned}."
    if cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    if len(cleaned) < 120:
        extra = _pick(cleaned, _PADDING)
        if extra:
            cleaned = f"{cleaned[:-1]}; {extra}."
    if len(cleaned) > 160:
        trimmed = cleaned[:157].rstrip(",;: ")
        cleaned = f"{trimmed}."
    return cleaned


def blurb(product: Product) -> str:
    focus = _focus_target(product)
    opener = _pick(product.id, _OPENERS)
    descriptor = _descriptor(product, focus)
    price_clause = _price_phrase(product)
    base = f"{opener} {focus}, {product.title} delivers {descriptor}"
    if price_clause:
        base = f"{base} and {price_clause}"
    else:
        base = f"{base} that feels ready to gift"
    closing = _pick(product.title, _CLOSERS)
    sentence = f"{base}. {closing}"
    return polish(sentence)
