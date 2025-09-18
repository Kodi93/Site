"""Helpers for generating roundup articles and synthetic products."""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Sequence

from .affiliates import amazon_search_link
from .article_repository import ArticleRepository
from .config import DATA_DIR
from .models import GeneratedProduct, RoundupArticle, RoundupItem
from .repository import ProductRepository
from .text import intro_breakdown, intro_roundup, title_roundup, desc_roundup
from .utils import slugify, timestamp

BASE_DIR = Path(__file__).resolve().parent.parent
ROUNDUP_CONFIG_FILE = BASE_DIR / "config" / "roundups.json"

DEFAULT_BULLETS = [
    "Quick to set up",
    "Useful daily features",
    "Compact footprint",
    "Giftable packaging",
]
DEFAULT_CAVEATS = [
    "Price fluctuates",
    "Specs vary by seller",
]


def load_roundup_config(path: Path) -> Sequence[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Roundup configuration not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Roundup configuration must be a list of topic definitions.")
    return payload


def pick_combinations(
    config: Sequence[dict],
    *,
    limit: int = 15,
    seed: str | None = None,
) -> List[tuple[str, int]]:
    options: List[tuple[str, int]] = []
    for entry in config:
        topic = str(entry.get("topic") or "").strip()
        caps = entry.get("caps") or []
        if not topic or not isinstance(caps, list):
            continue
        for cap in caps:
            try:
                cap_value = int(cap)
            except (TypeError, ValueError):
                continue
            options.append((topic, cap_value))
    if not options:
        return []
    seed_value = seed or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rng = random.Random(seed_value)
    rng.shuffle(options)
    return options[:limit]


def synthesize_item_names(topic: str) -> List[str]:
    words = [word for word in topic.split() if word]
    if not words:
        words = ["gift"]
    first = words[0]
    last = words[-1]
    composite = " ".join(words)
    templates = [
        f"Compact {first} Tool",
        f"Mini {last.title()} Kit",
        f"{first.title()} Pro Set",
        f"Pocket {last.title()}",
        f"Smart {composite.title()}",
        f"Ultra-Light {first.title()}",
        f"Foldable {last.title()}",
        f"Rechargeable {composite.title()}",
        f"{first.title()} Gift Pack",
        f"{last.title()} Starter",
    ]
    seen: set[str] = set()
    results: List[str] = []
    for template in templates:
        candidate = " ".join(template.split())
        if candidate not in seen:
            seen.add(candidate)
            results.append(candidate)
    while len(results) < 10:
        fallback = f"{first.title()} {len(results) + 1} Kit"
        if fallback not in seen:
            seen.add(fallback)
            results.append(fallback)
    return results[:10]


def build_generated_product(
    name: str,
    topic: str,
    cap: int,
    *,
    rank: int,
) -> GeneratedProduct:
    query = f"{name} {topic} under ${cap}"
    affiliate = amazon_search_link(query)
    slug = slugify(f"{name}-{topic}-under-{cap}")
    product = GeneratedProduct(
        slug=slug,
        name=name,
        query=query,
        affiliate_url=affiliate,
        intro=intro_breakdown(name, cap),
        bullets=list(DEFAULT_BULLETS),
        caveats=list(DEFAULT_CAVEATS),
        category=topic,
        price_cap=cap,
        status="published",
        score=max(0, 100 - rank),
    )
    product.mark_published()
    return product


def build_roundup(
    topic: str,
    cap: int,
    products: Sequence[GeneratedProduct],
) -> RoundupArticle:
    slug = slugify(f"top-10-{topic}-under-{cap}")
    items = [
        RoundupItem(
            rank=index,
            title=product.name,
            product_slug=product.slug,
            summary=(
                f"Why it fits: {product.name} nails the {topic} brief under ${cap} with gift-ready utility."
            ),
        )
        for index, product in enumerate(products, start=1)
    ]
    roundup = RoundupArticle(
        slug=slug,
        title=title_roundup(topic, cap),
        description=desc_roundup(topic, cap),
        topic=topic,
        price_cap=cap,
        intro=intro_roundup(topic, cap),
        amazon_search_url=amazon_search_link(f"{topic} under ${cap}"),
        items=items,
        status="published",
    )
    roundup.mark_published()
    return roundup


def generate_roundups(
    *,
    config_path: Path = ROUNDUP_CONFIG_FILE,
    limit: int = 15,
    seed: str | None = None,
) -> tuple[List[RoundupArticle], List[GeneratedProduct]]:
    config = load_roundup_config(config_path)
    combinations = pick_combinations(config, limit=limit, seed=seed)
    roundups: List[RoundupArticle] = []
    generated_products: List[GeneratedProduct] = []
    for topic, cap in combinations:
        names = synthesize_item_names(topic)
        topic_products = [
            build_generated_product(name, topic, cap, rank=index)
            for index, name in enumerate(names, start=1)
        ]
        generated_products.extend(topic_products)
        roundups.append(build_roundup(topic, cap, topic_products))
    return roundups, generated_products


def run_daily_roundups(
    *,
    config_path: Path = ROUNDUP_CONFIG_FILE,
    repository: ProductRepository | None = None,
    article_repository: ArticleRepository | None = None,
    limit: int = 15,
    seed: str | None = None,
) -> tuple[List[RoundupArticle], List[GeneratedProduct]]:
    repo = repository or ProductRepository()
    article_repo = article_repository or ArticleRepository(DATA_DIR / "articles.json")
    roundups, generated_products = generate_roundups(
        config_path=config_path, limit=limit, seed=seed
    )
    for roundup in roundups:
        article_repo.upsert_roundup(roundup)
    repo.upsert_generated_products(generated_products)
    return roundups, generated_products


def cli_entry() -> None:
    roundups, products = run_daily_roundups()
    print(
        f"Created {len(roundups)} roundups and {len(products)} generated products at {timestamp()}"
    )


__all__ = [
    "ROUNDUP_CONFIG_FILE",
    "run_daily_roundups",
    "generate_roundups",
    "cli_entry",
]
