from __future__ import annotations

from pathlib import Path

from giftgrab.config import SiteSettings
from giftgrab.generator import SiteGenerator
from giftgrab.models import Category, Product


def build_generator(tmp_path: Path) -> SiteGenerator:
    settings = SiteSettings(
        site_name="Test Site",
        base_url="https://example.com",
    )
    return SiteGenerator(settings, output_dir=tmp_path)


def make_product(*, category_slug: str, image: str | None = None) -> Product:
    return Product(
        asin="TESTASIN",
        title="Test Product",
        link="https://example.com/product",
        image=image,
        price=None,
        rating=None,
        total_reviews=None,
        category_slug=category_slug,
        summary="Test summary",
    )


def test_product_card_uses_category_fallback_when_image_missing(tmp_path: Path) -> None:
    generator = build_generator(tmp_path)
    category = Category(slug="gadgets", name="Gadgets", blurb="Gadget gifts", keywords=["gadgets"])
    generator._category_lookup = {category.slug: category}
    product = make_product(category_slug=category.slug, image=None)

    card_html = generator._product_card(product)

    assert 'src="https://source.unsplash.com/600x400/?gadgets"' in card_html


def test_product_card_fallback_defaults_to_category_slug(tmp_path: Path) -> None:
    generator = build_generator(tmp_path)
    product = make_product(category_slug="toys", image=None)

    card_html = generator._product_card(product)

    assert 'src="https://source.unsplash.com/600x400/?toys"' in card_html
