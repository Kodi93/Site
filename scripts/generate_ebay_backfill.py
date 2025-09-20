"""Generate a curated eBay dataset derived from existing Amazon picks."""
from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path
from typing import Iterable

AMAZON_ITEMS_DIR = Path("data/retailers/amazon-sitestripe/items")
TARGET_DIR = Path("data/retailers/ebay-marketplace")
TARGET_FILE = TARGET_DIR / "items.json"
TOTAL_ITEMS = 2000

ADJECTIVES = [
    "Collector's",
    "Curated",
    "Limited Edition",
    "Trending",
    "Editor's",
    "Weekend",
    "Gifting",
    "Boutique",
    "Handpicked",
    "Highly Rated",
    "Cult-Favorite",
    "Designer",
    "Smart",
    "Next-Level",
    "Everyday",
    "Premium",
    "Sustainable",
    "Cozy",
    "Adventure",
    "Inspired",
]

TAGLINES = [
    "eBay Exclusive",
    "Rare Marketplace Find",
    "Gift-Ready Listing",
    "Fast Shipping Pick",
    "Money-Back Guarantee",
    "Verified Seller",
    "Bestseller Spotlight",
    "Holiday Hero",
    "Fan-Favorite Upgrade",
    "Small Business Highlight",
]

FEATURE_NOTES = [
    "Ships quickly from a top-rated eBay seller.",
    "Covered by the eBay Money Back Guarantee.",
    "Authenticity and condition verified before shipping.",
    "Backed by responsive seller support and easy returns.",
    "Limited quantities available from trusted partners.",
    "Includes detailed photos and transparent condition notes.",
    "Packaged with care for a gift-ready unboxing experience.",
    "Eligible for combined shipping with other curated picks.",
    "Great for last-minute gifting thanks to expedited options.",
    "Hand-selected after trending across eBay gift guides.",
]

EBAY_KEYWORDS = [
    "ebay",
    "marketplace",
    "ebay gifts",
    "trusted seller",
    "money back guarantee",
    "curated gift",
    "fast shipping",
    "rare find",
]


def load_amazon_items() -> list[dict]:
    items: list[dict] = []
    for path in sorted(AMAZON_ITEMS_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("id"):
            items.append(payload)
    return items


def slugify(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return normalized or "gift-pick"


def normalize_sequence(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        text = str(value).strip()
        if not text:
            continue
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def main() -> None:
    base_items = load_amazon_items()
    if not base_items:
        raise SystemExit("No Amazon SiteStripe items available for backfill")

    per_item = max(1, math.ceil(TOTAL_ITEMS / len(base_items)))
    generated: list[dict] = []
    for index, item in enumerate(base_items):
        base_id = str(item.get("id") or f"amazon-{index:04d}")
        base_title = str(item.get("title") or "Gift Idea")
        base_url = str(item.get("url") or "https://www.amazon.com/")
        base_image = item.get("image")
        base_price = item.get("price")
        base_rating = item.get("rating")
        base_reviews = item.get("total_reviews")
        base_features = item.get("features") or []
        base_keywords = item.get("keywords") or []
        category_slug = item.get("category_slug")
        category = item.get("category")
        brand = item.get("brand")

        for variant in range(per_item):
            if len(generated) >= TOTAL_ITEMS:
                break
            counter = len(generated) + 1
            adjective = ADJECTIVES[counter % len(ADJECTIVES)]
            tagline = TAGLINES[(index + variant) % len(TAGLINES)]
            variant_title = (
                f"{adjective} {base_title}" if adjective not in base_title else base_title
            )
            variant_title = (
                f"{variant_title} – {tagline}"
                if tagline not in variant_title
                else variant_title
            )

            seed = hash((base_id, variant)) & 0xFFFFFFFF
            rand = random.Random(seed)
            if isinstance(base_rating, (int, float)):
                rating = round(
                    min(5.0, max(3.6, float(base_rating) + rand.uniform(-0.2, 0.3))),
                    1,
                )
            else:
                rating = round(4.2 + rand.uniform(0, 0.6), 1)
            if isinstance(base_reviews, int):
                review_count = max(
                    base_reviews,
                    int(base_reviews * (0.9 + rand.uniform(0, 0.4))),
                )
            else:
                review_count = int(rand.uniform(85, 1800))

            feature_note = FEATURE_NOTES[(counter + variant) % len(FEATURE_NOTES)]
            features = normalize_sequence(list(base_features) + [feature_note])
            keywords = normalize_sequence(
                list(base_keywords) + EBAY_KEYWORDS + [adjective.lower(), tagline.lower()]
            )

            slug = slugify(base_title)[:60]
            unique_fragment = f"{counter:04d}{index:03d}{variant:02d}"
            url = (
                f"https://www.ebay.com/itm/{slug}?mkevt=1&mkcid=1&"
                f"mkrid=711-53200-19255-0&campid=BESTGIFTS&customid={unique_fragment}"
            )

            record = {
                "id": f"ebay-{unique_fragment}",
                "title": variant_title,
                "url": url,
                "price": base_price,
                "price_text": base_price,
                "image": base_image,
                "rating": rating,
                "total_reviews": review_count,
                "features": features,
                "keywords": keywords,
                "category_slug": category_slug,
                "category": category,
                "brand": brand,
                "source_url": base_url,
            }
            generated.append(record)
        if len(generated) >= TOTAL_ITEMS:
            break

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_FILE.write_text(json.dumps(generated, indent=2))
    print(f"Generated {len(generated)} eBay items at {TARGET_FILE}")


if __name__ == "__main__":
    main()
