"""Helpers for generating roundup articles and synthetic products."""
from __future__ import annotations

import argparse
import json
import random
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from .affiliates import amazon_search_link
from .article_repository import ArticleRepository
from .config import DATA_DIR
from .models import GeneratedProduct, RoundupArticle, RoundupItem
from .repository import ProductRepository
from .text import clamp, clean_text, desc_roundup, intro_roundup, title_roundup
from .utils import slugify, timestamp

BASE_DIR = Path(__file__).resolve().parent.parent
ROUNDUP_CONFIG_FILE = BASE_DIR / "config" / "roundups.json"
ROUNDUPS_PER_DAY_DEFAULT = 15
ROUNDUP_PRODUCT_COUNT = 10

HIGHLIGHT_TONES = [
    "playful",
    "polished",
    "clever",
    "purposeful",
    "low-key",
]

HIGHLIGHT_AUDIENCES = [
    "coworkers",
    "teens",
    "parents",
    "frequent travelers",
    "gearheads",
    "college students",
    "roommates",
    "clients",
]

PRODUCT_DESCRIPTORS = [
    "Essential",
    "Curated",
    "Weekend",
    "Signature",
    "Compact",
    "Premium",
    "Ready",
    "Everyday",
    "Rapid",
    "Giftable",
]

PRODUCT_MODIFIERS = [
    "Kit",
    "Bundle",
    "Set",
    "Capsule",
    "Playbook",
    "Edit",
    "Sampler",
    "Stack",
    "Field Pack",
    "Starter",
    "Companion",
    "Duo",
]


def _compose_slug(*parts: str) -> str:
    return slugify("-".join(str(part) for part in parts if part))


def _normalize_topic_words(topic: str) -> List[str]:
    words = [word for word in re.split(r"[^a-z0-9]+", topic.lower()) if word]
    return words or ["gift"]


def _friendly_topic_focus(topic: str) -> str:
    words = _normalize_topic_words(topic)
    if len(words) > 1 and words[-1] in {"gifts", "gift", "ideas"}:
        words = words[:-1]
    return " ".join(words) or "gift"


def _topic_title(words: Iterable[str]) -> str:
    return " ".join(word.title() for word in words if word)


def _pairing_phrase(focus: str) -> str:
    if not focus:
        return "other gift ideas"
    if focus.endswith("s"):
        return f"other {focus} upgrades"
    return f"{focus} add-ons"


def _edition_label_for_date(value: date | None) -> str | None:
    if value is None:
        return None
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _to_iso(when: datetime | None) -> str | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).isoformat()


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
    limit: int = ROUNDUPS_PER_DAY_DEFAULT,
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


def synthesize_item_names(
    topic: str,
    *,
    seed: str | None = None,
    edition_label: str | None = None,
) -> List[str]:
    words = _normalize_topic_words(topic)
    focus_title = _topic_title(words)
    primary = words[-1]
    singular = primary[:-1] if primary.endswith("s") and len(primary) > 3 else primary
    singular_title = singular.title()
    month_hint = None
    if edition_label:
        month_hint = edition_label.split()[0]

    base_names: List[str] = []
    for descriptor in PRODUCT_DESCRIPTORS:
        for modifier in PRODUCT_MODIFIERS:
            base_names.append(f"{descriptor} {focus_title} {modifier}")
            base_names.append(f"{descriptor} {singular_title} {modifier}")
    if month_hint:
        base_names.extend(
            [
                f"{month_hint} {focus_title} Capsule",
                f"{month_hint} {singular_title} Edit",
                f"{month_hint} {focus_title} Drop",
            ]
        )
    rng = random.Random(f"{seed or focus_title}-{month_hint or ''}")
    rng.shuffle(base_names)
    results: List[str] = []
    seen: set[str] = set()
    for name in base_names:
        candidate = " ".join(name.split())
        if candidate not in seen:
            seen.add(candidate)
            results.append(candidate)
        if len(results) == ROUNDUP_PRODUCT_COUNT:
            break
    while len(results) < ROUNDUP_PRODUCT_COUNT:
        fallback = f"{focus_title} Idea {len(results) + 1}"
        if fallback not in seen:
            seen.add(fallback)
            results.append(fallback)
    return results[:ROUNDUP_PRODUCT_COUNT]


