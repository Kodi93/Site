"""Generate long-form editorial content for roundups and weekly picks."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Sequence
from uuid import uuid4

from .articles import Article, ArticleItem
from .models import Product
from .utils import slugify


BRAND_GUIDE_HERO = "/assets/brand/hero-fallback.svg"
BRAND_GUIDE_CARD = "/assets/brand/card-fallback.svg"


DEFAULT_RELATED_FALLBACK = [
    "gifts-for-him",
    "tech-and-gadgets",
    "home-and-kitchen",
    "fitness-and-outdoors",
    "coffee-and-tea",
    "pets",
]


def _safe_price(product: Product) -> str:
    if product.price:
        return product.price
    latest = product.latest_price_point
    if latest:
        symbol = "$"
        return f"{symbol}{latest.amount:,.2f}"
    return "See current listing"


def _rating_summary(product: Product) -> str | None:
    if product.rating and product.total_reviews:
        return f"{product.rating:.1f}/5 ({product.total_reviews:,} reviews)"
    if product.rating:
        return f"Rated {product.rating:.1f}/5"
    return None


def _extract_keywords(product: Product, limit: int = 3) -> List[str]:
    keywords = [keyword for keyword in product.keywords if keyword]
    seen: List[str] = []
    for keyword in keywords:
        normalized = keyword.strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
        if len(seen) >= limit:
            break
    return seen


def _build_blurb(product: Product, *, context: str) -> str:
    keywords = _extract_keywords(product, limit=3)
    highlight = ", ".join(keywords[:2]) if keywords else "gift-worthy details"
    rating = _rating_summary(product)
    sentences: List[str] = []
    sentences.append(
        f"{product.title} folds those {context} vibes into a compact package with {highlight}."
    )
    if rating:
        sentences.append(
            f"Reviewers highlight the balance of value and quality, giving it {rating}."
        )
    else:
        sentences.append(
            "It blends practical touches with fun flair so it feels thoughtful without the splurge."
        )
    sentences.append(
        "Pair it with a handwritten card or bundle it with a favorite treat to create a ready-to-gift surprise."
    )
    return " ".join(sentences)


def _build_specs(product: Product) -> List[str]:
    specs: List[str] = []
    specs.append(f"Price: {_safe_price(product)}")
    rating = _rating_summary(product)
    if rating:
        specs.append(f"Rating: {rating}")
    specs.append(f"Retailer: {product.retailer_name}")
    keywords = _extract_keywords(product, limit=2)
    if keywords:
        specs.append("Highlights: " + ", ".join(keywords))
    return specs


def _hero_image(products: Sequence[Product]) -> str:
    for product in products:
        if product.image:
            return product.image
    return BRAND_GUIDE_HERO


def _article_tags(topic: str, products: Sequence[Product]) -> List[str]:
    tags: List[str] = []
    words = [word.strip(".,") for word in topic.split() if word]
    for word in words:
        lowered = word.lower()
        if lowered and lowered not in tags:
            tags.append(lowered)
    for product in products:
        for keyword in product.keywords:
            lowered = keyword.lower().strip()
            if lowered and lowered not in tags:
                tags.append(lowered)
    return tags[:12]


def _related_slugs(products: Sequence[Product], *, limit: int = 6) -> List[str]:
    pool: List[str] = []
    for product in products:
        slug = product.slug
        if slug not in pool:
            pool.append(slug)
        if len(pool) >= limit:
            break
    while len(pool) < limit and DEFAULT_RELATED_FALLBACK:
        fallback = DEFAULT_RELATED_FALLBACK[len(pool) % len(DEFAULT_RELATED_FALLBACK)]
        if fallback not in pool:
            pool.append(fallback)
    return pool[:limit]


def _intro_paragraphs(topic: str, *, price_cap: float | None, items: Sequence[Product]) -> List[str]:
    sample_titles = [product.title for product in items[:3]]
    joined_titles = ", ".join(sample_titles)
    price_text = (
        f"Every pick lands under ${price_cap:,.0f}" if price_cap is not None else "Each find earns its spot"
    )
    first = (
        f"We keep hearing from readers hunting for {topic.lower()} surprises, so we combed through the latest arrivals and editor favorites to assemble a gift list that actually feels fresh. We sifted trend reports, price history charts, and community click data to make sure every pick delivers a genuine wow moment."
    )
    second = (
        f"{price_text} and still brings standout details—think {joined_titles} and a handful of clever extras that scored top marks in our testing rounds. Each recommendation includes current pricing, ratings context, and the reason it punches above its weight so you can hit checkout with confidence."
    )
    third = (
        "Expect a mix of fast-ship staples, indie maker energy, and a few smart upgrades that feel right at home in everyday routines. You'll also find quick links to matching hubs and product deep dives so you can keep curating without losing momentum."
    )
    return [first, second, third]


def _intro_with_calendar(holiday: str, year: int, *, items: Sequence[Product]) -> List[str]:
    sample_titles = [product.title for product in items[:2]]
    joined = " and ".join(sample_titles)
    start = (
        f"{holiday} {year} sneaks up fast, so we pulled together a lineup that saves you from the last-minute scramble. We mapped ship windows, personalization cutoffs, and bestseller restocks so you can slide gifts into the calendar without stress."
    )
    middle = (
        f"From {joined} to unique handmade upgrades, every idea was vetted for quick gifting, easy shipping, and genuine delight. You'll see pricing callouts, ratings snippets, and spec bullets to make it easy to match recipients with the right level of surprise."
    )
    final = (
        "Bookmark this guide for stress-free planning and a punch list of links you can fire off whenever gifting inspiration hits. Dive into the related hubs for backup ideas and use the related picks block when you want to keep the festive mood rolling."
    )
    return [start, middle, final]


def _intro_weekly(week_number: int, year: int, *, items: Sequence[Product]) -> List[str]:
    sample_titles = [product.title for product in items[:3]]
    joined = ", ".join(sample_titles)
    first = (
        f"Week {week_number} of {year} brought a fresh wave of clever finds, so we cherry-picked the drops you keep bookmarking. These highlights are pulled straight from reader clicks, affiliate conversions, and our own late-night testing sessions."
    )
    second = (
        f"This batch spans {joined} plus a few curveballs you told us you wanted more of—think small-space upgrades, dopamine decor, and smart workshop helpers. Each blurb spells out why it earned a spot along with specs that make checkout decisions easy."
    )
    third = (
        "Consider it your shortcut to the internet’s coolest carts before the algorithm buries them. Scroll through the related picks and hub links when you're ready to keep the discovery streak going or need backups in case something sells out."
    )
    return [first, second, third]


def _intro_partner(
    audience: str,
    price_cap: float,
    *,
    items: Sequence[Product],
    holiday: str | None,
    holiday_date: date | None,
) -> List[str]:
    sample_titles = [product.title for product in items[:3]]
    highlight = ", ".join(sample_titles) or "fresh drops we can't stop recommending"
    count = len(items)
    price_text = f"${price_cap:,.0f}"
    if holiday:
        event_phrase = holiday
        if holiday_date:
            event_phrase = f"{holiday} on {holiday_date.strftime('%B %d')}"
        first = (
            f"{event_phrase} has a way of sneaking up, so we stitched together {count} under-{price_text} wins tailored for your {audience}. "
            f"Our editors blended conversion data, reader wish lists, and shipping cutoff intel to surface showstoppers like {highlight}."
        )
    else:
        first = (
            f"Readers keep asking for under-{price_text} ideas that make a {audience} feel wildly appreciated, so we pulled {count} standouts including {highlight}. "
            "Each one earned rave scores for sentiment, packaging, and long-haul delight."
        )
    second = (
        f"Every pick stays at or below {price_text} yet still feels premium thanks to luxe textures, personalization moments, or clever utility touches. "
        "Use the blurbs to understand the love-it details in plain language and skim the specs for price, rating, and retailer perks so checkout decisions happen fast."
    )
    third = (
        "Treat the guide like a plug-and-play planning doc—stack two items into a themed surprise, tap the related hubs for backup plans, and note any customization lead times so nothing slips through the cracks. "
        "We also flag delivery windows and return policies so last-minute pivots never derail the celebration."
    )
    return [first, second, third]


def _guide_who_for(audience: str) -> str:
    return (
        f"Ideal for celebrating your {audience} during anniversaries, milestone wins, or just-because Tuesdays. Pair any pick with a handwritten note, a playlist, or a mini experience to keep the momentum going."
    )


def _guide_consider(price_cap: float, holiday: str | None) -> str:
    budget_callout = (
        f"Everything lands at or below ${price_cap:,.0f}, though flash restocks can nudge prices slightly."
    )
    timing_callout = (
        f"Build in buffer time for engraving or shipping—{holiday} gifting rushes sell out fast." if holiday else "Double-check personalization windows and delivery cutoffs so surprise plans stay on track."
    )
    return (
        f"{budget_callout} {timing_callout} Keep receipts handy for easy swaps and peek at retailer loyalty perks if you want to stretch the budget further."
    )


def _guide_meta_description(
    audience: str,
    price_cap: float,
    *,
    holiday: str | None,
) -> str:
    price_text = f"${price_cap:,.0f}"
    celebration = holiday or "surprise night"
    description = (
        f"Curated gifts under {price_text} for your {audience} with blurbs, price callouts, and shipping tips so planning a {celebration.lower()} feels effortless."
    )
    if len(description) < 140:
        description += " Expect editor-tested picks, personalization intel, and related hubs for backup plans."
    return description[:160]


def _who_for(topic: str, *, audience: str) -> str:
    return (
        f"Great for {audience} who light up when a gift feels tailored to their routine. Use it for birthdays, office swaps, or to surprise a friend who already owns the basics—these ideas layer personality without asking for a splurge."
    )


def _consider_notes(*, price_cap: float | None) -> str:
    budget_callout = (
        f"Most items hover well below ${price_cap:,.0f}, though limited runs can nudge prices slightly." if price_cap is not None else "Inventory moves quickly on viral picks, so act fast if something sells out."
    )
    return (
        f"{budget_callout} Double-check delivery windows for rural addresses and skim retailer return policies—especially on handmade or personalized gear."
    )


def _build_items(products: Sequence[Product], *, context: str) -> List[ArticleItem]:
    items: List[ArticleItem] = []
    for product in products:
        anchor = slugify(product.title) or slugify(product.asin)
        blurb = _build_blurb(product, context=context)
        specs = _build_specs(product)
        items.append(
            ArticleItem(
                anchor=anchor,
                title=product.title,
                product_slug=product.slug,
                image=product.image or BRAND_GUIDE_CARD,
                blurb=blurb,
                specs=specs,
                tags=_extract_keywords(product, limit=4),
                outbound_url=product.link,
            )
        )
    return items


def _meta_description(topic: str, *, price_cap: float | None, items: Sequence[Product]) -> str:
    keywords = _extract_keywords(items[0]) if items else []
    highlight = ", ".join(keywords[:3]) if keywords else topic.lower()
    price_text = (
        f"budget-friendly gifts under ${price_cap:,.0f}" if price_cap is not None else "editor-loved finds"
    )
    description = (
        f"Curated {topic.lower()} ideas with {price_text}, real-world specs, and quick links so you can wrap standout surprises without the scroll marathon."
    )
    if len(description) < 140:
        description += " Expect blurbs, spec bullets, and related picks to keep the gifting momentum going."
    return description[:160]


def _meta_weekly(week_number: int, year: int, *, items: Sequence[Product]) -> str:
    sample_titles = [product.title for product in items[:2]]
    joined = " and ".join(sample_titles)
    description = (
        f"This Week's Cool Finds for week {week_number} {year} highlights {joined} plus more viral-ready picks with pricing, specs, and shop-now links."
    )
    if len(description) < 140:
        description += " Discover editor-tested upgrades before they vanish."
    return description[:160]


def _article_id() -> str:
    return uuid4().hex


def make_spouse_guide(
    *,
    audience_slug: str,
    audience_label: str,
    tone: str,
    price_cap: float,
    products: Sequence[Product],
    now: datetime | None = None,
    holiday: str | None = None,
    holiday_date: date | None = None,
    related_products: Sequence[Product] | None = None,
    hub_slugs: Sequence[str] | None = None,
) -> Article:
    now = now or datetime.now(timezone.utc)
    limited = list(products[:12]) if len(products) >= 12 else list(products)
    items = _build_items(limited, context=tone)
    intro = _intro_partner(
        audience_label,
        price_cap,
        items=limited,
        holiday=holiday,
        holiday_date=holiday_date,
    )
    who_for = _guide_who_for(audience_label)
    consider = _guide_consider(price_cap, holiday)
    related = related_products or []
    slug = slugify(
        f"{audience_slug}-gifts-under-{int(price_cap)}-{now.date().isoformat()}"
    )
    path = f"guides/{slug}/index.html"
    article = Article(
        id=_article_id(),
        slug=slug,
        path=path,
        kind="guide",
        title=f"Top {len(items)} gifts under ${int(price_cap)} for your {audience_label}",
        description=_guide_meta_description(audience_label, price_cap, holiday=holiday),
        hero_image=_hero_image(limited),
        intro=intro,
        who_for=who_for,
        consider=consider,
        items=items,
        hub_slugs=list(hub_slugs or []),
        related_product_slugs=_related_slugs(related),
        tags=_article_tags(f"{audience_label} gifts", limited),
    )
    article.ensure_quality(min_items=10)
    return article


def make_roundup(
    topic: str,
    price_cap: float,
    products: Sequence[Product],
    *,
    related_products: Sequence[Product] | None = None,
    hub_slugs: Sequence[str] | None = None,
    now: datetime | None = None,
) -> Article:
    now = now or datetime.now(timezone.utc)
    limited = list(products[:12]) if len(products) >= 12 else list(products)
    items = _build_items(limited, context=topic.lower())
    intro = _intro_paragraphs(topic, price_cap=price_cap, items=limited)
    who_for = _who_for(topic, audience="gifters")
    consider = _consider_notes(price_cap=price_cap)
    related = related_products or []
    slug = slugify(f"{topic}-gifts-under-{int(price_cap)}-{now.date().isoformat()}")
    path = f"guides/{slug}/index.html"
    article = Article(
        id=_article_id(),
        slug=slug,
        path=path,
        kind="roundup",
        title=f"Top {len(items)} {topic} Gifts Under ${int(price_cap)}",
        description=_meta_description(topic, price_cap=price_cap, items=limited),
        hero_image=_hero_image(limited),
        intro=intro,
        who_for=who_for,
        consider=consider,
        items=items,
        hub_slugs=list(hub_slugs or []),
        related_product_slugs=_related_slugs(related),
        tags=_article_tags(topic, limited),
    )
    article.ensure_quality(min_items=10)
    return article


def make_seasonal(
    holiday: str,
    year: int,
    categories: Sequence[str],
    products: Sequence[Product],
    *,
    related_products: Sequence[Product] | None = None,
    now: datetime | None = None,
) -> Article:
    now = now or datetime.now(timezone.utc)
    limited = list(products[:12]) if len(products) >= 12 else list(products)
    items = _build_items(limited, context=holiday.lower())
    intro = _intro_with_calendar(holiday, year, items=limited)
    who_for = _who_for(holiday, audience="hosts and gifters")
    consider = _consider_notes(price_cap=None)
    related = related_products or []
    slug = slugify(f"{holiday}-{year}-gift-ideas")
    path = f"guides/{slug}/index.html"
    article = Article(
        id=_article_id(),
        slug=slug,
        path=path,
        kind="seasonal",
        title=f"{holiday} Gift Ideas {year}",
        description=_meta_description(holiday, price_cap=None, items=limited),
        hero_image=_hero_image(limited),
        intro=intro,
        who_for=who_for,
        consider=consider,
        items=items,
        hub_slugs=list(categories[:3]),
        related_product_slugs=_related_slugs(related),
        tags=_article_tags(holiday, limited),
    )
    article.ensure_quality(min_items=10)
    return article


def make_weekly_picks(
    week_number: int,
    products: Sequence[Product],
    *,
    year: int,
    related_products: Sequence[Product] | None = None,
    hub_slugs: Sequence[str] | None = None,
    now: datetime | None = None,
) -> Article:
    now = now or datetime.now(timezone.utc)
    limited = list(products[:10]) if len(products) >= 10 else list(products)
    items = _build_items(limited, context="weekly cool finds")
    intro = _intro_weekly(week_number, year, items=limited)
    who_for = _who_for("this week's finds", audience="trend-hunting friends")
    consider = _consider_notes(price_cap=None)
    related = related_products or []
    slug = slugify(f"week-{week_number}-{year}")
    path = f"weekly/{year}/week-{week_number}/index.html"
    article = Article(
        id=_article_id(),
        slug=slug,
        path=path,
        kind="weekly",
        title=f"This Week's Cool Finds – Week {week_number}",
        description=_meta_weekly(week_number, year, items=limited),
        hero_image=_hero_image(limited),
        intro=intro,
        who_for=who_for,
        consider=consider,
        items=items,
        hub_slugs=list(hub_slugs or []),
        related_product_slugs=_related_slugs(related),
        tags=_article_tags("weekly finds", limited),
    )
    article.ensure_quality(min_items=8)
    return article
