"""Static site generator for the GrabGifts catalog."""
from __future__ import annotations
import json
import logging
import os
import re
from html import escape as html_escape
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from .affiliates import affiliate_rel, prepare_affiliate_url
from .blog import blurb
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


_BANNED_PHRASES = ("fresh drops", "active vibes")

_STOPWORDS = {"for", "a", "the", "and", "of"}
_RIGHT_NOW_SUFFIX = re.compile(r"\s+right now\.?$", re.IGNORECASE)
_BEST_FOR_PATTERN = re.compile(
    r"(?i)^best\s+for\s+a\s+(?P<subject>.+?)\s+gifts(?P<tail>.*)$"
)
_TITLE_REPLACEMENTS = {"Techy": "Tech"}


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


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


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
        self._write_faq()
        self._write_sitemap()
        self._write_robots()
        self._write_rss(guides)

    # ------------------------------------------------------------------
    # Rendering helpers

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
        meta_parts: list[str] = []
        if product.category:
            meta_parts.append(html_escape(product.category))
        if product.brand:
            meta_parts.append(html_escape(product.brand))
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
        id_attr = f" data-product-id=\"{html_escape(product.id)}\"" if product.id else ""
        slug = html_escape(product.slug)
        image = html_escape(product.image)
        title = html_escape(product.title)
        return (
            f"<article class=\"feed-card\" data-home-product-card=\"true\"{id_attr}>"
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
        if cards:
            parts.append(f"<section class=\"grid\">{cards}</section>")
        else:
            parts.append("<p>No items are available for this guide right now.</p>")
        return "\n".join(parts), json_ld

    def _write_homepage(
        self, guides: Sequence[Guide], products: Sequence[Product]
    ) -> None:
        timestamps: list[datetime] = []
        for guide in guides:
            if guide.products:
                timestamps.extend(
                    _parse_iso_datetime(product.updated_at)
                    for product in guide.products
                )
            else:
                timestamps.append(_parse_iso_datetime(guide.created_at))
        for product in products:
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
        sorted_guides = sorted(
            guides,
            key=lambda item: (
                _parse_iso_datetime(item.created_at),
                polish_guide_title(item.title).lower(),
            ),
            reverse=True,
        )
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
        hero_markup.extend(
            [
                "<div class=\"hero-actions\">",
                "<a class=\"button\" href=\"/guides/\">Explore today's drops</a>",
                "<a class=\"button button-secondary\" href=\"/surprise/\">Spin up a surprise</a>",
                "<a class=\"button button-ghost\" href=\"/changelog/\">See the live changelog</a>",
                "</div>",
            ]
        )
        hero_markup.append("</section>")
        sections: List[str] = ["\n".join(hero_markup)]
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
            details: list[str] = []
            if product.brand:
                details.append(product.brand)
            if product.category:
                details.append(product.category)
            body_parts = [
                "<section class=\"page-header\">",
                f"<h1>{product.title}</h1>",
                f"<p>{description}</p>",
                "</section>",
            ]
            if product.image:
                body_parts.append(
                    f"<img src=\"{product.image}\" alt=\"{product.title}\" loading=\"lazy\">"
                )
            if details:
                body_parts.append(f"<p>{' • '.join(details)}</p>")
            if price_display:
                body_parts.append(f"<p class=\"price\">{price_display}</p>")
            body_parts.append(
                f"<p><a class=\"button\" rel=\"{affiliate_rel()}\" target=\"_blank\" href=\"{link}\">Shop now</a></p>"
            )
            body = "\n".join(body_parts)
            html = self._render_document(
                page_title=f"{product.title} – {self.settings.name}",
                description=description,
                canonical_path=f"/products/{product.slug}/",
                body=body,
                extra_json_ld=[self._product_json_ld(product, description)],
            )
            self._write_file(f"/products/{product.slug}/index.html", html)
            self._sitemap_entries.append((f"/products/{product.slug}/", product.updated_at))

    def _write_faq(self) -> None:
        body = "\n".join(
            [
                "<h1>Affiliate disclosure</h1>",
                "<p>GrabGifts may earn commissions from qualifying purchases made through outbound links. We only feature items that fit our curated guides.</p>",
                "<p>Questions? Contact us at support@grabgifts.net.</p>",
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
