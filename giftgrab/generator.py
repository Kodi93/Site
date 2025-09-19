"""Static site generator for the GiftGrab catalog."""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from .affiliates import affiliate_rel, prepare_affiliate_url
from .blog import blurb
from .models import Guide, Product
from .utils import slugify

ROOT_DIR = Path(__file__).resolve().parent.parent
HEADER_PATH = ROOT_DIR / "templates" / "partials" / "header.html"
FOOTER_PATH = ROOT_DIR / "templates" / "partials" / "footer.html"
THEME_PATH = ROOT_DIR / "public" / "assets" / "theme.css"
PROTECTED_FILES = {
    HEADER_PATH.resolve(),
    FOOTER_PATH.resolve(),
    THEME_PATH.resolve(),
}


def _load_partials() -> tuple[str, str, str]:
    header_raw = HEADER_PATH.read_text(encoding="utf-8").lstrip("\ufeff")
    match = re.match(r"^\s*<!doctype html>\s*", header_raw, flags=re.IGNORECASE)
    if match:
        doctype = match.group(0).strip()
        header_markup = header_raw[match.end():]
    else:
        doctype = "<!doctype html>"
        header_markup = header_raw
    header_markup = header_markup.strip()
    footer_markup = FOOTER_PATH.read_text(encoding="utf-8").strip()
    return doctype, f"{header_markup}\n", f"{footer_markup}\n"


