"""Pipeline that fetches products and rebuilds the static site."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .amazon import AmazonCredentials, AmazonProductClient
from .blog import generate_blog_post
from .config import CategoryDefinition
from .models import Category, Product
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
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.categories_config = categories
        self.credentials = credentials
        self.client: AmazonProductClient | None = (
            AmazonProductClient(credentials) if credentials else None
        )

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
        if not regenerate_only:
            if not self.client:
                raise RuntimeError(
                    "Amazon credentials are required for fetching products. Set AMAZON_PAAPI_ACCESS_KEY, "
                    "AMAZON_PAAPI_SECRET_KEY, and AMAZON_ASSOCIATE_TAG."
                )
            for definition in self.categories_config:
                items = self.client.search_items(keywords=definition.keywords, item_count=item_count)
                logger.info(
                    "Fetched %s products for %s", len(items), definition.name
                )
                for item in items:
                    product = self._build_product(item, definition)
                    new_products.append(product)
        combined = self.repository.upsert_products(new_products) if new_products else existing_products
        logger.info("Total products stored: %s", len(combined))
        self.generator.build(categories, combined)
        return PipelineResult(products=combined, categories=categories)

    def _build_product(self, item: dict, definition: CategoryDefinition) -> Product:
        asin = item.get("asin") or item.get("ASIN")
        if not asin:
            raise ValueError("Amazon response missing ASIN")
        title = item.get("title") or "Untitled Amazon Find"
        partner_tag = self.credentials.partner_tag if self.credentials else None
        link = ensure_partner_tag(item.get("detail_page_url"), partner_tag)
        image = item.get("image_url")
        price = item.get("price")
        features = item.get("features") or []
        keywords = list(definition.keywords)
        for feature in features:
            if feature and feature not in keywords:
                keywords.append(feature)
        product = Product(
            asin=asin,
            title=title,
            link=link,
            image=image,
            price=price,
            rating=None,
            total_reviews=None,
            category_slug=definition.slug,
            keywords=keywords[:12],
        )
        blog = generate_blog_post(product, definition.name, features)
        product.summary = blog.summary
        product.blog_content = blog.html
        return product


def ensure_partner_tag(url: str | None, partner_tag: str | None) -> str:
    if not url:
        return "https://www.amazon.com/"
    if not partner_tag:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query["tag"] = partner_tag
    new_query = urlencode(query)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))
