"""One-off script to regenerate professional SEO summaries for stored products."""
from __future__ import annotations

import logging
from pathlib import Path

from giftgrab.blog import generate_blog_post
from giftgrab.quality import SeoPayload, passes_seo
from giftgrab.repository import ProductRepository, get_category_definition
from giftgrab.text import TitleParams, make_title

logger = logging.getLogger(__name__)


def _resolve_category_name(slug: str) -> str:
    definition = get_category_definition(slug)
    if definition:
        return definition.name
    return slug.replace("-", " ").title() or "Gifts"


def reseo(data_file: Path | None = None) -> None:
    """Regenerate summaries and blog content for every stored product."""

    repo = ProductRepository(data_file=data_file)
    products = repo.load_products()
    updated = []
    for product in products:
        category_name = _resolve_category_name(product.category_slug)
        blog = generate_blog_post(product, category_name, [])
        product.summary = blog.summary
        product.blog_content = blog.html
        seo_title = make_title(
            TitleParams(
                name=product.title,
                brand=product.brand,
                category=category_name,
                use=(product.keywords[0] if product.keywords else None),
            )
        )
        payload = SeoPayload(title=seo_title, description=blog.summary, body=blog.html)
        if not passes_seo(payload):
            logger.warning("SEO quality gate failed for %s", product.asin)
        updated.append(product)
    repo.save_products(updated)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reseo()