def _compose_product_intro(
    name: str,
    topic: str,
    cap: int,
    edition_label: str | None,
) -> str:
    focus = _friendly_topic_focus(topic)
    edition_phrase = edition_label or "this week"
    price_fragment = f" under ${cap}" if cap else ""
    focus_fragment = f" for {focus}" if focus else ""
    intro = (
        f"{clean_text(name)} is a practical pick{focus_fragment}{price_fragment}. "
        f"Curated for {edition_phrase.lower()} gifting plans. Highlights and trade-offs below."
    )
    return clean_text(intro)


def _compose_highlights(
    *,
    topic: str,
    cap: int,
    edition_label: str | None,
    rank: int,
    rng: random.Random,
) -> List[str]:
    focus = _friendly_topic_focus(topic)
    edition_phrase = (edition_label or "this week").lower()
    pairing = _pairing_phrase(focus)
    tone = rng.choice(HIGHLIGHT_TONES)
    audience = rng.choice(HIGHLIGHT_AUDIENCES)
    bullet_templates = [
        "Ranks #{rank} in our {edition_phrase} shortlist for {focus} fans.",
        "Keeps total spend safely under ${cap} even when prices swing.",
        "Arrives ready to gift with packaging you won't need to overhaul.",
        "Pairs well with {pairing} if you want to build a bundle.",
        "Balances practical utility with {tone} flair recipients notice.",
        "Leaves room in the ${cap} budget for a handwritten card or add-on.",
        "Ships quickly so last-minute gifting still lands on time.",
        "Easy to explain in a quick message—no tech brief required.",
        "Well-reviewed pick that keeps Amazon feedback trending positive.",
        "Compact footprint so it works for small spaces or travel bags.",
        "Ideal for {audience} when you need something thoughtful but useful.",
    ]
    bullets: List[str] = []
    seen: set[str] = set()
    for template in bullet_templates:
        candidate = template.format(
            rank=rank,
            edition_phrase=edition_phrase,
            focus=focus,
            cap=cap,
            pairing=pairing,
            tone=tone,
            audience=audience,
        )
        text = clean_text(candidate)
        if text and text not in seen:
            seen.add(text)
            bullets.append(text)
    rng.shuffle(bullets)
    return bullets[:4]


def _compose_caveats(
    *, topic: str, cap: int, edition_label: str | None, rng: random.Random
) -> List[str]:
    focus = _friendly_topic_focus(topic)
    edition_phrase = edition_label or "the season"
    caveat_templates = [
        "Inventory can tighten around major {edition_phrase} shopping peaks—order early.",
        "Listings sometimes mix colors or bundles; verify the variant before checkout.",
        "Accessories pictured may be add-ons, so scan the fine print first.",
        "Prices occasionally creep a few dollars above ${cap}; clip coupons when offered.",
        "Packaging arrives in a standard Amazon box—add wrapping if presentation matters.",
        "Allow a few extra days for shipping if gifting to {focus} fans overseas.",
    ]
    caveats: List[str] = []
    seen: set[str] = set()
    for template in caveat_templates:
        candidate = template.format(
            edition_phrase=edition_phrase.lower(), cap=cap, focus=focus
        )
        text = clean_text(candidate)
        if text and text not in seen:
            seen.add(text)
            caveats.append(text)
    rng.shuffle(caveats)
    return caveats[:3]


def _compose_roundup_intro(
    topic: str, cap: int, edition_label: str | None
) -> str:
    base = intro_roundup(topic, cap)
    if not edition_label:
        return base
    extra = clean_text(f"Updated for {edition_label} gifting plans.")
    combined = clean_text(f"{base} {extra}")
    return combined


def _compose_roundup_description(
    topic: str, cap: int, edition_label: str | None
) -> str:
    base = desc_roundup(topic, cap)
    if not edition_label:
        return base
    extra = clean_text(f"Refreshed for {edition_label} shoppers.")
    return clamp(clean_text(f"{base} {extra}"), 155)


def _compose_roundup_title(
    topic: str, cap: int, edition_label: str | None
) -> str:
    title = title_roundup(topic, cap)
    if not edition_label:
        return title
    combined = clean_text(f"{title} – {edition_label}")
    return clamp(combined, 60)


