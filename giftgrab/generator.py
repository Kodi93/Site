"""Static site generator responsible for producing the HTML pages."""
from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .config import OUTPUT_DIR, SiteSettings, ensure_directories
from .models import Category, Product

logger = logging.getLogger(__name__)

ASSETS_STYLES = """
:root {
  color-scheme: light;
  --brand: #ff5a5f;
  --brand-dark: #e04850;
  --accent: #1c64f2;
  --bg: #f6f7fb;
  --text: #1f2933;
  --muted: #6c7983;
  --card: #ffffff;
  --border: #e1e7ef;
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}

img {
  max-width: 100%;
  display: block;
}

a {
  color: var(--brand);
  text-decoration: none;
  transition: color 0.2s ease;
}

a:hover,
a:focus {
  color: var(--brand-dark);
}

.skip-link {
  position: absolute;
  left: -999px;
  top: 0;
  background: var(--brand);
  color: #fff;
  padding: 0.6rem 1rem;
  border-radius: 0 0 12px 12px;
  font-weight: 600;
  z-index: 1000;
}

.skip-link:focus {
  left: 1rem;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

header {
  background: #ffffffcc;
  backdrop-filter: blur(6px);
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1px solid var(--border);
}

nav {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.5rem;
}

.logo {
  font-weight: 700;
  font-size: 1.2rem;
  color: var(--text);
}

.nav-groups {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.nav-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.95rem;
}

.nav-links a {
  color: var(--muted);
  font-weight: 500;
}

.nav-links a:hover,
.nav-links a:focus {
  color: var(--brand);
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.nav-actions a {
  color: var(--muted);
  font-weight: 500;
}

.nav-actions a:hover,
.nav-actions a:focus {
  color: var(--brand);
}

.pill-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-weight: 600;
  color: var(--brand);
  background: rgba(255, 90, 95, 0.08);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.pill-link:hover,
.pill-link:focus {
  background: rgba(255, 90, 95, 0.16);
  color: var(--brand-dark);
  transform: translateY(-1px);
}

.search-form {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.55rem;
  background: rgba(15, 23, 42, 0.04);
  border-radius: 999px;
}

.search-form input {
  border: none;
  background: transparent;
  font-size: 0.95rem;
  padding: 0.35rem 0.1rem 0.35rem 0.35rem;
  color: var(--text);
  min-width: 180px;
}

.search-form input:focus {
  outline: none;
}

.search-form button {
  border: none;
  background: transparent;
  color: var(--muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.search-form button:hover,
.search-form button:focus {
  color: var(--brand);
}

main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.75rem 1.5rem 3rem;
}

.hero {
  text-align: center;
  padding: 3rem 1rem 2.25rem;
}

.hero .eyebrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.3rem 0.8rem;
  border-radius: 999px;
  background: rgba(28, 100, 242, 0.12);
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 1rem;
}

.hero h1 {
  font-size: clamp(2.3rem, 4vw, 3.2rem);
  margin-bottom: 0.75rem;
}

.hero p {
  color: var(--muted);
  margin: 0 auto;
  max-width: 650px;
}

.hero-actions {
  margin-top: 1.75rem;
  display: flex;
  justify-content: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.hero-actions.align-left {
  justify-content: flex-start;
}

.button-link,
.cta-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.75rem 1.1rem;
  border-radius: 999px;
  background: var(--brand);
  color: #fff;
  font-weight: 600;
  letter-spacing: 0.01em;
  box-shadow: 0 10px 25px rgba(255, 90, 95, 0.4);
  transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  white-space: nowrap;
}

.button-link:hover,
.button-link:focus,
.cta-button:hover,
.cta-button:focus {
  background: var(--brand-dark);
  transform: translateY(-1px);
  box-shadow: 0 18px 30px rgba(224, 72, 80, 0.35);
}

.cta-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.7rem 1.05rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-weight: 600;
  color: var(--brand);
  background: rgba(255, 90, 95, 0.08);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.cta-secondary:hover,
.cta-secondary:focus {
  background: rgba(255, 90, 95, 0.16);
  color: var(--brand-dark);
  transform: translateY(-1px);
}

.section-heading {
  text-align: center;
  margin-bottom: 1.75rem;
}

.section-heading h2 {
  margin-bottom: 0.4rem;
  font-size: clamp(1.8rem, 3vw, 2.4rem);
}

.section-heading p {
  margin: 0;
  color: var(--muted);
  max-width: 620px;
  margin-left: auto;
  margin-right: auto;
}

.grid {
  display: grid;
  gap: 1.6rem;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.card {
  background: var(--card);
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: transform 120ms ease, box-shadow 120ms ease;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.15);
}

.card img {
  width: 100%;
  height: 220px;
  object-fit: cover;
}

.card-content {
  padding: 1.15rem 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  flex: 1;
}

.card-content h3 {
  margin: 0;
  font-size: 1.1rem;
}

.card-content p {
  color: var(--muted);
  margin: 0;
  font-size: 0.95rem;
}

.card-content .button-link {
  margin-top: 0.25rem;
}

.category-hero {
  display: grid;
  gap: 2rem;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  align-items: center;
  margin-bottom: 2.5rem;
}

.category-hero p {
  color: var(--muted);
  font-size: 1.05rem;
}

.newsletter-banner {
  margin: 3rem auto 0;
  background: rgba(28, 100, 242, 0.08);
  border: 1px dashed rgba(28, 100, 242, 0.3);
  border-radius: 18px;
  padding: 1.75rem;
  text-align: center;
  max-width: 720px;
}

.newsletter-banner h3 {
  margin-top: 0;
}

.newsletter-banner p {
  color: var(--muted);
  margin-bottom: 1.1rem;
}

.value-prop {
  margin-top: 3.5rem;
}

.value-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.value-card {
  background: var(--card);
  border-radius: 18px;
  padding: 1.5rem;
  border: 1px solid var(--border);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.value-card h3 {
  margin-top: 0.75rem;
}

.value-card p {
  margin: 0;
  color: var(--muted);
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: rgba(28, 100, 242, 0.12);
  color: var(--accent);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  font-weight: 700;
  text-transform: uppercase;
}

.latest-intro {
  text-align: center;
  margin-top: 3.5rem;
}

.latest-intro p {
  max-width: 640px;
  margin: 0.5rem auto 0;
  color: var(--muted);
}

.product-page {
  display: grid;
  gap: 2rem;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  align-items: flex-start;
}

.product-page img {
  width: 100%;
  border-radius: 20px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.2);
}

.product-meta {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.product-meta h1 {
  font-size: clamp(2rem, 3vw, 2.6rem);
  margin: 0;
}

.price-callout {
  font-weight: 600;
  color: var(--brand-dark);
}

.review-callout {
  color: var(--accent);
  font-weight: 500;
}

.feature-list {
  padding-left: 1.2rem;
}

.cta-row {
  margin-top: 1.25rem;
}

.related-grid {
  margin-top: 3rem;
}

.related-grid h2 {
  text-align: center;
  margin-bottom: 1.5rem;
}

.adsense-slot {
  margin: 2rem auto;
  text-align: center;
}

.breadcrumbs {
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
  color: var(--muted);
}

.breadcrumbs a {
  color: var(--muted);
}

.search-page {
  max-width: 780px;
  margin: 0 auto;
}

.search-results {
  list-style: none;
  margin: 2rem 0 0;
  padding: 0;
  display: grid;
  gap: 1.25rem;
}

.search-result {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

.search-result h3 {
  margin-top: 0;
  margin-bottom: 0.4rem;
}

.search-result p {
  margin: 0;
  color: var(--muted);
}

.search-empty {
  text-align: center;
  color: var(--muted);
  margin-top: 2rem;
}

footer {
  border-top: 1px solid var(--border);
  margin-top: 3.5rem;
  padding: 2.25rem 1.5rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.9rem;
}

.footer-links {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.footer-links a {
  color: var(--muted);
}

.footer-links a:hover,
.footer-links a:focus {
  color: var(--brand);
}

@media (max-width: 900px) {
  nav {
    flex-direction: column;
    align-items: flex-start;
  }

  .nav-groups {
    width: 100%;
    justify-content: space-between;
  }

  .search-form {
    width: 100%;
    justify-content: space-between;
  }

  .search-form input {
    flex: 1;
  }

  .hero {
    padding: 2.5rem 1rem 2rem;
  }
}

@media (max-width: 680px) {
  .category-hero {
    grid-template-columns: 1fr;
  }

  .product-page {
    grid-template-columns: 1fr;
  }
}
"""


