"""Pipeline that fetches products and rebuilds the static site."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Sequence
from .amazon import AmazonCredentials
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
            if new_cooldowns:
                self.repository.update_cooldowns(
                    new_cooldowns,
                    retention_days=self.cooldown_retention_days,
                    now=now,
                )
            unique_new = len({(product.retailer_slug, product.asin) for product in new_products})
            if self.minimum_daily_posts and unique_new < self.minimum_daily_posts:
                logger.warning(
                    "Only %s new products added (minimum target is %s).",
                    unique_new,
                    self.minimum_daily_posts,
                )
        combined = self.repository.upsert_products(new_products) if new_products else existing_products
        logger.info("Total products stored: %s", len(combined))
        self.generator.build(categories, combined)
        return PipelineResult(products=combined, categories=categories)

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
