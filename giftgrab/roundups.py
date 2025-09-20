"""Generate roundup guides based on topics and the current catalog."""
from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

from .generator import SiteGenerator
from .models import Guide, Product
from .pipeline import GiftPipeline
from .repository import ProductRepository
from .topics import Topic, generate_topics

LOGGER = logging.getLogger(__name__)

TARGET_ITEMS_PER_GUIDE = 20
MIN_ITEMS_PER_GUIDE = 10
STOP_WORDS = {
    "top",
    "best",
    "gifts",
    "gift",
    "right",
    "now",
    "under",
    "from",
    "for",
    "the",
    "a",
    "and",
    "of",
    "ideas",
    "20",
    "30",
    "40",
    "50",
}


def _score_product(product: Product) -> tuple:
    rating = float(product.rating or 0.0)
    reviews = int(product.rating_count or 0)
    try:
        updated = datetime.fromisoformat(product.updated_at).timestamp()
    except Exception:  # pragma: no cover - unexpected formats
        updated = 0.0
    return (rating, reviews, updated)


def _tokenize(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _topic_tokens(topic: Topic) -> set[str]:
    tokens = _tokenize(topic.title)
    return {token for token in tokens if token not in STOP_WORDS}


def _field_contains(field: str | None, needle: str) -> bool:
    if not field:
        return False
    return needle in field.lower()


def _matches_topic(product: Product, topic: Topic) -> bool:
    if topic.price_cap is not None:
        if product.price is None or product.price > topic.price_cap:
            return False
    if topic.brand:
        needle = topic.brand.lower()
        if product.brand and needle in product.brand.lower():
            return True
        return needle in product.title.lower()
    if topic.category:
        needle = topic.category.lower()
        return any(
            _field_contains(field, needle)
            for field in (product.category, product.title, product.brand)
        )
    topic_tokens = _topic_tokens(topic)
    if not topic_tokens:
        return True
    product_tokens = _tokenize(product.title)
    product_tokens.update(_tokenize(product.category))
    product_tokens.update(_tokenize(product.brand))
    return bool(topic_tokens & product_tokens)


def _rank_products(products: Sequence[Product]) -> List[Product]:
    return sorted(products, key=_score_product, reverse=True)


def _select_products_for_topic(
    topic: Topic,
    ranked_products: Sequence[Product],
) -> List[Product]:
    chosen: List[Product] = []
    seen_ids: set[str] = set()
    for product in ranked_products:
        if product.id in seen_ids:
            continue
        if _matches_topic(product, topic):
            chosen.append(product)
            seen_ids.add(product.id)
        if len(chosen) >= TARGET_ITEMS_PER_GUIDE:
            break
    if len(chosen) < MIN_ITEMS_PER_GUIDE:
        for product in ranked_products:
            if product.id in seen_ids:
                continue
            chosen.append(product)
            seen_ids.add(product.id)
            if len(chosen) >= TARGET_ITEMS_PER_GUIDE:
                break
    if len(chosen) < MIN_ITEMS_PER_GUIDE:
        raise RuntimeError(
            f"Not enough products for {topic.title} ({len(chosen)})"
        )
    return chosen[:TARGET_ITEMS_PER_GUIDE]


def _guide_description(topic: Topic) -> str:
    focus = topic.title.lower()
    return (
        f"Automated daily refresh spotlighting {focus} gift ideas, with each pick QA'd "
        "for price accuracy, availability, and brand fit."
    )


def generate_guides(
    repository: ProductRepository,
    *,
    limit: int = 15,
) -> List[Guide]:
    products = repository.load_products()
    if len(products) < 50:
        raise RuntimeError("Inventory too small to generate guides")
    history = repository.load_topic_history()
    topics = generate_topics(products, history=history, limit=limit)
    ranked = _rank_products(products)
    guides: List[Guide] = []
    for topic in topics[:limit]:
        items = _select_products_for_topic(topic, ranked)
        guide = Guide(
            slug=topic.slug,
            title=topic.title,
            description=_guide_description(topic),
            products=list(items),
        )
        guides.append(guide)
    if len(guides) < 15:
        raise RuntimeError(f"Insufficient guides generated: {len(guides)}")
    repository.save_guides(guides)
    for topic in topics[:limit]:
        repository.append_topic_history(topic.slug, topic.title)
    return guides


def cli_entry(argv: Sequence[str] | None = None) -> None:
    """Command-line entry point for daily roundup automation."""

    parser = argparse.ArgumentParser(
        description="Refresh the catalog and publish daily roundup guides.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Number of guides to generate (minimum 15).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("public"),
        help="Directory where the rendered site will be written.",
    )
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Skip refreshing the product catalog before generating guides.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.limit < 15:
        parser.error("--limit must be at least 15")

    repository = ProductRepository()

    if not args.skip_update:
        pipeline = GiftPipeline(repository=repository)
        LOGGER.info("Refreshing catalog before generating guides")
        pipeline.run()

    guides = generate_guides(repository, limit=args.limit)

    generator = SiteGenerator(output_dir=args.output)
    products = repository.load_products()
    generator.build(products=products, guides=guides)
    LOGGER.info("Generated %s guides in %s", len(guides), args.output)


if __name__ == "__main__":
    cli_entry()