def _compose_roundup_summary(
    *,
    topic: str,
    cap: int,
    edition_label: str | None,
    rank: int,
    product: GeneratedProduct,
) -> str:
    focus = _friendly_topic_focus(topic)
    edition_phrase = (edition_label or "this week").lower()
    base = f"Ranks #{rank} for {focus} gifting under ${cap} in {edition_phrase}."
    detail_pool = list(product.bullets[:2]) or [
        "Balances novelty with real-world utility.",
    ]
    rng = random.Random(f"summary-{product.slug}-{rank}")
    detail_pool.extend(
        [
            "Lands well with busy recipients who want ready-to-use gear.",
            "Easy win when you need a thoughtful pick without research marathons.",
        ]
    )
    rng.shuffle(detail_pool)
    detail = detail_pool[0].rstrip(".")
    summary = clean_text(f"{base} {detail}.")
    return summary


def build_generated_product(
    name: str,
    topic: str,
    cap: int,
    *,
    rank: int,
    edition_label: str | None,
    slug_suffix: str | None,
    published_at: datetime | None,
    seed: str | None,
) -> GeneratedProduct:
    query = f"{name} {topic} under ${cap}"
    affiliate = amazon_search_link(query)
    slug = _compose_slug(name, topic, f"under-{cap}", slug_suffix)
    rng = random.Random(seed or slug)
    bullets = _compose_highlights(
        topic=topic, cap=cap, edition_label=edition_label, rank=rank, rng=rng
    )
    caveats = _compose_caveats(
        topic=topic, cap=cap, edition_label=edition_label, rng=rng
    )
    intro = _compose_product_intro(name, topic, cap, edition_label)
    publish_iso = _to_iso(published_at)
    score = max(50, 120 - rank * 5 + rng.randint(0, 8))
    product = GeneratedProduct(
        slug=slug,
        name=name,
        query=query,
        affiliate_url=affiliate,
        intro=intro,
        bullets=bullets,
        caveats=caveats,
        category=topic,
        price_cap=cap,
        status="published",
        score=score,
    )
    if publish_iso:
        product.mark_published(when=publish_iso)
        product.created_at = publish_iso
    else:
        product.mark_published()
    return product


def build_roundup(
    topic: str,
    cap: int,
    products: Sequence[GeneratedProduct],
    *,
    edition_label: str | None,
    slug_suffix: str | None,
    published_at: datetime | None,
) -> RoundupArticle:
    slug = _compose_slug("top-10", topic, f"under-{cap}", slug_suffix)
    publish_iso = _to_iso(published_at)
    items = [
        RoundupItem(
            rank=index,
            title=product.name,
            product_slug=product.slug,
            summary=_compose_roundup_summary(
                topic=topic,
                cap=cap,
                edition_label=edition_label,
                rank=index,
                product=product,
            ),
        )
        for index, product in enumerate(products, start=1)
    ]
    roundup = RoundupArticle(
        slug=slug,
        title=_compose_roundup_title(topic, cap, edition_label),
        description=_compose_roundup_description(topic, cap, edition_label),
        topic=topic,
        price_cap=cap,
        intro=_compose_roundup_intro(topic, cap, edition_label),
        amazon_search_url=amazon_search_link(f"{topic} under ${cap}"),
        items=items,
        status="published",
    )
    if publish_iso:
        roundup.mark_published(when=publish_iso)
        roundup.created_at = publish_iso
    else:
        roundup.mark_published()
    return roundup


def generate_roundups(
    *,
    config_path: Path = ROUNDUP_CONFIG_FILE,
    limit: int = ROUNDUPS_PER_DAY_DEFAULT,
    seed: str | None = None,
    edition_date: date | None = None,
    edition_label: str | None = None,
    slug_suffix: str | None = None,
    publish_at: datetime | None = None,
) -> tuple[List[RoundupArticle], List[GeneratedProduct]]:
    config = load_roundup_config(config_path)
    combinations = pick_combinations(config, limit=limit, seed=seed)
    roundups: List[RoundupArticle] = []
    generated_products: List[GeneratedProduct] = []
    for combo_index, (topic, cap) in enumerate(combinations, start=1):
        combo_seed = f"{seed or 'auto'}-{slug_suffix or ''}-{topic}-{cap}-{combo_index}"
        names = synthesize_item_names(
            topic, seed=combo_seed, edition_label=edition_label
        )
        base_publish_dt = (
            publish_at + timedelta(hours=combo_index - 1)
            if publish_at is not None
            else None
        )
        products_for_combo: List[GeneratedProduct] = []
        for rank, name in enumerate(names, start=1):
            product_publish_dt = (
                base_publish_dt + timedelta(minutes=(rank - 1) * 6)
                if base_publish_dt is not None
                else None
            )
            product = build_generated_product(
                name,
                topic,
                cap,
                rank=rank,
                edition_label=edition_label,
                slug_suffix=slug_suffix,
                published_at=product_publish_dt,
                seed=f"{combo_seed}-{name}",
            )
            products_for_combo.append(product)
        roundup_publish_dt = (
            base_publish_dt + timedelta(minutes=72)
            if base_publish_dt is not None
            else None
        )
        generated_products.extend(products_for_combo)
        roundups.append(
            build_roundup(
                topic,
                cap,
                products_for_combo,
                edition_label=edition_label,
                slug_suffix=slug_suffix,
                published_at=roundup_publish_dt,
            )
        )
    return roundups, generated_products


