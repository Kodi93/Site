"""Static site generator for the GrabGifts catalog."""
from __future__ import annotations
import json
import logging
import math
import os
import re
from collections import Counter
from html import escape as html_escape
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Sequence
from statistics import median

from .affiliates import affiliate_rel, prepare_affiliate_url
from .blog import blurb
from .config import DEFAULT_PRESS_MENTIONS, PressMention
from .models import Guide, Product
from .text import title_case
from .utils import slugify

ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_TEMPLATE_PATH = ROOT_DIR / "templates" / "base.html"
HEADER_PATH = ROOT_DIR / "templates" / "partials" / "header.html"
FOOTER_PATH = ROOT_DIR / "templates" / "partials" / "footer.html"
THEME_PATH = ROOT_DIR / "public" / "assets" / "theme.css"
PROTECTED_FILES = {
    BASE_TEMPLATE_PATH.resolve(),
    HEADER_PATH.resolve(),
    FOOTER_PATH.resolve(),
    THEME_PATH.resolve(),
}

_MIN_TIMESTAMP = datetime.min.replace(tzinfo=timezone.utc)


_BANNED_PHRASES = ("fresh drops", "active vibes")

_STOPWORDS = {"for", "a", "the", "and", "of"}
_RIGHT_NOW_SUFFIX = re.compile(r"\s+right now\.?$", re.IGNORECASE)
_BEST_FOR_PATTERN = re.compile(
    r"(?i)^best\s+for\s+a\s+(?P<subject>.+?)\s+gifts(?P<tail>.*)$"
)
_TITLE_REPLACEMENTS = {"Techy": "Tech"}

_PRICE_BUCKETS: tuple[tuple[str, str, float | None, float | None], ...] = (
    ("under-25", "Under $25", None, 25.0),
    ("25-50", "$25 – $50", 25.0, 50.0),
    ("50-100", "$50 – $100", 50.0, 100.0),
    ("100-200", "$100 – $200", 100.0, 200.0),
    ("200-plus", "$200 & up", 200.0, None),
)

SOURCE_LABELS = {
    "amazon": "Amazon",
    "ebay": "eBay",
    "curated": "Curated",
}


def _strip_banned_phrases(text: str) -> str:
    result = text or ""
    for phrase in _BANNED_PHRASES:
        result = re.sub(re.escape(phrase), "", result, flags=re.IGNORECASE)
    return result.strip()


def _apply_stopwords(text: str) -> str:
    first_word_found = False

    def _lower(match: re.Match[str]) -> str:
        nonlocal first_word_found
        word = match.group(0)
        if not first_word_found:
            first_word_found = True
            return word
        if word.lower() in _STOPWORDS:
            return word.lower()
        return word

    return re.sub(r"[A-Za-z]+", _lower, text)


def polish_guide_title(title: str) -> str:
    text = (title or "").strip()
    if not text:
        return ""
    text = _RIGHT_NOW_SUFFIX.sub("", text).strip()
    match = _BEST_FOR_PATTERN.match(text)
    if match:
        subject = match.group("subject").strip()
        tail = match.group("tail") or ""
        text = f"Best {subject} Gifts{tail}"
    text = re.sub(r"\s+", " ", text).strip()
    text = title_case(text)
    text = _apply_stopwords(text)
    for source, target in _TITLE_REPLACEMENTS.items():
        text = re.sub(rf"\b{source}\b", target, text)
    return text.strip()


def _parse_iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_updated_label(value: str | None) -> str | None:
    if not value:
        return None
    parsed = _parse_iso_datetime(value)
    if parsed <= _MIN_TIMESTAMP:
        return None
    return parsed.strftime("%b %d, %Y")


