from datetime import datetime, timedelta

from giftgrab.models import Product
from giftgrab.topics import generate_topics


def make_product(idx: int, *, category: str, brand: str | None = None, price: float = 29.99) -> Product:
    return Product(
        id=f"prod-{category}-{idx}",
        title=f"{category} Item {idx}",
        url=f"https://example.com/{category}/{idx}",
        image=None,
        price=price,
        price_text=f"${price:,.2f}",
        currency="USD",
        brand=brand,
        category=category,
        rating=4.5,
        rating_count=120,
        source="curated",
    )


def build_inventory() -> list[Product]:
    inventory: list[Product] = []
    categories = [
        ("Cozy Home", "NestCo"),
        ("Desk Gear", "Deskify"),
        ("Coffee Gear", "BrewLab"),
        ("Outdoor Fun", "TrailSet"),
    ]
    for category, brand in categories:
        for i in range(1, 16):
            price = 19.99 + i
            inventory.append(make_product(i, category=category, brand=brand, price=price))
    return inventory


def test_topics_history_blocks_recent_entries():
    products = build_inventory()
    recent_slug = "top-20-cozy-home-gifts"
    history = [
        {
            "slug": recent_slug,
            "title": "Top 20 Cozy Home Gifts",
            "date": (datetime.now() - timedelta(days=5)).isoformat(),
        }
    ]
    topics = generate_topics(products, history=history, limit=15)
    slugs = {topic.slug for topic in topics}
    assert recent_slug not in slugs
    assert len(topics) >= 15
