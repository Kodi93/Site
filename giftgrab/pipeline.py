"""Pipeline that fetches products and rebuilds the static site."""
from __future__ import annotations

import logging
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Sequence
from .amazon import AmazonCredentials
from .article_repository import ArticleRepository
from .article_scheduler import ArticleAutomation
from .blog import generate_blog_post
from .config import CategoryDefinition
from .models import Category, CooldownEntry, Product
from .retailers import AmazonRetailerAdapter, RetailerAdapter
from .repository import ProductRepository

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    products: List[Product]
    categories: List[Category]


class GiftPipeline:
    """High level workflow that aggregates Amazon items and rebuilds the site."""

    def __init__(
        self,
        *,
        repository: ProductRepository,
        generator,
        categories: Sequence[CategoryDefinition],
        credentials: AmazonCredentials | None = None,
        retailers: Sequence[RetailerAdapter] | None = None,
        article_repository: ArticleRepository | None = None,
        cooldown_days: int = 15,
        cooldown_retention_days: int = 30,
        minimum_daily_posts: int = 5,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.categories_config = categories
        self.credentials = credentials
        if retailers is not None:
            self.retailers: List[RetailerAdapter] = list(retailers)
        elif credentials is not None:
            self.retailers = [AmazonRetailerAdapter(credentials)]
        else:
            self.retailers = []
        self.article_repository = article_repository
        self.article_automation = (
            ArticleAutomation(article_repository)
            if article_repository is not None
            else None
        )
        self.cooldown_days = max(0, cooldown_days)
        self.cooldown_retention_days = max(0, cooldown_retention_days)
        self.minimum_daily_posts = max(0, minimum_daily_posts)

    def run(self, *, item_count: int = 6, regenerate_only: bool = False) -> PipelineResult:
        logger.info("Starting pipeline regenerate_only=%s", regenerate_only)
        existing_products = self.repository.load_products()
        categories = [
            Category(
                slug=definition.slug,
                name=definition.name,
                blurb=definition.blurb,
                keywords=definition.keywords,
            )
            for definition in self.categories_config
        ]
        new_products: List[Product] = []
        new_cooldowns: List[CooldownEntry] = []
        fallback_products: List[Product] = []
        now = datetime.now(timezone.utc)
        active_cooldown_keys: set[tuple[str, str]] = set()
        if not regenerate_only:
            if not self.retailers:
                raise RuntimeError(
                    "At least one retailer adapter is required when fetching new products."
                )
            if self.minimum_daily_posts and item_count < self.minimum_daily_posts:
                logger.info(
                    "Requested item_count %s below minimum %s; adjusting.",
                    item_count,
                    self.minimum_daily_posts,
                )
                item_count = self.minimum_daily_posts
            cooldown_entries = self.repository.prune_cooldowns(
                self.cooldown_retention_days, now=now
            )
            active_cooldown_keys = {
                entry.key
                for entry in cooldown_entries
                if entry.is_active(self.cooldown_days, now)
            }
            for retailer in self.retailers:
                for definition in self.categories_config:
                    items = retailer.search_items(
                        keywords=definition.keywords, item_count=item_count
                    )
                    logger.info(
                        "Fetched %s products for %s from %s",
                        len(items),
                        definition.name,
                        retailer.name,
                    )
                    for item in items:
                        product = self._build_product(item, definition, retailer)
                        key = (product.retailer_slug, product.asin)
                        if key in active_cooldown_keys:
                            logger.debug(
                                "Skipping %s from %s due to active cooldown",
                                product.asin,
                                product.retailer_slug,
                            )
                            continue
                        new_products.append(product)
                        new_entry = CooldownEntry(
                            retailer_slug=product.retailer_slug,
                            asin=product.asin,
                            category_slug=product.category_slug,
                        )
                        new_cooldowns.append(new_entry)
                        active_cooldown_keys.add(key)
            unique_new = len(
                {(product.retailer_slug, product.asin) for product in new_products}
            )
            if self.minimum_daily_posts and unique_new < self.minimum_daily_posts:
                shortfall = self.minimum_daily_posts - unique_new
                logger.warning(
                    "Only %s new products added (minimum target is %s). Attempting to backfill %s slot%s with existing listings.",
                    unique_new,
                    self.minimum_daily_posts,
                    shortfall,
                    "" if shortfall == 1 else "s",
                )
                fallback_products = self._select_fallback_products(
                    existing_products,
                    required=shortfall,
                    active_cooldown_keys=active_cooldown_keys,
                )
                if fallback_products:
                    counts = Counter(
                        product.category_slug for product in fallback_products
                    )
                    for product in fallback_products:
                        if product.price:
                            product.record_price(product.price)
                        else:
                            product.touch()
                        key = (product.retailer_slug, product.asin)
                        active_cooldown_keys.add(key)
                        new_cooldowns.append(
                            CooldownEntry(
                                retailer_slug=product.retailer_slug,
                                asin=product.asin,
                                category_slug=product.category_slug,
                            )
                        )
                    logger.info(
                        "Backfilled %s fallback product%s to reach the daily minimum.",
                        len(fallback_products),
                        "" if len(fallback_products) == 1 else "s",
                    )
                    logger.debug(
                        "Fallback distribution by category: %s",
                        dict(counts),
                    )
                remaining_shortfall = shortfall - len(fallback_products)
                if remaining_shortfall > 0:
                    logger.warning(
                        "Daily quota remains short by %s item%s after fallback selection.",
                        remaining_shortfall,
                        "" if remaining_shortfall == 1 else "s",
                    )
        if new_cooldowns:
            self.repository.update_cooldowns(
                new_cooldowns,
                retention_days=self.cooldown_retention_days,
                now=now,
            )
        updates_to_apply: List[Product] = []
        if new_products:
            updates_to_apply.extend(new_products)
        if fallback_products:
            updates_to_apply.extend(fallback_products)
        combined = (
            self.repository.upsert_products(updates_to_apply)
            if updates_to_apply
            else existing_products
        )
        logger.info("Total products stored: %s", len(combined))
        articles = []
        if self.article_automation and self.article_repository:
            try:
                self.article_automation.generate(combined, now=now)
            except Exception as error:
                logger.warning("Article automation failed: %s", error)
            articles = self.article_repository.list_published()
        self.generator.build(categories, combined, articles=articles)
        return PipelineResult(products=combined, categories=categories)

    def _select_fallback_products(
        self,
        existing_products: List[Product],
        *,
        required: int,
        active_cooldown_keys: set[tuple[str, str]],
    ) -> List[Product]:
        if required <= 0:
            return []
        pools: dict[str, deque[Product]] = {}
        for product in existing_products:
            key = (product.retailer_slug, product.asin)
            if key in active_cooldown_keys:
                continue
            pools.setdefault(product.category_slug, []).append(product)

        def sort_key(item: Product) -> tuple[float, float, float, float]:
            drop = item.price_drop_percent() or 0.0
            rating = item.rating or 0.0
            reviews = float(item.total_reviews or 0)
            updated = self._parse_timestamp(item.updated_at)
            updated_ts = updated.timestamp() if updated else 0.0
            return (-drop, -rating, -reviews, updated_ts)

        ordered_pools: dict[str, deque[Product]] = {}
        for slug, items in pools.items():
            ordered = sorted(items, key=sort_key)
            ordered_pools[slug] = deque(ordered)
        if not ordered_pools:
            return []

        ordered_slugs: List[str] = [
            definition.slug
            for definition in self.categories_config
            if definition.slug in ordered_pools
        ]
        for slug in ordered_pools:
            if slug not in ordered_slugs:
                ordered_slugs.append(slug)

        selected: List[Product] = []
        while len(selected) < required and ordered_pools:
            progress = False
            for slug in ordered_slugs:
                queue = ordered_pools.get(slug)
                while queue and len(selected) < required:
                    candidate = queue.popleft()
                    selected.append(candidate)
                    progress = True
                    break
            if not progress:
                break
            for slug in list(ordered_pools.keys()):
                if not ordered_pools[slug]:
                    ordered_pools.pop(slug)
        return selected[:required]

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _build_product(
        self, item: dict, definition: CategoryDefinition, retailer: RetailerAdapter
    ) -> Product:
        product_id = item.get("id") or item.get("asin") or item.get("ASIN")
        if not product_id:
            raise ValueError("Retailer response missing product identifier")
        title = item.get("title") or "Untitled marketplace find"
        link = retailer.decorate_url(item.get("url") or item.get("detail_page_url"))
        image = item.get("image") or item.get("image_url")
        price = item.get("price")
        features = item.get("features") or []
        rating_value = item.get("rating")
        total_reviews_value = item.get("total_reviews")
        extra_keywords = item.get("keywords") or []
        explicit_slug = (item.get("category_slug") or "").strip()
        if explicit_slug and explicit_slug != definition.slug:
            for candidate in self.categories_config:
                if candidate.slug == explicit_slug:
                    definition = candidate
                    break
        explicit_category_name = (item.get("category") or "").strip()
        raw_brand = item.get("brand")
        brand = None
        if raw_brand not in (None, ""):
            brand = str(raw_brand).strip()
            if not brand:
                brand = None

        def _as_float(value):
            if value is None:
                return None
            try:
                return float(str(value).replace(",", ""))
            except (TypeError, ValueError):
                return None

        def _as_int(value):
            if value is None:
                return None
            try:
                return int(float(str(value).replace(",", "")))
            except (TypeError, ValueError):
                return None

        rating = _as_float(rating_value)
        total_reviews = _as_int(total_reviews_value)
        keywords = list(definition.keywords)
        for feature in features:
            if feature and feature not in keywords:
                keywords.append(feature)
        for keyword in extra_keywords:
            if keyword and keyword not in keywords:
                keywords.append(keyword)
        if explicit_category_name:
            normalized_name = explicit_category_name.lower()
            if normalized_name not in (kw.lower() for kw in keywords):
                keywords.append(explicit_category_name)
        cta_label = getattr(retailer, "cta_label", None) or f"Shop on {retailer.name}"
        product = Product(
            asin=str(product_id),
            title=title,
            link=link,
            image=image,
            price=price,
            rating=rating,
            total_reviews=total_reviews,
            category_slug=definition.slug,
            brand=brand,
            keywords=keywords[:12],
            retailer_slug=getattr(retailer, "slug", "marketplace"),
            retailer_name=getattr(retailer, "name", "Marketplace"),
            retailer_homepage=getattr(retailer, "homepage", None),
            call_to_action=cta_label,
        )
        blog = generate_blog_post(product, definition.name, features)
        product.summary = blog.summary
        product.blog_content = blog.html
        product.record_price(price)
        return product