@dataclass
class PageContext:
    title: str
    description: str
    canonical_url: str
    body: str
    og_image: str | None = None
    structured_data: List[dict] | None = None
    extra_head: str = ""
    noindex: bool = False


class SiteGenerator:
    """Generate static HTML pages for the curated gift site."""

    def __init__(
        self,
        settings: SiteSettings,
        *,
        output_dir: Path | None = None,
    ) -> None:
        ensure_directories()
        self.settings = settings
        self.output_dir = output_dir or OUTPUT_DIR
        self.assets_dir = self.output_dir / "assets"
        self.categories_dir = self.output_dir / "categories"
        self.products_dir = self.output_dir / "products"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.categories_dir.mkdir(parents=True, exist_ok=True)
        self.products_dir.mkdir(parents=True, exist_ok=True)
        self._nav_cache: List[Category] = []
        self._category_lookup: dict[str, Category] = {}

    def build(self, categories: List[Category], products: List[Product]) -> None:
        logger.info("Generating site with %s products", len(products))
        self._write_assets()
        self.preload_navigation(categories)
        self._category_lookup = {category.slug: category for category in categories}
        products_sorted = sorted(products, key=lambda p: p.updated_at, reverse=True)
        self._write_index(categories, products_sorted[:12], products_sorted)
        self._write_latest_page(products_sorted)
        self._write_search_page(categories, products_sorted)
        for category in categories:
            category_products = [
                product
                for product in products_sorted
                if product.category_slug == category.slug
            ]
            self._write_category_page(category, category_products)
            for product in category_products:
                related = [
                    candidate
                    for candidate in category_products
                    if candidate.asin != product.asin
                ][:3]
                self._write_product_page(product, category, related)
        self._write_feed(products_sorted)
        self._write_sitemap(categories, products_sorted)

    # ------------------------------------------------------------------
    # Rendering helpers
    def _layout(self, context: PageContext) -> str:
        adsense = ""
        if self.settings.adsense_client_id:
            adsense = (
                "<script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client="
                f"{self.settings.adsense_client_id}\" crossorigin=\"anonymous\"></script>"
            )
        meta_description = html.escape(context.description)
        meta_title = html.escape(context.title)
        canonical = html.escape(context.canonical_url)
        nav_links = "".join(
            f"<a href=\"/{self._category_path(slug)}\">{html.escape(name)}</a>"
            for slug, name in self._navigation_links()
        )
        nav_action_links = ['<a href="/latest.html">Latest</a>']
        if getattr(self.settings, "newsletter_url", None):
            newsletter_url = html.escape(self.settings.newsletter_url)
            nav_action_links.append(
                f'<a class="pill-link" href="{newsletter_url}" target="_blank" rel="noopener">Newsletter</a>'
            )
        search_form = (
            "<form class=\"search-form\" action=\"/search.html\" method=\"get\" role=\"search\">"
            "<label class=\"sr-only\" for=\"nav-search\">Search curated gifts</label>"
            "<input id=\"nav-search\" type=\"search\" name=\"q\" placeholder=\"Search curated gifts...\" aria-label=\"Search curated gifts\" />"
            "<button type=\"submit\" aria-label=\"Submit search\">"
            "<svg aria-hidden=\"true\" width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"11\" cy=\"11\" r=\"7\"></circle><line x1=\"20\" y1=\"20\" x2=\"16.65\" y2=\"16.65\"></line></svg>"
            "</button>"
            "</form>"
        )
        nav_actions_html = " ".join(filter(None, [" ".join(nav_action_links), search_form]))
        keywords_meta = ""
        if getattr(self.settings, "keywords", ()):  # type: ignore[attr-defined]
            keywords = ", ".join(html.escape(keyword) for keyword in self.settings.keywords)
            keywords_meta = f'<meta name="keywords" content="{keywords}" />'
        robots_meta = (
            "<meta name=\"robots\" content=\"noindex, nofollow\" />"
            if context.noindex
            else "<meta name=\"robots\" content=\"index, follow\" />"
        )
        feed_link = (
            f'<link rel="alternate" type="application/rss+xml" title="{html.escape(self.settings.site_name)} RSS" href="/feed.xml" />'
        )
        og_image_meta = ""
        if context.og_image:
            image = html.escape(context.og_image)
            og_image_meta = (
                f'<meta property="og:image" content="{image}" />\n'
                f'    <meta name="twitter:image" content="{image}" />'
            )
        twitter_meta = '<meta name="twitter:card" content="summary_large_image" />'
        if self.settings.twitter_handle:
            handle = self.settings.twitter_handle
            if not handle.startswith("@"):
                handle = f"@{handle}"
            safe_handle = html.escape(handle)
            twitter_meta += (
                f'\n    <meta name="twitter:site" content="{safe_handle}" />\n'
                f'    <meta name="twitter:creator" content="{safe_handle}" />'
            )
        facebook_meta = ""
        if self.settings.facebook_page:
            facebook_meta = (
                f'<meta property="article:publisher" content="{html.escape(self.settings.facebook_page)}" />'
            )
        adsense_slot = ""
        if self.settings.adsense_client_id and self.settings.adsense_slot:
            adsense_slot = (
                "<div class=\"adsense-slot\">"
                f"<ins class=\"adsbygoogle\" style=\"display:block\" data-ad-client=\"{self.settings.adsense_client_id}\" "
                f"data-ad-slot=\"{self.settings.adsense_slot}\" data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>"
                "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"
                "</div>"
            )
        structured_json = ""
        if context.structured_data:
            scripts = []
            for data in context.structured_data:
                json_blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
                scripts.append(f'<script type="application/ld+json">{json_blob}</script>')
            structured_json = "\n    ".join(scripts)
        extra_head = context.extra_head or ""
        structured_block = f"\n    {structured_json}" if structured_json else ""
        extra_head_block = f"\n    {extra_head}" if extra_head else ""
        now = datetime.utcnow()
        footer_links_parts = ['<a href="/index.html">Home</a>', '<a href="/latest.html">Latest finds</a>']
        if getattr(self.settings, "newsletter_url", None):
            newsletter_url = html.escape(self.settings.newsletter_url)
            footer_links_parts.append(
                f'<a href="{newsletter_url}" target="_blank" rel="noopener">Newsletter</a>'
            )
        if getattr(self.settings, "contact_email", None):
            footer_links_parts.append(
                f'<a href="mailto:{html.escape(self.settings.contact_email)}">Contact</a>'
            )
        footer_links = ""
        if footer_links_parts:
            footer_links = f"<div class=\"footer-links\">{' '.join(footer_links_parts)}</div>"
        return f"""<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{meta_title}</title>
    <meta name=\"description\" content=\"{meta_description}\" />
    {robots_meta}
    <link rel=\"canonical\" href=\"{canonical}\" />
    {feed_link}
    <link rel=\"stylesheet\" href=\"/assets/styles.css\" />
    {adsense}
    {keywords_meta}
    <meta property=\"og:type\" content=\"website\" />
    <meta property=\"og:title\" content=\"{meta_title}\" />
    <meta property=\"og:description\" content=\"{meta_description}\" />
    <meta property=\"og:url\" content=\"{canonical}\" />
    <meta property=\"og:site_name\" content=\"{html.escape(self.settings.site_name)}\" />
    <meta property=\"og:locale\" content=\"en_US\" />
    {og_image_meta}
    {twitter_meta}
    {facebook_meta}{structured_block}{extra_head_block}
  </head>
  <body>
    <a class=\"skip-link\" href=\"#main-content\">Skip to content</a>
    <header>
      <nav aria-label=\"Primary\">
        <a href=\"/index.html\" class=\"logo\">{html.escape(self.settings.site_name)}</a>
        <div class=\"nav-groups\">
          <div class=\"nav-links\">{nav_links}</div>
          <div class=\"nav-actions\">{nav_actions_html}</div>
        </div>
      </nav>
    </header>
    <main id=\"main-content\">
      {context.body}
      {adsense_slot}
    </main>
    <footer>
      <p>&copy; {now.year} {html.escape(self.settings.site_name)}. Updated {html.escape(now.strftime('%b %d, %Y'))}.</p>
      <p>As an Amazon Associate we earn from qualifying purchases. Links may generate affiliate revenue.</p>
      {footer_links}
    </footer>
  </body>
</html>
"""

    def _write_assets(self) -> None:
        stylesheet_path = self.assets_dir / "styles.css"
        stylesheet_path.write_text(ASSETS_STYLES, encoding="utf-8")

    def _write_index(
        self,
        categories: List[Category],
        featured_products: List[Product],
        all_products: List[Product],
    ) -> None:
        cta_href = f"/{self._category_path(categories[0].slug)}" if categories else "#"
        hero = f"""
<section class=\"hero\">
  <span class=\"eyebrow\">Conversion-optimized gift discovery</span>
  <h1>{html.escape(self.settings.site_name)}</h1>
  <p>{html.escape(self.settings.description)}</p>
  <div class=\"hero-actions\">
    <a class=\"button-link\" href=\"{cta_href}\">Browse curated gems</a>
    <a class=\"cta-secondary\" href=\"/latest.html\">See what's new today</a>
  </div>
</section>
"""
        category_cards = "".join(
            self._category_card(category) for category in categories
        )
        featured_cards = "".join(
            self._product_card(product) for product in featured_products
        )
        category_section = f"""
<section>
  <div class=\"section-heading\">
    <h2>Explore by vibe</h2>
    <p>Jump into themed collections that blend persuasive copy, contextual affiliate links, and display ad slots.</p>
  </div>
  <div class=\"grid\">{category_cards}</div>
</section>
"""
        featured_section = f"""
<section class=\"latest-intro\">
  <div class=\"section-heading\">
    <h2>Latest trending gifts</h2>
    <p>Freshly ingested Amazon finds with hype-driven descriptions, perfect for daily newsletter mentions or social promos.</p>
  </div>
  <div class=\"grid\">{featured_cards}</div>
  <p><a class=\"cta-secondary\" href=\"/latest.html\">View the full trending list</a></p>
</section>
"""
        value_props = """
<section class=\"value-prop\">
  <div class=\"section-heading\">
    <h2>Why marketers love Curated Gift Radar</h2>
    <p>We do the heavy lifting so you can focus on distribution, partnerships, and profitable ad spend.</p>
  </div>
  <div class=\"value-grid\">
    <article class=\"value-card\">
      <span class=\"badge\">SEO Ready</span>
      <h3>Long-form copy that ranks</h3>
      <p>Every page ships with keyword-rich storytelling, internal links, and structured data to woo organic traffic.</p>
    </article>
    <article class=\"value-card\">
      <span class=\"badge\">Affiliate Friendly</span>
      <h3>Monetize every click</h3>
      <p>Amazon partner tags are hard-wired into each CTA so discovery instantly turns into tracked commissions.</p>
    </article>
    <article class=\"value-card\">
      <span class=\"badge\">Fresh Daily</span>
      <h3>Automations keep it relevant</h3>
      <p>Nightly refreshes ensure your catalogue reflects the latest viral finds and seasonal crowd-pleasers.</p>
    </article>
  </div>
</section>
"""
        newsletter_banner = self._newsletter_banner()
        body = f"{hero}{category_section}{featured_section}{newsletter_banner}{value_props}"
        structured_data = [
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": self.settings.site_name,
                "url": self.settings.base_url,
                "description": self.settings.description,
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": f"{self.settings.base_url.rstrip('/')}/search.html?q={{search_term_string}}",
                    "query-input": "required name=search_term_string",
                },
            },
            self._item_list_structured_data(
                "Featured gift ideas",
                [
                    (product.title, self._absolute_url(self._product_path(product)))
                    for product in featured_products
                ],
            ),
        ]
        og_image = None
        for product in featured_products:
            if product.image:
                og_image = product.image
                break
        context = PageContext(
            title=f"{self.settings.site_name} — Daily curated Amazon gift ideas",
            description=self.settings.description,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/index.html",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
        )
        self._write_page(self.output_dir / "index.html", context)

    def _write_category_page(self, category: Category, products: List[Product]) -> None:
        cards = "".join(self._product_card(product) for product in products)
        amazon_url = (
            f"https://www.amazon.com/s?k={html.escape('+'.join(category.keywords))}"
        )
        if self.settings.amazon_partner_tag:
            amazon_url = f"{amazon_url}&tag={html.escape(self.settings.amazon_partner_tag)}"
        newsletter_banner = self._newsletter_banner()
        body = f"""
<div class=\"breadcrumbs\"><a href=\"/index.html\">Home</a> &rsaquo; {html.escape(category.name)}</div>
<section class=\"category-hero\">
  <div>
    <span class=\"badge\">Category spotlight</span>
    <h1>{html.escape(category.name)}</h1>
    <p>{html.escape(category.blurb)}</p>
    <div class=\"hero-actions align-left\">
      <a class=\"cta-secondary\" href=\"/latest.html\">See the newest arrivals</a>
    </div>
  </div>
  <div>
    <a class=\"button-link\" href=\"{amazon_url}\" target=\"_blank\" rel=\"noopener sponsored\">Shop full Amazon results</a>
  </div>
</section>
<section>
  <div class=\"grid\">{cards}</div>
</section>
{newsletter_banner}
"""
        og_image = None
        for product in products:
            if product.image:
                og_image = product.image
                break
        if og_image is None:
            og_image = f"https://source.unsplash.com/1200x630/?{category.slug}"
        structured_data = [
            self._breadcrumb_structured_data(
                [
                    ("Home", self._absolute_url("index.html")),
                    (category.name, self._absolute_url(self._category_path(category.slug))),
                ]
            ),
            self._item_list_structured_data(
                f"{category.name} gift ideas",
                [
                    (product.title, self._absolute_url(self._product_path(product)))
                    for product in products
                ],
            ),
        ]
        context = PageContext(
            title=f"{category.name} — {self.settings.site_name}",
            description=category.blurb,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/{self._category_path(category.slug)}",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
        )
        path = self.categories_dir / category.slug / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(path, context)

    def _write_product_page(self, product: Product, category: Category, related: List[Product]) -> None:
        price_line = f"<p class=\"price-callout\">{html.escape(product.price)}</p>" if product.price else ""
        rating_line = (
            f"<p class=\"review-callout\">{product.rating:.1f} / 5.0 ({product.total_reviews:,} reviews)</p>"
            if product.rating and product.total_reviews
            else ""
        )
        related_section = ""
        if related:
            related_cards = "".join(self._product_card(item) for item in related)
            related_section = f"""
<section class=\"related-grid\">
  <h2>More {html.escape(category.name)} hits</h2>
  <div class=\"grid\">{related_cards}</div>
</section>
"""
        breadcrumbs_html = f"""
<div class=\"breadcrumbs\"><a href=\"/index.html\">Home</a> &rsaquo; <a href=\"/{self._category_path(category.slug)}\">{html.escape(category.name)}</a></div>
"""
        body = f"""
{breadcrumbs_html}
<div class=\"product-page\">
  <div>
    <img src=\"{html.escape(product.image or '')}\" alt=\"{html.escape(product.title)}\" loading=\"lazy\" decoding=\"async\" />
  </div>
  <div class=\"product-meta\">
    <h1>{html.escape(product.title)}</h1>
    {price_line}
    {rating_line}
    {product.blog_content or ''}
    <p class=\"cta-row\"><a class=\"cta-button\" href=\"{html.escape(product.link)}\" target=\"_blank\" rel=\"noopener sponsored\">Grab it on Amazon</a></p>
  </div>
</div>
{related_section}
"""
        structured_data = [
            self._breadcrumb_structured_data(
                [
                    ("Home", self._absolute_url("index.html")),
                    (category.name, self._absolute_url(self._category_path(category.slug))),
                    (product.title, self._absolute_url(self._product_path(product))),
                ]
            ),
            self._product_structured_data(product, category),
        ]
        context = PageContext(
            title=f"{product.title} — {category.name} gift idea",
            description=product.summary or self.settings.description,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/{self._product_path(product)}",
            body=body,
            og_image=product.image,
            structured_data=structured_data,
        )
        path = self.products_dir / product.slug / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(path, context)

    def _write_latest_page(self, products: List[Product]) -> None:
        cards = "".join(self._product_card(product) for product in products[:60])
        body = f"""
<section class=\"latest-intro\">
  <div class=\"section-heading\">
    <h1>Latest gift drops</h1>
    <p>Keep tabs on the freshest Amazon discoveries and schedule them into campaigns before competitors notice.</p>
  </div>
  <div class=\"grid\">{cards}</div>
</section>
{self._newsletter_banner()}
"""
        structured_data = [
            self._item_list_structured_data(
                "Latest gift ideas",
                [
                    (product.title, self._absolute_url(self._product_path(product)))
                    for product in products[:30]
                ],
            )
        ]
        og_image = None
        for product in products:
            if product.image:
                og_image = product.image
                break
        context = PageContext(
            title=f"Latest gift drops — {self.settings.site_name}",
            description="The newest curated Amazon gift ideas, refreshed automatically for maximum conversion potential.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/latest.html",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
        )
        self._write_page(self.output_dir / "latest.html", context)

    def _write_search_page(self, categories: List[Category], products: List[Product]) -> None:
        category_lookup = {category.slug: category.name for category in categories}
        index_entries = [
            {
                "title": product.title,
                "summary": product.summary or "",
                "url": f"/{self._product_path(product)}",
                "category": category_lookup.get(product.category_slug, ""),
            }
            for product in products
        ]
        dataset = json.dumps(index_entries, ensure_ascii=False).replace("</", "<\\/")
        body = f"""
<section class=\"search-page\">
  <h1>Search the gift radar</h1>
  <p>Filter our conversion-ready product library by keyword, category, or gift recipient.</p>
  <form id=\"search-page-form\" class=\"search-form\" action=\"/search.html\" method=\"get\" role=\"search\">
    <label class=\"sr-only\" for=\"search-query\">Search curated gifts</label>
    <input id=\"search-query\" type=\"search\" name=\"q\" placeholder=\"Type a gift, keyword, or category\" aria-label=\"Search curated gifts\" />
    <button type=\"submit\" aria-label=\"Submit search\">
      <svg aria-hidden=\"true\" width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"11\" cy=\"11\" r=\"7\"></circle><line x1=\"20\" y1=\"20\" x2=\"16.65\" y2=\"16.65\"></line></svg>
    </button>
  </form>
  <div id=\"search-feedback\" class=\"search-empty\">Start typing to reveal the latest gift ideas.</div>
  <ol id=\"search-results\" class=\"search-results\" aria-live=\"polite\"></ol>
</section>
<script>
const PRODUCT_INDEX = {dataset};
const form = document.getElementById('search-page-form');
const input = document.getElementById('search-query');
const feedback = document.getElementById('search-feedback');
const resultsList = document.getElementById('search-results');
function renderResults(query) {
  resultsList.innerHTML = '';
  if (!query) {
    feedback.textContent = 'Start typing to reveal the latest gift ideas.';
    return;
  }
  const normalized = query.toLowerCase();
  const matches = PRODUCT_INDEX.filter((item) => {
    return item.title.toLowerCase().includes(normalized) ||
      item.summary.toLowerCase().includes(normalized) ||
      (item.category && item.category.toLowerCase().includes(normalized));
  }).slice(0, 30);
  if (!matches.length) {
    feedback.textContent = 'No matching gifts yet — try a different keyword.';
    return;
  }
  feedback.textContent = `Showing ${matches.length} conversion-ready picks.`;
  const frag = document.createDocumentFragment();
  for (const match of matches) {
    const li = document.createElement('li');
    li.className = 'search-result';
    const heading = document.createElement('h3');
    const link = document.createElement('a');
    link.href = match.url;
    link.textContent = match.title;
    heading.appendChild(link);
    li.appendChild(heading);
    const summary = document.createElement('p');
    summary.textContent = match.summary || 'Tap through to read the full hype breakdown.';
    li.appendChild(summary);
    if (match.category) {
      const badge = document.createElement('p');
      badge.className = 'badge';
      badge.textContent = match.category;
      li.appendChild(badge);
    }
    frag.appendChild(li);
  }
  resultsList.appendChild(frag);
}
const params = new URLSearchParams(window.location.search);
const initial = (params.get('q') || '').trim();
input.value = initial;
renderResults(initial);
form.addEventListener('submit', (event) => {
  event.preventDefault();
  const value = input.value.trim();
  const url = new URL(window.location.href);
  if (value) {
    url.searchParams.set('q', value);
  } else {
    url.searchParams.delete('q');
  }
  window.history.replaceState(null, '', url.toString());
  renderResults(value);
});
input.addEventListener('input', (event) => {
  renderResults(event.target.value.trim());
});
</script>
"""
        structured_data = [
            {
                "@context": "https://schema.org",
                "@type": "SearchResultsPage",
                "name": f"Search {self.settings.site_name}",
                "description": "Search curated Amazon gift ideas across every category.",
                "url": f"{self.settings.base_url.rstrip('/')}/search.html",
            }
        ]
        context = PageContext(
            title=f"Search gifts — {self.settings.site_name}",
            description="Search curated Amazon gift ideas instantly.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/search.html",
            body=body,
            structured_data=structured_data,
            noindex=True,
        )
        self._write_page(self.output_dir / "search.html", context)

    def _write_feed(self, products: List[Product]) -> None:
        items = "".join(
            f"""
    <item>
      <title>{html.escape(product.title)}</title>
      <link>{html.escape(self._absolute_url(self._product_path(product)))}</link>
      <guid>{html.escape(product.asin)}</guid>
      <description>{html.escape(product.summary or '')}</description>
      <pubDate>{html.escape(product.updated_at)}</pubDate>
    </item>
"""
            for product in products[:30]
        )
        rss = f"""
<?xml version=\"1.0\" encoding=\"UTF-8\" ?>
<rss version=\"2.0\">
  <channel>
    <title>{html.escape(self.settings.site_name)}</title>
    <link>{html.escape(self.settings.base_url)}</link>
    <description>{html.escape(self.settings.description)}</description>
    {items}
  </channel>
</rss>
"""
        (self.output_dir / "feed.xml").write_text(rss.strip(), encoding="utf-8")

    def _write_sitemap(self, categories: List[Category], products: List[Product]) -> None:
        urls = [self._absolute_url("index.html"), self._absolute_url("latest.html")]
        urls.extend(self._absolute_url(self._category_path(category.slug)) for category in categories)
        urls.extend(self._absolute_url(self._product_path(product)) for product in products)
        url_tags = "".join(
            f"<url><loc>{html.escape(url)}</loc></url>" for url in urls
        )
        xml = f"""
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
{url_tags}
</urlset>
"""
        (self.output_dir / "sitemap.xml").write_text(xml.strip(), encoding="utf-8")

    def _newsletter_banner(self) -> str:
        if not getattr(self.settings, "newsletter_url", None):
            return ""
        url = html.escape(self.settings.newsletter_url)
        return f"""
<section class=\"newsletter-banner\">
  <h3>Steal our weekly bestseller intel</h3>
  <p>Subscribe to receive high-performing gift drops, category insights, and seasonal launch reminders.</p>
  <a class=\"button-link\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Join the newsletter</a>
</section>
"""

    def _item_list_structured_data(self, name: str, items: List[tuple[str, str]]) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": name,
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": title,
                    "url": url,
                }
                for index, (title, url) in enumerate(items)
            ],
        }

    def _breadcrumb_structured_data(self, crumbs: List[tuple[str, str]]) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": name,
                    "item": url,
                }
                for index, (name, url) in enumerate(crumbs)
            ],
        }

    def _product_structured_data(self, product: Product, category: Category) -> dict:
        data: dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "sku": product.asin,
            "url": self._absolute_url(self._product_path(product)),
            "description": product.summary or self.settings.description,
            "category": category.name,
        }
        if product.image:
            data["image"] = [product.image]
        price_value, currency = self._extract_price_components(product.price)
        if price_value:
            data["offers"] = {
                "@type": "Offer",
                "price": price_value,
                "priceCurrency": currency or "USD",
                "availability": "https://schema.org/InStock",
                "url": product.link,
            }
        if product.rating and product.total_reviews:
            data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": f"{product.rating:.1f}",
                "reviewCount": str(product.total_reviews),
            }
        return data

    @staticmethod
    def _extract_price_components(price: str | None) -> tuple[str | None, str | None]:
        if not price:
            return None, None
        currency_map = {
            "C$": "CAD",
            "A$": "AUD",
            "£": "GBP",
            "€": "EUR",
            "¥": "JPY",
            "$": "USD",
        }
        currency = None
        for symbol, code in currency_map.items():
            if symbol in price:
                currency = code
                break
        numeric_match = re.search(r"(\d+[\d.,]*)", price)
        if not numeric_match:
            return None, currency
        numeric = numeric_match.group(1).replace(",", ".")
        if numeric.count(".") > 1:
            head, *tail = numeric.split(".")
            numeric = head + "." + "".join(tail)
        return numeric, currency

    def _product_card(self, product: Product) -> str:
        description = html.escape(product.summary or "Discover why we love this find.")
        image = html.escape(product.image or "")
        return f"""
<article class=\"card\">
  <a href=\"/{self._product_path(product)}\"><img src=\"{image}\" alt=\"{html.escape(product.title)}\" loading=\"lazy\" decoding=\"async\" /></a>
  <div class=\"card-content\">
    <h3><a href=\"/{self._product_path(product)}\">{html.escape(product.title)}</a></h3>
    <p>{description}</p>
    <div><a class=\"button-link\" href=\"/{self._product_path(product)}\">Read the hype</a></div>
  </div>
</article>
"""

    def _category_card(self, category: Category) -> str:
        return f"""
<article class=\"card\">
  <a href=\"/{self._category_path(category.slug)}\"><img src=\"https://source.unsplash.com/600x400/?{html.escape(category.slug)}\" alt=\"{html.escape(category.name)}\" loading=\"lazy\" decoding=\"async\" /></a>
  <div class=\"card-content\">
    <h3><a href=\"/{self._category_path(category.slug)}\">{html.escape(category.name)}</a></h3>
    <p>{html.escape(category.blurb)}</p>
  </div>
</article>
"""

    def _write_page(self, path: Path, context: PageContext) -> None:
        logger.debug("Writing page %s", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        html_content = self._layout(context)
        path.write_text(html_content, encoding="utf-8")

    def _category_path(self, slug: str) -> str:
        return f"categories/{slug}/index.html"

    def _product_path(self, product: Product) -> str:
        return f"products/{product.slug}/index.html"

    def _absolute_url(self, relative: str) -> str:
        base = self.settings.base_url.rstrip("/")
        relative = relative.lstrip("/")
        return f"{base}/{relative}"

    def _navigation_links(self) -> Iterable[tuple[str, str]]:
        # keep navigation limited to six categories to avoid crowding
        return [
            (category.slug, category.name)
            for category in self._nav_categories[:6]
        ]

    @property
    def _nav_categories(self) -> List[Category]:
        # store categories on generator for navigation reuse
        if not hasattr(self, "_nav_cache"):
            self._nav_cache: List[Category] = []
        return self._nav_cache

    @_nav_categories.setter
    def _nav_categories(self, value: List[Category]) -> None:
        self._nav_cache = value

    def preload_navigation(self, categories: List[Category]) -> None:
        self._nav_categories = categories
        logger.debug("Navigation preload set for %s categories", len(self._nav_categories))