def _read_markup(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff").strip()


def _apply_includes(template: str) -> str:
    includes = {
        "partials/header.html": _read_markup(HEADER_PATH),
        "partials/footer.html": _read_markup(FOOTER_PATH),
    }

    for include_path, markup in includes.items():
        pattern = re.compile(
            rf"(?P<indent>[\t ]*)\{{%\s*include\s+[\"']{re.escape(include_path)}[\"']\s*%\}}"
        )

        def _replace(match: re.Match[str]) -> str:
            indent = match.group("indent")
            lines = markup.splitlines()
            if not lines:
                return ""
            return "\n".join(f"{indent}{line}" if line else "" for line in lines)

        template = pattern.sub(_replace, template)

    return template


BASE_TEMPLATE = _apply_includes(
    BASE_TEMPLATE_PATH.read_text(encoding="utf-8").lstrip("\ufeff")
)


def _join_with_and(items: Sequence[str]) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _price_in_bucket(price: float | None, minimum: float | None, maximum: float | None) -> bool:
    if price is None:
        return False
    if minimum is not None and price < minimum:
        return False
    if maximum is not None and price >= maximum:
        return False
    return True


def _format_price_value(value: float | None) -> str:
    if value is None:
        return ""
    text = f"{value:.2f}"
    return text.rstrip("0").rstrip(".")

_HEAD_SAFE_PATTERN = re.compile(r"\{\{\s*head\|safe\s*\}\}")
_HEAD_PATTERN = re.compile(r"\{\{\s*head\s*\}\}")
_CONTENT_SAFE_PATTERN = re.compile(r"\{\{\s*content\|safe\s*\}\}")
_CONTENT_PATTERN = re.compile(r"\{\{\s*content\s*\}\}")


def _render_with_base(*, content: str, head: str = "") -> str:
    html = BASE_TEMPLATE
    escaped_head = html_escape(head)
    escaped_content = html_escape(content)
    html = _HEAD_SAFE_PATTERN.sub(lambda _match: head, html)
    html = _HEAD_PATTERN.sub(lambda _match: escaped_head, html)
    html = _CONTENT_SAFE_PATTERN.sub(lambda _match: content, html)
    html = _CONTENT_PATTERN.sub(lambda _match: escaped_content, html)
    return html

LOGGER = logging.getLogger(__name__)

GUIDE_ITEM_TARGET = 20


@dataclass
class SiteSettings:
    name: str
    base_url: str
    description: str
    logo_url: str | None
    twitter: str | None
    facebook: str | None
    contact_email: str | None
    keywords: tuple[str, ...]
    analytics_id: str | None
    analytics_snippet: str | None
    adsense_client_id: str | None
    adsense_slot: str | None
    adsense_rail_slot: str | None
    favicon_url: str | None
    press_mentions: tuple[PressMention, ...]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _parse_press_mentions(raw: str | None) -> tuple[PressMention, ...]:
    """Parse press mentions from an environment payload."""

    if not raw:
        return DEFAULT_PRESS_MENTIONS

    text = raw.strip()
    if not text:
        return DEFAULT_PRESS_MENTIONS
    if text.lower() in {"none", "off"}:
        return ()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logging.getLogger(__name__).warning("Failed to parse SITE_PRESS_MENTIONS JSON; using defaults")
        return DEFAULT_PRESS_MENTIONS

    entries: list[PressMention] = []
    if isinstance(payload, dict):
        payload = [payload]
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            outlet = str(item.get("outlet", "")).strip()
            quote = str(item.get("quote", "")).strip()
            if not outlet or not quote:
                continue
            url_raw = item.get("url")
            logo_raw = item.get("logo")
            url = str(url_raw).strip() if isinstance(url_raw, str) else None
            logo = str(logo_raw).strip() if isinstance(logo_raw, str) else None
            entries.append(
                PressMention(
                    outlet=outlet,
                    quote=quote,
                    url=url or None,
                    logo=logo or None,
                )
            )
    if entries:
        return tuple(entries)
    return ()


def load_settings() -> SiteSettings:
    keywords_env = _env("SITE_KEYWORDS")
    keywords: tuple[str, ...] = ()
    if keywords_env:
        keywords = tuple(
            item.strip()
            for item in keywords_env.split(",")
            if item.strip()
        )
    return SiteSettings(
        name=_env("SITE_NAME", "GrabGifts") or "GrabGifts",
        base_url=_env("SITE_BASE_URL", "https://example.com"),
        description=_env(
            "SITE_DESCRIPTION",
            (
                "Grab Gifts surfaces viral-ready Amazon finds with conversion copy and plug-and-play affiliate automation. "
                "Launch scroll-stopping gift funnels that convert on autopilot."
            ),
        )
        or (
            "Grab Gifts surfaces viral-ready Amazon finds with conversion copy and plug-and-play affiliate automation. "
            "Launch scroll-stopping gift funnels that convert on autopilot."
        ),
        logo_url=_env("SITE_LOGO_URL"),
        twitter=_env("SITE_TWITTER"),
        facebook=_env("SITE_FACEBOOK"),
        contact_email=_env("SITE_CONTACT_EMAIL"),
        keywords=keywords,
        analytics_id=_env("SITE_ANALYTICS_ID"),
        analytics_snippet=_env("SITE_ANALYTICS_SNIPPET"),
        adsense_client_id=_env("ADSENSE_CLIENT_ID"),
        adsense_slot=_env("ADSENSE_SLOT"),
        adsense_rail_slot=_env("ADSENSE_RAIL_SLOT"),
        favicon_url=_env("SITE_FAVICON_URL"),
        press_mentions=_parse_press_mentions(_env("SITE_PRESS_MENTIONS")),
    )


class SiteGenerator:
    def __init__(self, output_dir: Path | str = Path("public"), settings: SiteSettings | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.settings = settings or load_settings()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sitemap_entries: List[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Public API

    def build(self, *, products: Sequence[Product], guides: Sequence[Guide]) -> None:
        LOGGER.info("Rendering site to %s", self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sitemap_entries = []
        self._write_homepage(guides, products)
        self._write_guides(guides)
        self._write_categories(products)
        self._write_products(products)
        self._write_products_index(products)
        self._write_about(guides, products)
        self._write_curation_page(guides, products)
        self._write_contact()
        self._write_faq()
        self._write_sitemap()
        self._write_robots()
        self._write_rss(guides)

    # ------------------------------------------------------------------
    # Rendering helpers

    def _press_section_markup(self) -> str | None:
        mentions = getattr(self.settings, "press_mentions", ())
        cards: list[str] = []
        for mention in mentions:
            if not mention or not getattr(mention, "quote", None):
                continue
            outlet = getattr(mention, "outlet", "").strip()
            if not outlet:
                continue
            quote = html_escape(str(mention.quote).strip())
            outlet_label = html_escape(outlet)
            url = getattr(mention, "url", None)
            outlet_markup = outlet_label
            if isinstance(url, str) and url.strip():
                outlet_markup = (
                    f'<a href="{html_escape(url.strip())}" rel="noopener" target="_blank">'
                    + outlet_label
                    + "</a>"
                )
            logo = getattr(mention, "logo", None)
            logo_markup = ""
            if isinstance(logo, str) and logo.strip():
                logo_markup = (
                    '<div class="press-logo">'
                    f"<img src=\"{html_escape(logo.strip())}\" alt=\"{outlet_label} logo\" loading=\"lazy\">"
                    "</div>"
                )
            parts = ["<article class=\"press-card\">"]
            if logo_markup:
                parts.append(logo_markup)
            parts.append(f"<p class=\"press-quote\">&ldquo;{quote}&rdquo;</p>")
            parts.append(f"<p class=\"press-outlet\">{outlet_markup}</p>")
            parts.append("</article>")
            cards.append("".join(parts))
        if not cards:
            return None
        return "\n".join(
            [
                '<section class="press-section" aria-labelledby="press-heading">',
                '<div class="page-header">',
                '<h2 id="press-heading">Loved by performance teams</h2>',
                '<p>Clips from operators who lean on grabgifts to launch faster.</p>',
                '</div>',
                '<div class="press-grid">',
                "\n".join(cards),
                '</div>',
                '</section>',
            ]
        )

    def _abs_url(self, path: str) -> str:
        base = (self.settings.base_url or "https://example.com").rstrip("/")
        if path.startswith("/"):
            return f"{base}{path}"
        return f"{base}/{path}"

    def _adsense_unit(self, slot: str | None) -> str:
        return ""

    def _safe_write(self, target: Path, content: str) -> None:
        resolved = target.resolve()
        if resolved in PROTECTED_FILES:
            raise RuntimeError("Protected layout file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _write_file(self, path: str, content: str) -> None:
        file_path = self.output_dir / path.lstrip("/")
        if file_path.name != "index.html":
            file_path = file_path / "index.html"
        self._safe_write(file_path, content)


    def _render_document(
        self,
        *,
        page_title: str,
        description: str,
        canonical_path: str,
        body: str,
        extra_json_ld: Iterable[dict] | None = None,
    ) -> str:
        head_parts: list[str] = []
        title_text = (page_title or "").strip()
        if title_text:
            head_parts.append(f"<title>{html_escape(title_text)}</title>")

        description_text = (description or "").strip()
        if description_text:
            head_parts.append(
                "<meta name=\"description\" content=\""
                + html_escape(description_text)
                + "\">"
            )

        canonical = (canonical_path or "").strip()
        if canonical:
            head_parts.append(
                "<link rel=\"canonical\" href=\""
                + html_escape(self._abs_url(canonical))
                + "\">"
            )

        for payload in extra_json_ld or ():
            if not payload:
                continue
            try:
                json_ld = json.dumps(payload, ensure_ascii=False)
            except (TypeError, ValueError):
                LOGGER.exception("Failed to encode JSON-LD payload")
                continue
            json_ld = json_ld.replace("</", "<\\/")
            head_parts.append(
                "<script type=\"application/ld+json\">"
                + json_ld
                + "</script>"
            )

        head_html = ""
        if head_parts:
            head_lines = [head_parts[0]]
            head_lines.extend(f"  {part}" for part in head_parts[1:])
            head_html = "\n".join(head_lines)

        body_html = body if body.endswith("\n") else f"{body}\n"
        return _render_with_base(content=body_html, head=head_html)

    def _guide_json_ld(self, guide: Guide, canonical_path: str) -> dict:
        title = polish_guide_title(guide.title)
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": title,
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": product.title,
                    "url": self._abs_url(f"/products/{product.slug}/"),
                }
                for index, product in enumerate(guide.products)
            ],
            "url": self._abs_url(canonical_path),
        }

    def _product_json_ld(self, product: Product, description: str) -> dict:
        payload = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "url": product.url,
            "description": description,
        }
        if product.image:
            payload["image"] = product.image
        if product.brand:
            payload["brand"] = {"@type": "Brand", "name": product.brand}
        if product.rating is not None and product.rating_count:
            payload["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": round(product.rating, 2),
                "reviewCount": product.rating_count,
            }
        if product.price is not None:
            payload["offers"] = {
                "@type": "Offer",
                "price": f"{product.price:.2f}",
                "priceCurrency": product.currency or "USD",
                "url": product.url,
            }
        return payload

    def _product_card(self, product: Product) -> tuple[str, dict] | None:
        if not product.image:
            return None
        description_source = product.description or blurb(product)
        description = _strip_banned_phrases(description_source)
        link = prepare_affiliate_url(product.url, product.source)
        price_display = product.price_text
        if not price_display and product.price is not None:
            currency = product.currency or "USD"
            if currency.upper() == "USD":
                price_display = f"${product.price:,.2f}"
            else:
                price_display = f"{product.price:,.2f} {currency.upper()}"
        meta_parts = []
        if product.brand:
            meta_parts.append(product.brand)
        if product.category:
            meta_parts.append(product.category)
        body = ["<article class=\"card\">"]
        body.append(
            f"<img src=\"{product.image}\" alt=\"{product.title}\" loading=\"lazy\">"
        )
        body.append(f"<h2>{product.title}</h2>")
        if price_display:
            body.append(f"<p class=\"price\">{price_display}</p>")
        if meta_parts:
            body.append(f"<p>{' • '.join(meta_parts)}</p>")
        body.append(f"<p>{description}</p>")
        body.append(
            f"<a class=\"button\" rel=\"{affiliate_rel()}\" target=\"_blank\" href=\"{link}\">See details</a>"
        )
        body.append("</article>")
        return "".join(body), self._product_json_ld(product, description)

    def _product_preview_card(self, product: Product) -> str | None:
        if not product.title or not product.image:
            return None
        price_display = product.price_text
        if not price_display and product.price is not None:
            currency = product.currency or "USD"
            if currency.upper() == "USD":
                price_display = f"${product.price:,.2f}"
            else:
                price_display = f"{product.price:,.2f} {currency.upper()}"
        raw_title = product.title or ""
        raw_brand = product.brand or ""
        raw_category = product.category or ""
        description = product.description or ""
        meta_parts: list[str] = []
        if raw_category:
            meta_parts.append(html_escape(raw_category))
        if raw_brand:
            meta_parts.append(html_escape(raw_brand))
        meta_html = (
            "<p class=\"feed-card-meta\">" + " • ".join(meta_parts) + "</p>"
            if meta_parts
            else ""
        )
        price_html = (
            f"<p class=\"feed-card-price\">{html_escape(price_display)}</p>"
            if price_display
            else ""
        )
        summary_source = [raw_title, raw_brand, raw_category]
        if description:
            summary_source.append(description)
        keywords = " ".join(
            " ".join(str(value).split()) for value in summary_source if value
        ).lower()
        keywords_attr = html_escape(keywords[:600])
        category_slug = slugify(raw_category) if raw_category else ""
        category_attr = html_escape(category_slug)
        brand_attr = html_escape(raw_brand.lower())
        title_attr = html_escape(raw_title.lower())
        price_attr = (
            f"{product.price:.2f}"
            if product.price is not None
            else ""
        )
        attributes = [
            'class="feed-card"',
            'data-home-product-card="true"',
            'data-product-card="true"',
        ]
        if product.id:
            attributes.append(f'data-product-id="{html_escape(product.id)}"')
        attributes.append(f'data-product-title="{title_attr}"')
        attributes.append(f'data-product-brand="{brand_attr}"')
        attributes.append(
            f'data-product-category="{category_attr}"'
            if category_attr
            else 'data-product-category=""'
        )
        attributes.append(
            f'data-product-price="{price_attr}"'
            if price_attr
            else 'data-product-price=""'
        )
        attributes.append(f'data-product-keywords="{keywords_attr}"')
        attr_html = " ".join(attributes)
        slug = html_escape(product.slug)
        image = html_escape(product.image)
        title = html_escape(raw_title)
        return (
            f"<article {attr_html}>"
            f"<a class=\"feed-card-link\" href=\"/products/{slug}/\">"
            f"<div class=\"feed-card-media\"><img src=\"{image}\" alt=\"{title}\" loading=\"lazy\"></div>"
            "<div class=\"feed-card-body\">"
            f"{meta_html}"
            f"<h3 class=\"feed-card-title\">{title}</h3>"
            f"{price_html}"
            "</div>"
            "</a>"
            "</article>"
        )

    def _guide_summary(self, guide: Guide) -> str | None:
        products = [product for product in guide.products if product]
        if not products:
            return None
        items: list[str] = []
        items.append(
            "<li class=\"guide-meta__item\">"
            "<span class=\"guide-meta__label\">Total picks</span>"
            f"<span class=\"guide-meta__value\">{len(products)}</span>"
            "</li>"
        )
        price_values = sorted(
            float(product.price)
            for product in products
            if product.price is not None
        )
        if price_values:
            low = price_values[0]
            high = price_values[-1]
            mid = median(price_values)
            if math.isclose(low, high, rel_tol=0.02, abs_tol=0.5):
                price_label = _format_price_value(mid)
            else:
                price_label = (
                    f"{_format_price_value(low)} – {_format_price_value(high)}"
                )
                if not (
                    math.isclose(mid, low, rel_tol=0.02, abs_tol=0.5)
                    or math.isclose(mid, high, rel_tol=0.02, abs_tol=0.5)
                ):
                    price_label += f" · median {_format_price_value(mid)}"
            items.append(
                "<li class=\"guide-meta__item\">"
                "<span class=\"guide-meta__label\">Price range</span>"
                f"<span class=\"guide-meta__value\">{html_escape(price_label)}</span>"
                "</li>"
            )
        brands = sorted(
            {html_escape(product.brand.strip()) for product in products if product.brand and product.brand.strip()}
        )
        if brands:
            if len(brands) <= 3:
                brand_label = _join_with_and(brands)
            else:
                brand_label = f"{len(brands)} brands"
            items.append(
                "<li class=\"guide-meta__item\">"
                "<span class=\"guide-meta__label\">Brands</span>"
                f"<span class=\"guide-meta__value\">{brand_label}</span>"
                "</li>"
            )
        categories = sorted(
            {html_escape(product.category.strip()) for product in products if product.category and product.category.strip()}
        )
        if categories:
            if len(categories) <= 3:
                category_label = _join_with_and(categories)
            else:
                category_label = f"{len(categories)} categories"
            items.append(
                "<li class=\"guide-meta__item\">"
                "<span class=\"guide-meta__label\">Categories</span>"
                f"<span class=\"guide-meta__value\">{category_label}</span>"
                "</li>"
            )
        sources = sorted(
            {
                html_escape(SOURCE_LABELS.get(product.source, product.source.title()))
                for product in products
                if product.source
            }
        )
        if sources:
            source_label = _join_with_and(sources)
            items.append(
                "<li class=\"guide-meta__item\">"
                "<span class=\"guide-meta__label\">Sources</span>"
                f"<span class=\"guide-meta__value\">{source_label}</span>"
                "</li>"
            )
        if not items:
            return None
        return "\n".join(
            [
                '<section class="guide-meta" aria-label="Guide highlights">',
                '<ul class="guide-meta__grid">',
                "\n".join(items),
                '</ul>',
                '</section>',
            ]
        )

    def _guide_body(self, guide: Guide) -> tuple[str, List[dict]]:
        cards_html = []
        json_ld: List[dict] = []
        guide_title = polish_guide_title(guide.title)
        for product in guide.products:
            card = self._product_card(product)
            if not card:
                continue
            card_html, payload = card
            cards_html.append(card_html)
            json_ld.append(payload)
        cards = "\n".join(cards_html)
        guide_description = _strip_banned_phrases(guide.description)
        parts = [
            "<section class=\"page-header\">",
            f"<h1>{guide_title}</h1>",
            f"<p>{guide_description}</p>",
            "</section>",
        ]
        summary = self._guide_summary(guide)
        if summary:
            parts.append(summary)
        if cards:
            parts.append(f"<section class=\"grid\">{cards}</section>")
        else:
            parts.append("<p>No items are available for this guide right now.</p>")
        return "\n".join(parts), json_ld

    def _write_homepage(
        self, guides: Sequence[Guide], products: Sequence[Product]
    ) -> None:
        timestamps: list[datetime] = []
        category_counts: Counter[str] = Counter()
        brand_set: set[str] = set()
        for guide in guides:
            if guide.products:
                timestamps.extend(
                    _parse_iso_datetime(product.updated_at)
                    for product in guide.products
                )
            else:
                timestamps.append(_parse_iso_datetime(guide.created_at))
        for product in products:
            if product.category:
                category_counts[product.category] += 1
            if product.brand:
                brand_set.add(product.brand)
            timestamps.append(
                max(
                    _parse_iso_datetime(product.created_at),
                    _parse_iso_datetime(product.updated_at),
                )
            )
        if timestamps:
            last_updated = max(timestamps).isoformat()
        else:
            last_updated = datetime.now(timezone.utc).isoformat()
        updated_label = _format_updated_label(last_updated)
        sorted_guides = sorted(
            guides,
            key=lambda item: (
                _parse_iso_datetime(item.created_at),
                polish_guide_title(item.title).lower(),
            ),
            reverse=True,
        )
        live_guides = [guide for guide in sorted_guides if guide.products]
        guides_live_count = len(live_guides)
        total_products = len(products)
        unique_brands = len(brand_set)
        top_categories = [name for name, _count in category_counts.most_common(3)]

        guide_cards: list[str] = []
        for index, guide in enumerate(sorted_guides):
            display_title = polish_guide_title(guide.title)
            first = guide.products[0] if guide.products else None
            teaser_source = first if first else guide
            teaser = blurb(teaser_source) if first else guide.description
            teaser = _strip_banned_phrases(teaser)
            attrs = ['class="card"', 'data-home-guide-card="true"']
            if index >= 5:
                attrs.append('hidden')
                attrs.append('data-home-guide-hidden="true"')
            guide_cards.append(
                '<article '
                + ' '.join(attrs)
                + '>'
                + f'<h2><a href="/guides/{guide.slug}/">{display_title}</a></h2>'
                + f'<p>{teaser}</p>'
                + '</article>'
            )
        cards_html = "\n".join(guide_cards)
        home_description = _strip_banned_phrases(self.settings.description)
        hero_markup = [
            "<section class=\"hero\">",
            "<h1>grabgifts</h1>",
        ]
        if home_description:
            hero_markup.append(f"<p>{home_description}</p>")
        hero_stats: list[str] = []
        if guides_live_count:
            hero_stats.append(
                "<li>"
                f"<span class=\"hero-meta__value\">{guides_live_count:,}</span>"
                "<span class=\"hero-meta__label\">Guides live</span>"
                "</li>"
            )
        if total_products:
            hero_stats.append(
                "<li>"
                f"<span class=\"hero-meta__value\">{total_products:,}</span>"
                "<span class=\"hero-meta__label\">Products tracked</span>"
                "</li>"
            )
        if unique_brands:
            hero_stats.append(
                "<li>"
                f"<span class=\"hero-meta__value\">{unique_brands:,}</span>"
                "<span class=\"hero-meta__label\">Brands covered</span>"
                "</li>"
            )
        if updated_label:
            hero_stats.append(
                "<li>"
                f"<span class=\"hero-meta__value\">{html_escape(updated_label)}</span>"
                "<span class=\"hero-meta__label\">Last refresh</span>"
                "</li>"
            )
        if hero_stats:
            hero_markup.append('<ul class=\"hero-meta\" aria-label=\"Grabgifts highlights\">')
            hero_markup.extend(hero_stats)
            hero_markup.append("</ul>")
        hero_markup.extend(
            [
                "<div class=\"hero-actions\">",
                "<a class=\"button\" href=\"/guides/\">Explore today's drops</a>",
                "<a class=\"button button-secondary\" href=\"/surprise/\">Spin up a surprise</a>",
                "<a class=\"button button-ghost\" href=\"/changelog/\">See the live changelog</a>",
                "</div>",
            ]
        )
        hero_markup.extend(
            [
                '<div class="hero-support">',
                '<p class="hero-support__lede">What each refresh delivers</p>',
                '<ul class="hero-support__list">',
                '<li>Daily automations capture trending inventory before your morning standup.</li>',
                '<li>Editors rewrite blurbs, remove duplicates, and QA every affiliate-safe link.</li>',
                '<li>Each deploy ships with JSON-LD, RSS, and metadata ready to publish.</li>',
                '</ul>',
                '</div>',
            ]
        )
        hero_markup.append("</section>")
        sections: List[str] = ["\n".join(hero_markup)]
        press_section = self._press_section_markup()
        if press_section:
            sections.append(press_section)
        freshness_detail = (
            "Refreshed on "
            + html_escape(updated_label)
            + " with manual QA before publish."
            if updated_label
            else "Refreshed daily with manual QA before publish."
        )
        quality_cards: list[str] = [
            (
                "<article class=\"quality-card\">"
                "<h3>Fresh every morning</h3>"
                f"<p>{freshness_detail}</p>"
                "</article>"
            ),
            (
                "<article class=\"quality-card\">"
                f"<h3>{GUIDE_ITEM_TARGET} picks per guide</h3>"
                "<p>Each roundup ships with ranked blurbs, pricing context, and affiliate-safe links ready to promote.</p>"
                "</article>"
            ),
        ]
        if total_products:
            coverage_parts: list[str] = []
            category_count = len(category_counts)
            if category_count:
                coverage_parts.append(f"{category_count} categories")
            if unique_brands:
                coverage_parts.append(f"{unique_brands:,} brands")
            if coverage_parts:
                coverage_text = _join_with_and(coverage_parts)
                inventory_detail = f"{total_products:,} gift ideas spanning {coverage_text}."
            else:
                inventory_detail = f"{total_products:,} gift ideas are live in today's catalog."
            quality_cards.append(
                (
                    "<article class=\"quality-card\">"
                    "<h3>Catalog depth</h3>"
                    f"<p>{inventory_detail}</p>"
                    "</article>"
                )
            )
        if top_categories:
            escaped_categories = [html_escape(name) for name in top_categories]
            categories_text = _join_with_and(escaped_categories)
            verb = "are" if len(escaped_categories) > 1 else "is"
            quality_cards.append(
                (
                    "<article class=\"quality-card\">"
                    "<h3>Trending themes</h3>"
                    f"<p>{categories_text} {verb} resonating with shoppers right now.</p>"
                    "</article>"
                )
            )
        if quality_cards:
            quality_section = [
                '<section class="quality-section" aria-labelledby="quality-heading">',
                '<div class="page-header">',
                '<h2 id="quality-heading">Why shoppers trust grabgifts</h2>',
                '<p>Transparency, testing, and constant refreshes keep our picks sharp.</p>',
                '</div>',
                '<div class="quality-grid">',
                "".join(quality_cards),
                '</div>',
                '</section>',
            ]
            sections.append("\n".join(quality_section))
        if cards_html:
            guide_section_parts = [
                '<section id="guide-list" data-home-guides>',
                '<div class="page-header">',
                "<h2>Today's drops</h2>",
                '<p>Browse the guides refreshed for the latest grabgifts catalog.</p>',
                '</div>',
                '<div class="grid guide-grid">',
                cards_html,
                '</div>',
            ]
            if len(guide_cards) > 5:
                guide_section_parts.append(
                    '<button class="button" type="button" data-home-guide-toggle="true" aria-expanded="false">See more guides</button>'
                )
            guide_section_parts.append('</section>')
            sections.append("\n".join(guide_section_parts))
        else:
            sections.append(
                "\n".join(
                    [
                        "<section id=\"guide-list\">",
                        "<div class=\"page-header\">",
                        "<h2>Today's drops</h2>",
                        "<p>Guides are being prepared. Check back soon.</p>",
                        "</div>",
                        "</section>",
                    ]
                )
            )

        highlighted_ids: set[str] = set()
        ebay_products = [
            product
            for product in products
            if (product.source or "").lower() == "ebay"
        ]
        if ebay_products:
            cutoff = datetime.now(timezone.utc) - timedelta(days=1)

            def _recency(product: Product) -> tuple[datetime, str]:
                created = _parse_iso_datetime(product.created_at)
                updated = _parse_iso_datetime(product.updated_at)
                latest = max(created, updated)
                title_key = (product.title or "").lower()
                return latest, title_key

            sorted_ebay = sorted(
                ebay_products,
                key=lambda item: _recency(item),
                reverse=True,
            )
            recent_ebay = [
                product for product in sorted_ebay if _recency(product)[0] >= cutoff
            ]
            display_pool = recent_ebay or sorted_ebay
            recent_cards: list[str] = []
            for product in display_pool[:8]:
                card = self._product_preview_card(product)
                if card:
                    if product.id:
                        highlighted_ids.add(product.id)
                    recent_cards.append(card)
            if recent_cards:
                sections.append(
                    "\n".join(
                        [
                            '<section class="feed-section" id="recent-ebay-products" data-home-ebay>',
                            '<div class="page-header">',
                            '<h2>Most recent additions</h2>',
                            '<p>Fresh arrivals pulled from the latest eBay sweep.</p>',
                            '</div>',
                            '<div class="feed-list">',
                            "\n".join(recent_cards),
                            '</div>',
                            '</section>',
                        ]
                    )
                )
            else:
                sections.append(
                    "\n".join(
                        [
                            '<section class="feed-section" id="recent-ebay-products" data-home-ebay>',
                            '<div class="page-header">',
                            '<h2>Most recent additions</h2>',
                            '<p>Fresh eBay picks will land here after the next refresh.</p>',
                            '</div>',
                            '</section>',
                        ]
                    )
                )
        else:
            sections.append(
                "\n".join(
                    [
                        '<section class="feed-section" id="recent-ebay-products" data-home-ebay>',
                        '<div class="page-header">',
                        '<h2>Most recent additions</h2>',
                        '<p>Fresh eBay picks will land here after the next refresh.</p>',
                        '</div>',
                        '</section>',
                    ]
                )
            )

        product_cards_initial: list[str] = []
        product_cards_remaining: list[str] = []
        for product in sorted(
            products,
            key=lambda item: (
                max(
                    _parse_iso_datetime(item.created_at),
                    _parse_iso_datetime(item.updated_at),
                ),
                item.title.lower() if item.title else "",
            ),
            reverse=True,
        ):
            if product.id in highlighted_ids:
                continue
            card = self._product_preview_card(product)
            if not card:
                continue
            if len(product_cards_initial) < 10:
                product_cards_initial.append(card)
            else:
                product_cards_remaining.append(card)

        if product_cards_initial:
            product_section_parts = [
                '<section class="feed-section" id="latest-products" data-home-products data-product-batch="6">',
                '<div class="page-header">',
                '<h2>Fresh product drops</h2>',
                '<p>Catch the newest arrivals across the catalog.</p>',
                '</div>',
                '<div class="feed-list" data-product-grid>',
                "\n".join(product_cards_initial),
                '</div>',
            ]
            if product_cards_remaining:
                product_section_parts.extend(
                    [
                        '<div class="feed-sentinel" data-product-sentinel></div>',
                        '<script type="application/json" data-product-source>'
                        + html_escape(json.dumps(product_cards_remaining))
                        + '</script>',
                    ]
                )
            product_section_parts.append('</section>')
            sections.append("\n".join(product_section_parts))
        else:
            sections.append(
                "\n".join(
                    [
                        '<section class="feed-section" id="latest-products">',
                        '<div class="page-header">',
                        '<h2>Fresh product drops</h2>',
                        '<p>New arrivals will appear here soon.</p>',
                        '</div>',
                        '</section>',
                    ]
                )
            )

        body = "\n".join(sections)
        html = self._render_document(
            page_title=self.settings.name,
            description=home_description,
            canonical_path="/",
            body=body,
        )
        self._write_file("/index.html", html)
        self._sitemap_entries.append(("/", last_updated))

    def _write_guides(self, guides: Sequence[Guide]) -> None:
        for guide in guides:
            display_title = polish_guide_title(guide.title)
            body, product_json_ld = self._guide_body(guide)
            page_description = _strip_banned_phrases(guide.description)
            ld_objects = [self._guide_json_ld(guide, f"/guides/{guide.slug}/")] + product_json_ld
            html = self._render_document(
                page_title=f"{display_title} – {self.settings.name}",
                description=page_description,
                canonical_path=f"/guides/{guide.slug}/",
                body=body,
                extra_json_ld=ld_objects,
            )
            self._write_file(f"/guides/{guide.slug}/index.html", html)
            if guide.products:
                latest = max(product.updated_at for product in guide.products)
            else:
                latest = datetime.now(timezone.utc).isoformat()
            self._sitemap_entries.append((f"/guides/{guide.slug}/", latest))
        self._write_guides_index(guides)
        self._write_surprise_page(guides)
        self._write_changelog(guides)

    def _write_guides_index(self, guides: Sequence[Guide]) -> None:
        header = [
            "<section class=\"page-header\">",
            "<h1>All guides</h1>",
            "<p>Every grabgifts collection in one place.</p>",
            "</section>",
        ]
        cards = []
        for guide in sorted(
            guides, key=lambda item: polish_guide_title(item.title).lower()
        ):
            display_title = polish_guide_title(guide.title)
            first = guide.products[0] if guide.products else None
            teaser = blurb(first) if first else guide.description
            teaser = _strip_banned_phrases(teaser)
            cards.append(
                "<article class=\"card\">"
                f"<h2><a href=\"/guides/{guide.slug}/\">{display_title}</a></h2>"
                f"<p>{teaser}</p>"
                "</article>"
            )
        body_parts = header[:]
        if cards:
            body_parts.extend(
                [
                    "<div class=\"grid\">",
                    "\n".join(cards),
                    "</div>",
                ]
            )
        else:
            body_parts.append("<p>No guides are available right now.</p>")
        html = self._render_document(
            page_title=f"Guides – {self.settings.name}",
            description="Browse every GrabGifts guide.",
            canonical_path="/guides/",
            body="\n".join(body_parts),
        )
        self._write_file("/guides/index.html", html)
        self._sitemap_entries.append(("/guides/", datetime.now(timezone.utc).isoformat()))

    def _write_surprise_page(self, guides: Sequence[Guide]) -> None:
        guide_links = [
            (f"/guides/{guide.slug}/", polish_guide_title(guide.title))
            for guide in guides
            if guide.products
        ]
        guide_urls = [url for url, _ in guide_links]
        header = [
            "<section class=\"page-header\">",
            "<h1>Spin up a surprise</h1>",
            "<p>We send you to a random guide from today's drops.</p>",
            "</section>",
        ]
        body_parts = header[:]
        if guide_urls:
            body_parts.append("<p>Hold tight—we're picking something for you.</p>")
            body_parts.append(
                "<script>const guides = "
                + json.dumps(guide_urls)
                + ";if(guides.length){const target = guides[Math.floor(Math.random()*guides.length)];window.location.href = target;}</script>"
            )
            link_items = "".join(
                f"<li><a href=\"{url}\">{title}</a></li>" for url, title in guide_links
            )
            body_parts.append(
                "<noscript><p>Enable JavaScript to jump automatically. Until then, pick a guide below.</p>"
                f"<ul class=\"link-list\">{link_items}</ul></noscript>"
            )
        else:
            body_parts.append("<p>No guides are available right now. Check back soon.</p>")
        html = self._render_document(
            page_title=f"Spin up a surprise – {self.settings.name}",
            description="Jump to a random GrabGifts guide.",
            canonical_path="/surprise/",
            body="\n".join(body_parts),
        )
        self._write_file("/surprise/index.html", html)
        self._sitemap_entries.append(("/surprise/", datetime.now(timezone.utc).isoformat()))

    def _write_changelog(self, guides: Sequence[Guide]) -> None:
        entries: List[tuple[datetime, Guide]] = []
        for guide in guides:
            if guide.products:
                latest = max(product.updated_at for product in guide.products)
            else:
                latest = guide.created_at
            parsed = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            entries.append((parsed.astimezone(timezone.utc), guide))
        entries.sort(key=lambda pair: pair[0], reverse=True)
        header = [
            "<section class=\"page-header\">",
            "<h1>Live changelog</h1>",
            "<p>Follow every update we push into grabgifts.</p>",
            "</section>",
        ]
        body_parts = header[:]
        if entries:
            items = []
            for timestamp, guide in entries:
                display_title = polish_guide_title(guide.title)
                label = timestamp.strftime("%b %d, %Y %H:%M UTC")
                items.append(
                    "<li>"
                    f"<time datetime=\"{timestamp.isoformat()}\">{label}</time>"
                    f"<a href=\"/guides/{guide.slug}/\">{display_title}</a>"
                    "</li>"
                )
            body_parts.append(
                "<ul class=\"timeline\">"
                + "\n".join(items)
                + "</ul>"
            )
        else:
            body_parts.append("<p>No changes logged yet.</p>")
        html = self._render_document(
            page_title=f"Live changelog – {self.settings.name}",
            description="Track the latest GrabGifts updates.",
            canonical_path="/changelog/",
            body="\n".join(body_parts),
        )
        self._write_file("/changelog/index.html", html)
        self._sitemap_entries.append(("/changelog/", datetime.now(timezone.utc).isoformat()))

    def _write_categories(self, products: Sequence[Product]) -> None:
        categories: dict[tuple[str, str], List[Product]] = {}
        for product in products:
            if not product.category:
                continue
            slug = slugify(product.category)
            categories.setdefault((slug, product.category), []).append(product)
        for (slug, name), items in sorted(categories.items(), key=lambda pair: pair[0][1].lower()):
            ranked = sorted(items, key=_score_key, reverse=True)
            cards = []
            product_json = []
            for product in ranked[:GUIDE_ITEM_TARGET]:
                card = self._product_card(product)
                if not card:
                    continue
                card_html, payload = card
                cards.append(card_html)
                product_json.append(payload)
            description = _strip_banned_phrases(
                f"Trending picks from the {name} category updated daily."
            )
            parts = [
                "<section class=\"page-header\">",
                f"<h1>{name}</h1>",
                f"<p>{description}</p>",
                "</section>",
            ]
            if cards:
                parts.extend(
                    [
                        "<section class=\"grid\">",
                        "\n".join(cards),
                        "</section>",
                    ]
                )
            else:
                parts.append("<p>No items are available for this category right now.</p>")
            body = "\n".join(parts)
            html = self._render_document(
                page_title=f"{name} Gifts – {self.settings.name}",
                description=description,
                canonical_path=f"/categories/{slug}/",
                body=body,
                extra_json_ld=[
                    {
                        "@context": "https://schema.org",
                        "@type": "ItemList",
                        "name": f"{name} gifts",
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": idx + 1,
                                "name": product.title,
                                "url": self._abs_url(f"/products/{product.slug}/"),
                            }
                        for idx, product in enumerate(ranked[:GUIDE_ITEM_TARGET])
                        ],
                    },
                    *product_json,
                ],
            )
            self._write_file(f"/categories/{slug}/index.html", html)
            latest = max(product.updated_at for product in items)
            self._sitemap_entries.append((f"/categories/{slug}/", latest))

    def _write_products(self, products: Sequence[Product]) -> None:
        for product in products:
            description_source = product.description or blurb(product)
            description = _strip_banned_phrases(description_source)
            link = prepare_affiliate_url(product.url, product.source)
            price_display = product.price_text
            if not price_display and product.price is not None:
                currency = product.currency or "USD"
                if currency.upper() == "USD":
                    price_display = f"${product.price:,.2f}"
                else:
                    price_display = f"{product.price:,.2f} {currency.upper()}"
            tags: list[str] = []
            if product.brand:
                tags.append(html_escape(product.brand))
            if product.category:
                tags.append(html_escape(product.category))
            tags_html = (
                "<ul class=\"product-card__tags\">"
                + "".join(f"<li>{tag}</li>" for tag in tags)
                + "</ul>"
            ) if tags else ""

            price_html = (
                f"<p class=\"product-card__price\">{html_escape(price_display)}</p>"
                if price_display
                else ""
            )

            rating_html = ""
            if product.rating is not None:
                rating_value = f"{product.rating:.1f}".rstrip("0").rstrip(".")
                reviews_html = ""
                if product.rating_count and product.rating_count > 0:
                    review_word = "review" if product.rating_count == 1 else "reviews"
                    reviews_html = (
                        f"<span class=\"product-card__rating-count\">({product.rating_count:,} {review_word})</span>"
                    )
                rating_html = (
                    "<div class=\"product-card__rating\" "
                    f"aria-label=\"Rated {rating_value} out of 5\">"
                    "<span class=\"product-card__rating-icon\" aria-hidden=\"true\">★</span>"
                    f"<span class=\"product-card__rating-score\">{rating_value}</span>"
                    + reviews_html
                    + "</div>"
                )

            updated_label = _format_updated_label(product.updated_at)
            updated_html = (
                f"<p class=\"product-card__updated\">Updated {html_escape(updated_label)}</p>"
                if updated_label
                else ""
            )

            card_parts = ['<article class="product-card product-card--page">']
            if product.image:
                card_parts.append(
                    "<div class=\"product-card__media\">"
                    + f"<img src=\"{html_escape(product.image)}\" alt=\"{html_escape(product.title)}\" loading=\"lazy\">"
                    + "</div>"
                )
            card_parts.append("<div class=\"product-card__body\">")
            if tags_html:
                card_parts.append(tags_html)
            card_parts.append(
                f"<h1 class=\"product-card__title\">{html_escape(product.title)}</h1>"
            )
            if price_html:
                card_parts.append(price_html)
            if rating_html:
                card_parts.append(rating_html)
            card_parts.append(
                f"<p class=\"product-card__description\">{html_escape(description)}</p>"
            )
            card_parts.append(
                "<a class=\"button product-card__cta\" "
                f"rel=\"{affiliate_rel()}\" target=\"_blank\" href=\"{html_escape(link)}\">Shop now</a>"
            )
            if updated_html:
                card_parts.append(updated_html)
            card_parts.append("</div>")
            card_parts.append("</article>")
            body = "\n".join(card_parts)
            html = self._render_document(
                page_title=f"{product.title} – {self.settings.name}",
                description=description,
                canonical_path=f"/products/{product.slug}/",
                body=body,
                extra_json_ld=[self._product_json_ld(product, description)],
            )
            self._write_file(f"/products/{product.slug}/index.html", html)
            self._sitemap_entries.append((f"/products/{product.slug}/", product.updated_at))

    def _build_category_options(self, products: Sequence[Product]) -> list[str]:
        counts: dict[str, int] = {}
        labels: dict[str, str] = {}
        for product in products:
            if not product.category:
                continue
            label = product.category.strip()
            if not label:
                continue
            slug = slugify(label)
            if not slug:
                continue
            counts[slug] = counts.get(slug, 0) + 1
            labels.setdefault(slug, label)
        if not counts:
            return []
        total = len(products)
        options = [f'<option value="">All categories ({total:,})</option>']
        for slug in sorted(
            counts.keys(),
            key=lambda key: (-counts[key], labels[key].lower()),
        ):
            count = counts[slug]
            label = labels[slug]
            options.append(
                f'<option value="{html_escape(slug)}">{html_escape(label)} ({count:,})</option>'
            )
        return options

    def _build_price_options(self, products: Sequence[Product]) -> list[str]:
        bucket_counts = {bucket_id: 0 for bucket_id, *_ in _PRICE_BUCKETS}
        priced_total = 0
        missing_price = 0
        for product in products:
            if product.price is None:
                missing_price += 1
                continue
            price = product.price
            priced_total += 1
            for bucket_id, _label, minimum, maximum in _PRICE_BUCKETS:
                if _price_in_bucket(price, minimum, maximum):
                    bucket_counts[bucket_id] += 1
                    break
        options: list[str] = []
        if priced_total or missing_price:
            options.append('<option value="">All price ranges</option>')
            for bucket_id, label, minimum, maximum in _PRICE_BUCKETS:
                count = bucket_counts[bucket_id]
                if not count:
                    continue
                attrs: list[str] = []
                if minimum is not None:
                    attrs.append(f'data-product-min="{_format_price_value(minimum)}"')
                if maximum is not None:
                    attrs.append(f'data-product-max="{_format_price_value(maximum)}"')
                attr_text = f" {' '.join(attrs)}" if attrs else ""
                options.append(
                    f'<option value="{bucket_id}"{attr_text}>{html_escape(label)} ({count:,})</option>'
                )
            if missing_price:
                options.append(
                    f'<option value="no-price" data-product-missing="true">Price unavailable ({missing_price:,})</option>'
                )
        if len(options) <= 1:
            return []
        return options

    def _render_product_catalog(
        self, cards: Sequence[str], products: Sequence[Product]
    ) -> list[str]:
        total = len(cards)
        summary_text = f"Showing {total:,} of {total:,} products"
        summary_id = "product-results-summary"
        category_options = self._build_category_options(products)
        price_options = self._build_price_options(products)
        parts: list[str] = ['<section class="product-catalog" data-product-catalog>']
        parts.extend(
            [
                '  <div class="product-catalog__controls">',
                '    <form class="product-filters" data-product-form>',
                '      <div class="product-filters__fields">',
                '        <div class="product-filters__group product-filters__group--search">',
                '          <label class="product-filters__label" for="product-search">Search</label>',
                '          <input class="product-filters__input" type="search" id="product-search" name="search" placeholder="Search by product, brand, or keyword" autocomplete="off" spellcheck="false" aria-describedby="product-results-summary" data-product-search>',
                '        </div>',
            ]
        )
        if category_options:
            parts.append('        <div class="product-filters__group">')
            parts.append('          <label class="product-filters__label" for="product-category">Category</label>')
            parts.append('          <select class="product-filters__select" id="product-category" name="category" data-product-filter="category">')
            parts.extend(f"            {option}" for option in category_options)
            parts.append('          </select>')
            parts.append('        </div>')
        if price_options:
            parts.append('        <div class="product-filters__group">')
            parts.append('          <label class="product-filters__label" for="product-price">Price</label>')
            parts.append('          <select class="product-filters__select" id="product-price" name="price" data-product-filter="price">')
            parts.extend(f"            {option}" for option in price_options)
            parts.append('          </select>')
            parts.append('        </div>')
        parts.extend(
            [
                '      </div>',
                '      <div class="product-filters__actions">',
                '        <button type="reset" class="button button-ghost product-filters__reset">Clear filters</button>',
                '      </div>',
                '    </form>',
                f'    <p class="product-filters__summary" id="{summary_id}" data-product-summary aria-live="polite">{summary_text}</p>',
                '  </div>',
                '  <section class="feed-section product-catalog__results">',
                f'    <div class="feed-list" data-product-grid data-product-total="{total}">',
            ]
        )
        parts.extend(f"      {card}" for card in cards)
        parts.extend(
            [
                '    </div>',
                '  </section>',
                '  <p class="product-catalog__empty" data-product-empty aria-live="polite" hidden>No products match your filters yet. Try adjusting or clearing the filters.</p>',
                '</section>',
            ]
        )
        return parts

    def _write_products_index(self, products: Sequence[Product]) -> None:
        header = [
            '<section class="page-header">',
            '<h1>All products</h1>',
            '<p>Every grabgifts find in one catalog. Use the filters below to zero in on the perfect gift fast.</p>',
            '</section>',
        ]
        sorted_products = sorted(
            products,
            key=lambda item: (
                max(
                    _parse_iso_datetime(item.created_at),
                    _parse_iso_datetime(item.updated_at),
                ),
                item.title.lower() if item.title else "",
            ),
            reverse=True,
        )
        cards: list[str] = []
        for product in sorted_products:
            card = self._product_preview_card(product)
            if not card:
                continue
            cards.append(card)

        body_parts = header[:]
        if cards:
            body_parts.extend(self._render_product_catalog(cards, sorted_products))
        else:
            body_parts.append("<p>No products are available right now.</p>")

        html = self._render_document(
            page_title=f"Products – {self.settings.name}",
            description="Browse every product in the GrabGifts catalog with fast category, price, and keyword filters.",
            canonical_path="/products/",
            body="\n".join(body_parts),
        )
        self._write_file("/products/index.html", html)
        latest = max(
            (
                max(
                    _parse_iso_datetime(product.created_at),
                    _parse_iso_datetime(product.updated_at),
                )
                for product in sorted_products
            ),
            default=datetime.now(timezone.utc),
        )
        self._sitemap_entries.append(("/products/", latest.isoformat()))

    def _write_about(self, guides: Sequence[Guide], products: Sequence[Product]) -> None:
        live_guides = [guide for guide in guides if guide.products]
        live_count = len(live_guides)
        total_products = len(products)
        category_counts = Counter(
            product.category for product in products if product.category
        )
        category_count = len([name for name in category_counts])
        brand_count = len({product.brand for product in products if product.brand})
        top_categories = [name for name, _ in category_counts.most_common(3)]
        stats_cards: list[str] = []
        if live_count:
            guide_label = "guides" if live_count != 1 else "guide"
            verb = "regenerate" if live_count != 1 else "regenerates"
            refresh_text = (
                f"{live_count:,} {guide_label} {verb} before most people finish their first coffee."
            )
        else:
            refresh_text = (
                "Our automations rebuild the entire catalog every morning so it is ready the moment new inventory appears."
            )
        stats_cards.append(
            "<article class=\"quality-card\">"
            "<h3>Daily refresh cadence</h3>"
            f"<p>{refresh_text}</p>"
            "</article>"
        )
        coverage_bits: list[str] = []
        if total_products:
            coverage_bits.append(f"{total_products:,} gift ideas tracked")
        if category_count:
            category_label = "categories" if category_count != 1 else "category"
            coverage_bits.append(f"{category_count} {category_label} monitored")
        if brand_count:
            brand_label = "brands" if brand_count != 1 else "brand"
            coverage_bits.append(f"{brand_count:,} {brand_label} represented")
        if coverage_bits:
            coverage_text = _join_with_and(coverage_bits)
            coverage_text = f"{coverage_text}."
        else:
            coverage_text = (
                "We monitor standout gift ideas across the marketplaces our audience shops most."
            )
        stats_cards.append(
            "<article class=\"quality-card\">"
            "<h3>Catalog depth</h3>"
            f"<p>{coverage_text}</p>"
            "</article>"
        )
        stats_cards.append(
            "<article class=\"quality-card\">"
            "<h3>Editorial guardrails</h3>"
            "<p>Every pick ships with human-written copy, duplicate scrubbing, and pricing context before it goes live.</p>"
            "</article>"
        )
        if top_categories:
            escaped = [html_escape(name) for name in top_categories]
            categories_text = _join_with_and(escaped)
            verb = "lead" if len(escaped) != 1 else "leads"
            stats_cards.append(
                "<article class=\"quality-card\">"
                "<h3>Trending themes</h3>"
                f"<p>{categories_text} currently {verb} the click-through charts.</p>"
                "</article>"
            )
        mission_cards = [
            (
                "<article class=\"card\">"
                "<h3>What you'll find</h3>"
                f"<p>Each guide showcases {GUIDE_ITEM_TARGET} standout gifts with pricing context, verified imagery, and quick-scan blurbs.</p>"
                "</article>"
            ),
            (
                "<article class=\"card\">"
                "<h3>Signals we monitor</h3>"
                "<p>Release calendars, retailer feeds, review velocity, and community chatter all factor into our selections.</p>"
                "</article>"
            ),
            (
                "<article class=\"card\">"
                "<h3>Automation plus humans</h3>"
                "<p>Scripted pipelines flag promising items while editors trim the noise, rewrite copy, and ensure merchandising stays sharp.</p>"
                "</article>"
            ),
        ]
        if category_count and top_categories:
            category_label = "categories" if category_count != 1 else "category"
            highlighted = _join_with_and([html_escape(name) for name in top_categories])
            focus_verb = "are" if len(top_categories) != 1 else "is"
            mission_cards.append(
                "<article class=\"card\">"
                "<h3>Where we focus</h3>"
                f"<p>We constantly rotate through {category_count} {category_label}, with {highlighted} {focus_verb} resonating right now.</p>"
                "</article>"
            )
        cta_links = [
            "<li><a href=\"/guides/\">Browse today's guides</a></li>",
            "<li><a href=\"/how-we-curate/\">See how we curate</a></li>",
            "<li><a href=\"/contact/\">Reach the team</a></li>",
        ]
        body_parts = [
            "<section class=\"page-header\">",
            "<h1>About grabgifts</h1>",
            "<p>grabgifts is a small editorial studio tracking giftable finds with automation, data, and a human edit pass.</p>",
            "</section>",
            "<section class=\"quality-section\" aria-labelledby=\"about-highlights\">",
            "<div class=\"page-header\">",
            "<h2 id=\"about-highlights\">What drives the project</h2>",
            "<p>Metrics, manual curation, and constant iteration keep the catalog trustworthy.</p>",
            "</div>",
            "<div class=\"quality-grid\">",
            "".join(stats_cards),
            "</div>",
            "</section>",
            "<section>",
            "<div class=\"page-header\">",
            "<h2>How we work</h2>",
            "<p>Automation handles the heavy lifting while editors focus on storytelling and product fit.</p>",
            "</div>",
            "<div class=\"grid\">",
            "\n".join(mission_cards),
            "</div>",
            "</section>",
            "<section>",
            "<div class=\"page-header\">",
            "<h2>Explore more</h2>",
            "<p>Jump into the latest guides or learn more about our process.</p>",
            "</div>",
            f"<ul class=\"link-list\">{''.join(cta_links)}</ul>",
            "</section>",
        ]
        html = self._render_document(
            page_title=f"About {self.settings.name}",
            description=f"Meet the {self.settings.name} team and see how we scout giftable products.",
            canonical_path="/about/",
            body="\n".join(body_parts),
        )
        self._write_file("/about/index.html", html)
        self._sitemap_entries.append(("/about/", datetime.now(timezone.utc).isoformat()))

    def _write_curation_page(
        self, guides: Sequence[Guide], products: Sequence[Product]
    ) -> None:
        total_products = len(products)
        guide_count = len(guides)
        signals = [
            (
                "<article class=\"quality-card\">"
                "<h3>Inventory sweep</h3>"
                "<p>Marketplace APIs and curated retailer feeds pipe in promising items with pricing, imagery, and metadata.</p>"
                "</article>"
            ),
            (
                "<article class=\"quality-card\">"
                "<h3>Signal scoring</h3>"
                "<p>We weigh release timing, review velocity, price movement, and gifting fit to rank every product candidate.</p>"
                "</article>"
            ),
            (
                "<article class=\"quality-card\">"
                "<h3>Editorial pass</h3>"
                f"<p>Editors fact-check availability, write blurbs, and assemble {GUIDE_ITEM_TARGET}-item lineups ready for syndication.</p>"
                "</article>"
            ),
        ]
        guardrails = [
            (
                "<article class=\"card\">"
                "<h3>Duplication control</h3>"
                "<p>IDs, URLs, and titles are normalized so repeats never sneak into a guide.</p>"
                "</article>"
            ),
            (
                "<article class=\"card\">"
                "<h3>Price monitoring</h3>"
                "<p>We refresh price data daily and surface shifts that change the recommendation.</p>"
                "</article>"
            ),
            (
                "<article class=\"card\">"
                "<h3>Compliance ready</h3>"
                "<p>Affiliate rel attributes, sponsored disclosures, and JSON-LD ship in every build.</p>"
                "</article>"
            ),
        ]
        timeline_entries = [
            ("07:00", "Automation syncs pricing, inventory status, and new arrivals."),
            ("11:00", "Editors review flagged products and slot new standouts into guides."),
            ("15:00", "Guides regenerate, metadata refreshes, and the static site deploys."),
        ]
        timeline_markup = []
        for label, description in timeline_entries:
            timeline_markup.append(
                "<li>"
                f"<time datetime=\"{label}\">{label} UTC</time>"
                f"<span>{description}</span>"
                "</li>"
            )
        summary_bits: list[str] = []
        if guide_count:
            guide_label = "guides" if guide_count != 1 else "guide"
            summary_bits.append(f"{guide_count} {guide_label} in rotation")
        if total_products:
            product_label = "products" if total_products != 1 else "product"
            summary_bits.append(f"{total_products:,} {product_label} scored")
        summary_text = " and ".join(summary_bits) if summary_bits else "Our pipeline hums along even when inventory is light"
        body_parts = [
            "<section class=\"page-header\">",
            "<h1>How we curate</h1>",
            f"<p>{summary_text}. Here's how the workflow runs end to end.</p>",
            "</section>",
            "<section class=\"quality-section\" aria-labelledby=\"curation-steps\">",
            "<div class=\"page-header\">",
            "<h2 id=\"curation-steps\">Three phases keep quality high</h2>",
            "<p>Automation narrows the field, scoring ranks the contenders, and editors finalize every recommendation.</p>",
            "</div>",
            "<div class=\"quality-grid\">",
            "".join(signals),
            "</div>",
            "</section>",
            "<section>",
            "<div class=\"page-header\">",
            "<h2>Daily publishing rhythm</h2>",
            "<p>Each build runs on a repeatable schedule so updates land like clockwork.</p>",
            "</div>",
            "<ul class=\"timeline\">",
            "".join(timeline_markup),
            "</ul>",
            "</section>",
            "<section>",
            "<div class=\"page-header\">",
            "<h2>Quality guardrails</h2>",
            "<p>Checks fire on every run to catch anything that could erode trust.</p>",
            "</div>",
            "<div class=\"grid\">",
            "\n".join(guardrails),
            "</div>",
            "</section>",
            "<section>",
            "<div class=\"page-header\">",
            "<h2>Need something else?</h2>",
            "<p>Reach out if you want to collaborate, request coverage, or surface feedback.</p>",
            "</div>",
            "<ul class=\"link-list\"><li><a href=\"/contact/\">Contact the editors</a></li><li><a href=\"/about/\">Learn about grabgifts</a></li></ul>",
            "</section>",
        ]
        html = self._render_document(
            page_title=f"How {self.settings.name} curates",
            description=f"Understand the scoring pipeline and editorial guardrails that power {self.settings.name}.",
            canonical_path="/how-we-curate/",
            body="\n".join(body_parts),
        )
        self._write_file("/how-we-curate/index.html", html)
        self._sitemap_entries.append(("/how-we-curate/", datetime.now(timezone.utc).isoformat()))

    def _write_contact(self) -> None:
        contact_email = self.settings.contact_email or "support@grabgifts.net"
        contact_label = html_escape(contact_email)
        contact_href = html_escape(f"mailto:{contact_email}")
        social_links: list[str] = []

        def _normalize_social(value: str, prefix: str) -> str:
            cleaned = value.strip()
            if cleaned.startswith("http://") or cleaned.startswith("https://"):
                return cleaned
            handle = cleaned.lstrip("@")
            return f"{prefix}{handle}"

        if self.settings.twitter:
            twitter_url = _normalize_social(self.settings.twitter, "https://twitter.com/")
            social_links.append(
                "<li><a href=\""
                + html_escape(twitter_url)
                + "\" target=\"_blank\" rel=\"noopener\">Say hi on X (Twitter)</a></li>"
            )
        if self.settings.facebook:
            facebook_url = _normalize_social(self.settings.facebook, "https://facebook.com/")
            social_links.append(
                "<li><a href=\""
                + html_escape(facebook_url)
                + "\" target=\"_blank\" rel=\"noopener\">Follow along on Facebook</a></li>"
            )
        link_items = [
            f"<li><a href=\"{contact_href}\">Email {contact_label}</a></li>",
            "<li><a href=\"/faq/\">Review our FAQ &amp; disclosure</a></li>",
            "<li><a href=\"/guides/\">Catch today's guides</a></li>",
        ]
        link_items.extend(social_links)
        support_cards = [
            (
                "<article class=\"quality-card\">"
                "<h3>Partnerships &amp; pitches</h3>"
                "<p>Share launch timelines, exclusive bundles, or affiliate-ready drops you'd like us to evaluate.</p>"
                "</article>"
            ),
            (
                "<article class=\"quality-card\">"
                "<h3>Corrections</h3>"
                "<p>See an item go out of stock or pricing that drifted? Send the details and we will rerun the checks.</p>"
                "</article>"
            ),
            (
                "<article class=\"quality-card\">"
                "<h3>Press &amp; inquiries</h3>"
                "<p>Need a quote about gifting trends or our automation stack? Drop a note and we will respond quickly.</p>"
                "</article>"
            ),
        ]
        expectations_cards = [
            (
                "<article class=\"card\">"
                "<h3>Response time</h3>"
                "<p>We aim to reply within one business day, often sooner when a launch is in motion.</p>"
                "</article>"
            ),
            (
                "<article class=\"card\">"
                "<h3>What to include</h3>"
                "<p>Links, pricing, regional availability, and any embargo dates help us act fast.</p>"
                "</article>"
            ),
        ]
        body_parts = [
            "<section class=\"page-header\">",
            "<h1>Contact the grabgifts editors</h1>",
            "<p>We love hearing about new products, partnerships, and feedback from shoppers.</p>",
            "</section>",
            "<section class=\"quality-section\" aria-labelledby=\"contact-topics\">",
            "<div class=\"page-header\">",
            "<h2 id=\"contact-topics\">How we can help</h2>",
            "<p>Pick the lane that matches what you need and we will route it to the right editor.</p>",
            "</div>",
            "<div class=\"quality-grid\">",
            "".join(support_cards),
            "</div>",
            "</section>",
            "<section>",
            "<div class=\"page-header\">",
            "<h2>Reach us quickly</h2>",
            "<p>Choose the channel that works best for you.</p>",
            "</div>",
            f"<ul class=\"link-list\">{''.join(link_items)}</ul>",
            "</section>",
            "<section>",
            "<div class=\"page-header\">",
            "<h2>Set expectations</h2>",
            "<p>A little prep goes a long way and keeps the catalog clean.</p>",
            "</div>",
            "<div class=\"grid\">",
            "\n".join(expectations_cards),
            "</div>",
            "</section>",
        ]
        html = self._render_document(
            page_title=f"Contact {self.settings.name}",
            description=f"Get in touch with the {self.settings.name} editors for partnerships, tips, or support.",
            canonical_path="/contact/",
            body="\n".join(body_parts),
        )
        self._write_file("/contact/index.html", html)
        self._sitemap_entries.append(("/contact/", datetime.now(timezone.utc).isoformat()))

    def _write_faq(self) -> None:
        contact_email = self.settings.contact_email or "support@grabgifts.net"
        contact_label = html_escape(contact_email)
        contact_href = html_escape(f"mailto:{contact_email}")
        body = "\n".join(
            [
                "<h1>Affiliate disclosure</h1>",
                "<p>GrabGifts may earn commissions from qualifying purchases made through outbound links. We only feature items that fit our curated guides.</p>",
                f"<p>Questions? Contact us at <a href=\"{contact_href}\">{contact_label}</a>.</p>",
            ]
        )
        html = self._render_document(
            page_title="Affiliate disclosure",
            description="Affiliate disclosure",
            canonical_path="/faq/",
            body=body,
        )
        self._write_file("/faq/index.html", html)
        self._sitemap_entries.append(("/faq/", datetime.now(timezone.utc).isoformat()))

    # ------------------------------------------------------------------
    # Static assets

    def _write_sitemap(self) -> None:
        entries = [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">",
        ]
        for path, lastmod in self._sitemap_entries:
            entries.append("<url>")
            entries.append(f"<loc>{self._abs_url(path)}</loc>")
            entries.append(f"<lastmod>{lastmod}</lastmod>")
            entries.append("</url>")
        entries.append("</urlset>")
        self._safe_write(self.output_dir / "sitemap.xml", "\n".join(entries))

    def _write_robots(self) -> None:
        content = (
            "User-agent: *\nAllow: /\n"
            f"Sitemap: {self._abs_url('/sitemap.xml')}\n"
        )
        self._safe_write(self.output_dir / "robots.txt", content)

    def _write_rss(self, guides: Sequence[Guide]) -> None:
        base = self._abs_url("/")
        items: List[str] = []
        for guide in guides[:20]:
            link = self._abs_url(f"/guides/{guide.slug}/")
            description = guide.description
            display_title = polish_guide_title(guide.title)
            items.append(
                "<item>"
                f"<title>{display_title}</title>"
                f"<link>{link}</link>"
                f"<guid>{link}</guid>"
                f"<description><![CDATA[{description}]]></description>"
                f"<pubDate>{_format_rfc2822(guide.created_at)}</pubDate>"
                "</item>"
            )
        rss = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<rss version=\"2.0\"><channel>"
            f"<title>{self.settings.name}</title>"
            f"<link>{base}</link>"
            f"<description>{self.settings.description}</description>"
            f"{''.join(items)}"
            "</channel></rss>"
        )
        self._safe_write(self.output_dir / "rss.xml", rss)


def _format_rfc2822(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    except Exception:  # pragma: no cover - invalid dates
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _score_key(product: Product) -> tuple:
    rating = float(product.rating or 0.0)
    reviews = int(product.rating_count or 0)
    try:
        updated = datetime.fromisoformat(product.updated_at).timestamp()
    except Exception:
        updated = 0.0
    return (rating, reviews, updated)
