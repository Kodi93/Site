"""Pipeline that fetches products and rebuilds the static site."""
from __future__ import annotations

import logging
import math
import re
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Sequence, Tuple
from .amazon import AmazonCredentials
from .article_repository import ArticleRepository
from .article_scheduler import ArticleAutomation
from .blog import generate_blog_post
from .config import CategoryDefinition
from .models import (
    Category,
    CooldownEntry,
    GeneratedProduct,
    Product,
    RoundupArticle,
)
from .retailers import AmazonRetailerAdapter, RetailerAdapter
from .repository import ProductRepository

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    products: List[Product]
    categories: List[Category]


class GiftPipeline:
    """Coordinate product ingestion, copy generation, and site rebuilds.

    The pipeline seeds a high-quality catalog up to ``bootstrap_target`` on the
    first few runs and then enforces a tighter ``minimum_daily_posts`` quota for
    subsequent refreshes. Each run scores potential additions by ratings,
    reviews, and copy depth so the daily picks stay campaign-ready while still
    aggregating listings from each configured retailer.
    """

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
        bootstrap_target: int = 100,
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
        self.bootstrap_target = max(self.minimum_daily_posts, bootstrap_target)

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
        existing_count = len(existing_products)
        target_total = self.minimum_daily_posts
        if existing_count < self.bootstrap_target:
            deficit = self.bootstrap_target - existing_count
            target_total = max(deficit, self.minimum_daily_posts)
            logger.info(
                "Bootstrap mode active: aiming for %s net new products (existing=%s, target=%s)",
                target_total,
                existing_count,
                self.bootstrap_target,
            )
        else:
            logger.info(
                "Daily cadence active: aiming for %s new products", self.minimum_daily_posts
            )
        if not regenerate_only:
            if not self.retailers:
                raise RuntimeError(
                    "At least one retailer adapter is required when fetching new products."
                )
            desired_item_count = item_count
            if self.minimum_daily_posts:
                desired_item_count = max(desired_item_count, self.minimum_daily_posts)
            if target_total > 0:
                per_category_target = math.ceil(
                    target_total / max(1, len(self.categories_config))
                )
                desired_item_count = max(desired_item_count, per_category_target)
            if desired_item_count != item_count:
                logger.info(
                    "Requested item_count %s below target %s; adjusting.",
                    item_count,
                    desired_item_count,
                )
                item_count = desired_item_count
            cooldown_entries = self.repository.prune_cooldowns(
                self.cooldown_retention_days, now=now
            )
            active_cooldown_keys = {
                entry.key
                for entry in cooldown_entries
                if entry.is_active(self.cooldown_days, now)
            }
            candidate_pool: Dict[Tuple[str, str], Tuple[Product, float]] = {}
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
                        score = self._quality_score(product)
                        existing = candidate_pool.get(key)
                        if existing is None or score > existing[1]:
                            candidate_pool[key] = (product, score)
            ordered_candidates = sorted(
                candidate_pool.values(), key=lambda pair: pair[1], reverse=True
            )
            if target_total:
                reserved: List[Tuple[Product, float]] = []
                reserved_keys: set[Tuple[str, str]] = set()
                seen_retailers: set[str] = set()

                for product, score in ordered_candidates:
                    if product.retailer_slug in seen_retailers:
                        continue
                    reserved.append((product, score))
                    reserved_keys.add((product.retailer_slug, product.asin))
                    seen_retailers.add(product.retailer_slug)

                if len(reserved) < target_total:
                    for product, score in ordered_candidates:
                        key = (product.retailer_slug, product.asin)
                        if key in reserved_keys:
                            continue
                        reserved.append((product, score))
                        reserved_keys.add(key)
                        if len(reserved) >= target_total:
                            break

                ordered_candidates = reserved
            new_products = [product for product, _ in ordered_candidates]
            for product in new_products:
                key = (product.retailer_slug, product.asin)
                new_entry = CooldownEntry(
                    retailer_slug=product.retailer_slug,
                    asin=product.asin,
                    category_slug=product.category_slug,
                )
                new_cooldowns.append(new_entry)
                active_cooldown_keys.add(key)
            unique_new = len(new_products)
            desired_new = target_total
            if desired_new and unique_new < desired_new:
                shortfall = desired_new - unique_new
                logger.warning(
                    "Only %s new products added (minimum target is %s). Attempting to backfill %s slot%s with existing listings.",
                    unique_new,
                    desired_new,
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
        generated_products: List[GeneratedProduct] = (
            self.repository.load_generated_products()
        )
        roundups: List[RoundupArticle] = []
        if self.article_repository is not None:
            try:
                roundups = self.article_repository.list_published_roundups()
            except Exception as error:
                logger.warning("Unable to load roundup articles: %s", error)
        best_generated = self.repository.best_generated_product()
        self.generator.build(
            categories,
            combined,
            articles=articles,
            generated_products=generated_products,
            roundups=roundups,
            best_generated=best_generated,
        )
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
    def _blog_word_count(content: str | None) -> int:
        if not content:
            return 0
        text = re.sub(r"<[^>]+>", " ", content)
        words = [segment for segment in text.split() if segment.strip()]
        return len(words)

    @classmethod
    def _quality_score(cls, product: Product) -> float:
        score = 0.0
        rating_value: float | None = None
        if product.rating is not None:
            try:
                rating_value = float(product.rating)
            except (TypeError, ValueError):
                rating_value = None
        if rating_value is not None:
            if rating_value > 0:
                score += rating_value * 120.0
            else:
                score -= 40.0
        reviews_value: float | None = None
        if product.total_reviews is not None:
            try:
                reviews_value = float(product.total_reviews)
            except (TypeError, ValueError):
                reviews_value = None
        if reviews_value is not None:
            if reviews_value > 0:
                score += min(reviews_value, 500.0) * 0.6
            else:
                score -= 20.0
        if product.price:
            score += 12.0
        if product.image:
            score += 8.0
        if product.summary:
            score += min(len(product.summary.split()), 60)
        blog_words = cls._blog_word_count(product.blog_content)
        if blog_words:
            score += min(blog_words, 400)
        else:
            score -= 25.0
        if product.brand:
            score += 5.0
        return score

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
