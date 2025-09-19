from giftgrab.generator import SiteGenerator, polish_guide_title
from giftgrab.models import Product
from giftgrab.repository import ProductRepository
from giftgrab.roundups import generate_guides


def sample_products() -> list[Product]:
    inventory: list[Product] = []
    categories = [
        ("Cozy Home", "NestCo"),
        ("Desk Gear", "Deskify"),
        ("Coffee Gear", "BrewLab"),
        ("Outdoor Fun", "TrailSet"),
        ("Fitness Essentials", "StrideWell"),
    ]
    for category, brand in categories:
        for index in range(1, 17):
            price = 18.0 + index
            source = "amazon" if index % 4 == 0 else "ebay" if index % 3 == 0 else "curated"
            url = (
                f"https://www.amazon.com/dp/example-{category}-{index}"
                if source == "amazon"
                else f"https://example.com/{category}/{index}"
            )
            inventory.append(
                Product(
                    id=f"{category}-{index}",
                    title=f"{brand} {category} Item {index}",
                    url=url,
                    image=None,
                    price=price,
                    price_text=f"${price:,.2f}",
                    currency="USD",
                    brand=brand,
                    category=category,
                    rating=4.2,
                    rating_count=100 + index,
                    source=source,
                )
            )
    return inventory


def test_generator_outputs_required_files(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    repository = ProductRepository(base_dir=data_dir)
    products = sample_products()
    repository.ingest(products)
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com")
    monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "testtag-20")
    output_dir = tmp_path / "public"
    guides = generate_guides(repository, limit=15)
    generator = SiteGenerator(output_dir=output_dir)
    stored_products = repository.load_products()
    generator.build(products=stored_products, guides=guides)

    sitemap = (output_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert sitemap.count("<url>") >= 16
    assert (output_dir / "rss.xml").exists()
    assert (output_dir / "robots.txt").exists()

    amazon_product = next(product for product in stored_products if product.source == "amazon")
    product_html = (output_dir / "products" / amazon_product.slug / "index.html").read_text(encoding="utf-8")
    assert 'rel="sponsored nofollow noopener"' in product_html
    assert "tag=testtag-20" in product_html


def test_polish_guide_title_removes_for_a_and_right_now():
    cleaned = polish_guide_title("Best For A Techy Gifts Right Now")
    assert cleaned == "Best Tech Gifts"