HEADER_DOCTYPE, HEADER_PARTIAL, FOOTER_PARTIAL = _load_partials()

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
        name=_env("SITE_NAME", "GiftGrab") or "GiftGrab",
        base_url=_env("SITE_BASE_URL", "https://example.com"),
        description=_env(
            "SITE_DESCRIPTION",
            "Daily gift roundups featuring gadgets, home comforts, and fun surprises.",
        )
        or "Daily gift roundups featuring gadgets, home comforts, and fun surprises.",
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
        self._website_json_ld = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": self.settings.name,
                "url": self.settings.base_url,
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": f"{self.settings.base_url}/search?q={{query}}",
                    "query-input": "required name=query",
                },
            },
            separators=(",", ":"),
        )

    # ------------------------------------------------------------------
    # Public API

    def build(self, *, products: Sequence[Product], guides: Sequence[Guide]) -> None:
        LOGGER.info("Rendering site to %s", self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sitemap_entries = []
        self._write_homepage(guides)
        self._write_guides(guides)
        self._write_categories(products)
        self._write_products(products)
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
        if not self.settings.adsense_client_id or not slot:
            return ""
        return (
            f"<ins class=\"adsbygoogle\" style=\"display:block\" data-ad-client=\"{self.settings.adsense_client_id}\" "
            f"data-ad-slot=\"{slot}\" data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>"
            "<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>"
        )

    def _safe_write(self, target: Path, content: str) -> None:
        resolved = target.resolve()
        if resolved in PROTECTED_FILES:
            raise RuntimeError("Protected layout files may not be modified by content builds.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _write_file(self, path: str, content: str) -> None:
        file_path = self.output_dir / path.lstrip("/")
        if file_path.name != "index.html":
            file_path = file_path / "index.html"
        self._safe_write(file_path, content)

    def _page_head(
        self,
        *,
        title: str,
        description: str,
        canonical_path: str,
        extra_json_ld: Iterable[dict] | None = None,
    ) -> str:
        canonical_url = self._abs_url(canonical_path)
        pieces = [
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            f"<title>{title}</title>",
            f"<link rel=\"canonical\" href=\"{canonical_url}\">",
            f"<meta name=\"description\" content=\"{description}\">",
            f"<meta property=\"og:type\" content=\"website\">",
            f"<meta property=\"og:title\" content=\"{title}\">",
            f"<meta property=\"og:description\" content=\"{description}\">",
            f"<meta property=\"og:url\" content=\"{canonical_url}\">",
            f"<meta property=\"og:site_name\" content=\"{self.settings.name}\">",
            "<meta name=\"twitter:card\" content=\"summary_large_image\">",
            f"<meta name=\"twitter:title\" content=\"{title}\">",
            f"<meta name=\"twitter:description\" content=\"{description}\">",
            f"<meta name=\"twitter:url\" content=\"{canonical_url}\">",
            f"<link rel=\"alternate\" type=\"application/rss+xml\" title=\"{self.settings.name} RSS\" href=\"{self._abs_url('/rss.xml')}\">",
            "<link rel=\"stylesheet\" href=\"/assets/theme.css\">",
            f"<script type=\"application/ld+json\">{self._website_json_ld}</script>",
        ]
        if self.settings.logo_url:
            pieces.append(f"<meta property=\"og:image\" content=\"{self.settings.logo_url}\">")
            pieces.append(f"<meta name=\"twitter:image\" content=\"{self.settings.logo_url}\">")
        if self.settings.favicon_url:
            pieces.append(f"<link rel=\"icon\" href=\"{self.settings.favicon_url}\">")
        if self.settings.twitter:
            pieces.append(f"<meta name=\"twitter:site\" content=\"{self.settings.twitter}\">")
        if self.settings.keywords:
            pieces.append(
                f"<meta name=\"keywords\" content=\"{', '.join(self.settings.keywords)}\">"
            )
        if self.settings.analytics_snippet:
            pieces.append(self.settings.analytics_snippet)
        elif self.settings.analytics_id:
            gid = self.settings.analytics_id
            pieces.append(
                "<script async src=\"https://www.googletagmanager.com/gtag/js?id="
                f"{gid}\"></script>"
            )
            pieces.append(
                "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                "gtag('js', new Date());gtag('config','" + gid + "');</script>"
            )
        if self.settings.adsense_client_id:
            pieces.append(
                "<script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client="
                f"={self.settings.adsense_client_id}\" crossorigin=\"anonymous\"></script>"
            )
        for obj in extra_json_ld or []:
            pieces.append(
                f"<script type=\"application/ld+json\">{json.dumps(obj, separators=(',', ':'))}</script>"
            )
        return "\n".join(pieces)

    def _page_shell(self, *, head: str, body: str) -> str:
        body_html = body if body.endswith("\n") else f"{body}\n"
        return (
            f"{HEADER_DOCTYPE}\n"
            f"<html lang=\"en\"><head>{head}</head><body>\n"
            f"{HEADER_PARTIAL}"
            f"<main><div class=\"wrap\">{body_html}</div></main>\n"
            f"{FOOTER_PARTIAL}</body></html>"
        )

    def _guide_json_ld(self, guide: Guide, canonical_path: str) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": guide.title,
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

    def _product_card(self, product: Product) -> tuple[str, dict]:
        description = blurb(product)
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
        if product.rating:
            meta_parts.append(f"{product.rating:.1f}★")
        body = ["<article class=\"card\">"]
        if product.image:
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

    def _guide_body(self, guide: Guide) -> tuple[str, List[dict]]:
        cards_html = []
        json_ld: List[dict] = []
        for product in guide.products:
            card_html, payload = self._product_card(product)
            cards_html.append(card_html)
            json_ld.append(payload)
        cards = "".join(cards_html)
        ad_block = self._adsense_unit(self.settings.adsense_slot)
        parts = [f"<h1>{guide.title}</h1>", f"<p>{guide.description}</p>"]
        if ad_block:
            parts.append(ad_block)
        parts.append(f"<section class=\"grid\">{cards}</section>")
        parts.append(
            "<p class=\"disclosure\">Affiliate links may earn commissions. Prices and availability can change.</p>"
        )
        return "\n".join(parts), json_ld

    def _write_homepage(self, guides: Sequence[Guide]) -> None:
        if guides:
            last_updated = max(
                product.updated_at
                for guide in guides
                for product in guide.products
            )
        else:
            last_updated = datetime.now(timezone.utc).isoformat()
        cards = []
        for guide in guides[:12]:
            first = guide.products[0] if guide.products else None
            teaser = blurb(first) if first else guide.description
            cards.append(
                "<article class=\"card\">"
                f"<h2><a href=\"/guides/{guide.slug}/\">{guide.title}</a></h2>"
                f"<p>{teaser}</p>"
                f"<a class=\"button\" href=\"/guides/{guide.slug}/\">View guide</a>"
                "</article>"
            )
        cards_html = "".join(cards)
        ad_block = self._adsense_unit(self.settings.adsense_slot)
        parts = [
            f"<h1>{self.settings.name}</h1>",
            f"<p>{self.settings.description}</p>",
        ]
        if ad_block:
            parts.append(ad_block)
        if cards_html:
            parts.append(f"<section class=\"grid\">{cards_html}</section>")
        else:
            parts.append(
                "<p class=\"disclosure\">Guides are being prepared. Check back soon.</p>"
            )
        parts.append(
            "<p class=\"disclosure\">As an Amazon Associate and eBay Partner Network member we earn from qualifying purchases.</p>"
        )
        body = "\n".join(parts)
        head = self._page_head(
            title=self.settings.name,
            description=self.settings.description,
            canonical_path="/",
        )
        html = self._page_shell(head=head, body=body)
        self._write_file("/index.html", html)
        self._sitemap_entries.append(("/", last_updated))

    def _write_guides(self, guides: Sequence[Guide]) -> None:
        for guide in guides:
            body, product_json_ld = self._guide_body(guide)
            ld_objects = [self._guide_json_ld(guide, f"/guides/{guide.slug}/")] + product_json_ld
            head = self._page_head(
                title=f"{guide.title} – {self.settings.name}",
                description=guide.description,
                canonical_path=f"/guides/{guide.slug}/",
                extra_json_ld=ld_objects,
            )
            html = self._page_shell(head=head, body=body)
            self._write_file(f"/guides/{guide.slug}/index.html", html)
            if guide.products:
                latest = max(product.updated_at for product in guide.products)
            else:
                latest = datetime.now(timezone.utc).isoformat()
            self._sitemap_entries.append((f"/guides/{guide.slug}/", latest))

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
                card_html, payload = self._product_card(product)
                cards.append(card_html)
                product_json.append(payload)
            description = f"Trending picks from the {name} category updated daily."
            parts = [
                f"<h1>{name}</h1>",
                f"<p>{description}</p>",
                f"<section class=\"grid\">{''.join(cards)}</section>",
                "<p class=\"disclosure\">Prices and availability are subject to change.</p>",
            ]
            body = "\n".join(parts)
            head = self._page_head(
                title=f"{name} Gifts – {self.settings.name}",
                description=description,
                canonical_path=f"/categories/{slug}/",
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
            html = self._page_shell(head=head, body=body)
            self._write_file(f"/categories/{slug}/index.html", html)
            latest = max(product.updated_at for product in items)
            self._sitemap_entries.append((f"/categories/{slug}/", latest))

    def _write_products(self, products: Sequence[Product]) -> None:
        for product in products:
            description = blurb(product)
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
            if product.rating:
                details.append(f"{product.rating:.1f}★")
            body_parts = [f"<h1>{product.title}</h1>", f"<p>{description}</p>"]
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
            rail = self._adsense_unit(self.settings.adsense_rail_slot)
            if rail:
                body_parts.append(rail)
            body_parts.append(
                "<p class=\"disclosure\">Affiliate links may earn commissions. Always verify current pricing and availability.</p>"
            )
            body = "\n".join(body_parts)
            head = self._page_head(
                title=f"{product.title} – {self.settings.name}",
                description=description,
                canonical_path=f"/products/{product.slug}/",
                extra_json_ld=[self._product_json_ld(product, description)],
            )
            html = self._page_shell(head=head, body=body)
            self._write_file(f"/products/{product.slug}/index.html", html)
            self._sitemap_entries.append((f"/products/{product.slug}/", product.updated_at))

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
            items.append(
                "<item>"
                f"<title>{guide.title}</title>"
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