def generate_roundups_for_span(
    *,
    config_path: Path = ROUNDUP_CONFIG_FILE,
    start_date: date | None = None,
    days: int = 1,
    limit: int = ROUNDUPS_PER_DAY_DEFAULT,
    seed: str | None = None,
) -> tuple[List[RoundupArticle], List[GeneratedProduct]]:
    effective_days = max(1, int(days))
    start = start_date or datetime.now(timezone.utc).date()
    roundups: List[RoundupArticle] = []
    products: List[GeneratedProduct] = []
    for offset in range(effective_days):
        edition_date = start + timedelta(days=offset)
        edition_label = _edition_label_for_date(edition_date)
        slug_suffix = edition_date.isoformat()
        base_publish = datetime.combine(edition_date, time(hour=6, tzinfo=timezone.utc))
        day_seed = f"{seed or 'auto'}-{slug_suffix}"
        day_roundups, day_products = generate_roundups(
            config_path=config_path,
            limit=limit,
            seed=day_seed,
            edition_date=edition_date,
            edition_label=edition_label,
            slug_suffix=slug_suffix,
            publish_at=base_publish,
        )
        roundups.extend(day_roundups)
        products.extend(day_products)
    return roundups, products


def run_daily_roundups(
    *,
    config_path: Path = ROUNDUP_CONFIG_FILE,
    repository: ProductRepository | None = None,
    article_repository: ArticleRepository | None = None,
    limit: int = ROUNDUPS_PER_DAY_DEFAULT,
    seed: str | None = None,
    days: int = 1,
    start_date: date | None = None,
) -> tuple[List[RoundupArticle], List[GeneratedProduct]]:
    repo = repository or ProductRepository()
    article_repo = article_repository or ArticleRepository(DATA_DIR / "articles.json")
    roundups, generated_products = generate_roundups_for_span(
        config_path=config_path,
        start_date=start_date,
        days=days,
        limit=limit,
        seed=seed,
    )
    for roundup in roundups:
        article_repo.upsert_roundup(roundup)
    repo.upsert_generated_products(generated_products)
    return roundups, generated_products


def cli_entry(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate roundup articles and linked product breakdowns.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=ROUNDUPS_PER_DAY_DEFAULT,
        help="Roundups to create per day (default: 15).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days of roundup content to synthesize (default: 1).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="ISO date (YYYY-MM-DD) to start scheduling from.",
    )
    parser.add_argument(
        "--seed",
        type=str,
        help="Optional seed for deterministic generation.",
    )
    args = parser.parse_args(argv)
    try:
        limit = max(1, int(args.limit))
    except (TypeError, ValueError):
        parser.error("--limit must be a positive integer")
    try:
        days = max(1, int(args.days))
    except (TypeError, ValueError):
        parser.error("--days must be a positive integer")
    start_date = None
    if args.start_date:
        try:
            start_date = date.fromisoformat(args.start_date)
        except ValueError:
            parser.error(f"Invalid --start-date value: {args.start_date}")
    roundups, products = run_daily_roundups(
        limit=limit,
        seed=args.seed,
        days=days,
        start_date=start_date,
    )
    print(
        f"Created {len(roundups)} roundups and {len(products)} generated products at {timestamp()}"
    )


__all__ = [
    "ROUNDUP_CONFIG_FILE",
    "generate_roundups",
    "generate_roundups_for_span",
    "run_daily_roundups",
    "cli_entry",
]
