"""Static site generator responsible for producing the HTML pages."""
from __future__ import annotations

import html
import json
import logging
import re
from urllib.parse import quote_plus
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

html {
  scroll-behavior: smooth;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  background-image: radial-gradient(120% 120% at 50% 0%, rgba(255, 90, 95, 0.06) 0%, rgba(28, 100, 242, 0.03) 42%, transparent 100%);
  color: var(--text);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
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

:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

a:focus-visible,
button:focus-visible,
.button-link:focus-visible,
.cta-button:focus-visible,
.cta-secondary:focus-visible,
.pill-link:focus-visible {
  color: var(--brand-dark);
}

button,
input {
  font: inherit;
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

.surprise-link {
  background: rgba(28, 100, 242, 0.14);
  color: var(--accent);
}

.surprise-link:hover,
.surprise-link:focus {
  background: rgba(28, 100, 242, 0.2);
  color: var(--accent);
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

.card-media {
  position: relative;
  display: block;
  overflow: hidden;
  border-bottom: 1px solid var(--border);
}

.card-media img {
  width: 100%;
  height: 220px;
  object-fit: cover;
  transition: transform 160ms ease;
}

.card:hover .card-media img {
  transform: scale(1.03);
}

.card-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.3);
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

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  font-size: 0.9rem;
  color: var(--muted);
  align-items: center;
}

.card-price {
  font-weight: 600;
  color: var(--text);
  background: rgba(28, 100, 242, 0.12);
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
}

.card-rating {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(255, 90, 95, 0.15);
  color: var(--brand-dark);
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
}

.card-rating svg {
  width: 14px;
  height: 14px;
}

.card-rating-count {
  color: var(--muted);
  margin-left: 0.15rem;
}

.card-actions {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.card-cta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.card-cta-row .button-link,
.card-cta-row .cta-secondary {
  flex: 1 1 140px;
  justify-content: center;
}

.card-share {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.85rem;
  color: var(--muted);
  flex-wrap: wrap;
}

.card-share span {
  font-weight: 600;
  color: var(--text);
}

.share-link {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.06);
  color: var(--muted);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.share-link:hover,
.share-link:focus {
  background: var(--brand);
  color: #fff;
  transform: translateY(-1px);
}

.share-link svg {
  width: 16px;
  height: 16px;
}

@media (min-width: 640px) {
  .card-cta-row .button-link,
  .card-cta-row .cta-secondary {
    flex: 0 1 auto;
  }
}

@media (max-width: 600px) {
  .card-media img {
    height: 200px;
  }
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

.cta-stack {
  margin-top: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.cta-stack .cta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.cta-stack .cta-row .cta-button,
.cta-stack .cta-row .cta-secondary {
  flex: 1 1 180px;
  justify-content: center;
}

.share-links {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.share-links.share-inline {
  flex-wrap: wrap;
}

.share-links span {
  font-weight: 600;
  color: var(--muted);
}

.share-links .share-link {
  width: 36px;
  height: 36px;
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

.search-page-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.filter-toolbar {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  background: rgba(15, 23, 42, 0.04);
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.05);
  padding: 1.25rem 1.5rem;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 0;
}

.filter-group legend {
  font-size: 0.8rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}

.filter-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.filter-chip {
  position: relative;
  display: inline-flex;
}

.filter-chip input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.filter-chip span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: #fff;
  color: var(--muted);
  font-weight: 500;
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

.filter-chip input:checked + span {
  background: rgba(255, 90, 95, 0.16);
  border-color: var(--brand);
  color: var(--brand-dark);
  transform: translateY(-1px);
}

.filter-summary {
  font-size: 0.85rem;
  color: var(--muted);
}

.filter-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.filter-clear {
  background: none;
  border: none;
  color: var(--brand);
  font-weight: 600;
  cursor: pointer;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  transition: background 0.2s ease, color 0.2s ease;
}

.filter-clear:hover,
.filter-clear:focus {
  color: var(--brand-dark);
  background: rgba(255, 90, 95, 0.12);
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

.search-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.result-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.result-price {
  background: rgba(28, 100, 242, 0.12);
  color: var(--accent);
}

.result-category {
  background: rgba(255, 90, 95, 0.14);
  color: var(--brand-dark);
}

.result-recipient {
  background: rgba(15, 23, 42, 0.06);
  color: var(--muted);
}

.search-empty {
  text-align: center;
  color: var(--muted);
  margin-top: 2rem;
}

.random-redirect {
  min-height: 50vh;
  display: grid;
  place-content: center;
  text-align: center;
  gap: 1rem;
}

.random-redirect p {
  color: var(--muted);
  margin: 0;
}

.random-redirect a {
  color: var(--brand);
  font-weight: 600;
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

  .nav-actions {
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

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }

  .card:hover,
  .button-link:hover,
  .cta-button:hover,
  .cta-secondary:hover,
  .pill-link:hover {
    transform: none !important;
    box-shadow: none !important;
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
        self._all_products: List[Product] = []

    def build(self, categories: List[Category], products: List[Product]) -> None:
        logger.info("Generating site with %s products", len(products))
        self._write_assets()
        self.preload_navigation(categories)
        self._category_lookup = {category.slug: category for category in categories}
        products_sorted = sorted(products, key=lambda p: p.updated_at, reverse=True)
        self._all_products = products_sorted
        self._write_index(categories, products_sorted[:12], products_sorted)
        self._write_latest_page(products_sorted)
        self._write_search_page(categories, products_sorted)
        self._write_random_page(products_sorted)
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
        nav_action_links = [
            '<a href="/latest.html">Latest</a>',
            '<a class="pill-link surprise-link" href="/random.html">Surprise me</a>',
        ]
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
        merchant_links = self._merchant_links(product)
        cta_buttons = ""
        if merchant_links:
            button_parts = []
            for index, link in enumerate(merchant_links):
                url = html.escape(link["url"])
                label = html.escape(link.get("label", "Shop"))
                rel = html.escape(link.get("rel", "noopener"))
                classes = "cta-button" if index == 0 else "cta-secondary"
                button_parts.append(
                    f'<a class="{classes}" href="{url}" target="_blank" rel="{rel}">{label}</a>'
                )
            cta_buttons = "".join(button_parts)
        share_markup = self._share_links_markup(product)
        share_block = (
            f'<div class="share-links share-inline"><span>Share</span>{share_markup}</div>'
            if share_markup
            else ""
        )
        cta_sections = []
        if cta_buttons:
            cta_sections.append(f'<div class="cta-row">{cta_buttons}</div>')
        if share_block:
            cta_sections.append(share_block)
        cta_block = (
            f'<div class="cta-stack">{"".join(cta_sections)}</div>'
            if cta_sections
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
    {cta_block}
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
        category_map = {category.slug: category for category in categories}
        price_filters = [
            ("any", "Any price"),
            ("under-25", "Under $25"),
            ("25-50", "$25 – $50"),
            ("50-100", "$50 – $100"),
            ("over-100", "$100+"),
        ]
        recipient_counts: dict[str, int] = {}
        recipient_labels: dict[str, str] = {}
        index_entries: list[dict[str, object]] = []
        for product in products:
            category_name = category_lookup.get(product.category_slug, "")
            category_obj = category_map.get(product.category_slug)
            price_bucket_slug, price_bucket_label = self._price_bucket(product.price)
            recipients = self._recipient_tags(category_obj)
            unique_recipients: list[str] = []
            seen_recipients: set[str] = set()
            for label in recipients:
                if label not in seen_recipients:
                    unique_recipients.append(label)
                    seen_recipients.add(label)
            recipient_slugs: list[str] = []
            for label in unique_recipients:
                slug = self._filter_slug(label)
                recipient_slugs.append(slug)
                recipient_labels.setdefault(slug, label)
                recipient_counts[slug] = recipient_counts.get(slug, 0) + 1
            keywords = [keyword.strip() for keyword in (product.keywords or []) if keyword and keyword.strip()]
            keyword_blob = " ".join(keyword.lower() for keyword in keywords)
            index_entries.append(
                {
                    "title": product.title,
                    "summary": product.summary or "",
                    "url": f"/{self._product_path(product)}",
                    "category": category_name,
                    "price": product.price or "",
                    "priceBucket": price_bucket_slug or "any",
                    "priceLabel": price_bucket_label or "",
                    "recipientTags": unique_recipients,
                    "recipientSlugs": recipient_slugs,
                    "keywords": keywords,
                    "keywordBlob": keyword_blob,
                }
            )
        dataset = json.dumps(index_entries, ensure_ascii=False).replace("</", "<\/")
        price_filter_controls = "".join(
            f'<label class="filter-chip"><input type="radio" name="price-filter" value="{value}"'
            f"{' checked' if value == 'any' else ''} /><span>{html.escape(label)}</span></label>"
            for value, label in price_filters
        )
        sorted_recipients = [
            item
            for item in sorted(
                recipient_labels.items(),
                key=lambda entry: (-recipient_counts.get(entry[0], 0), entry[1].lower()),
            )
            if recipient_counts.get(item[0], 0) > 0
        ]
        top_recipient_filters = sorted_recipients[:8]
        recipient_controls = "".join(
            f'<label class="filter-chip"><input type="checkbox" name="recipient-filter" value="{slug}" /><span>{html.escape(label)}</span></label>'
            for slug, label in top_recipient_filters
        )
        recipient_fieldset = (
            f'<fieldset class="filter-group"><legend>Recipients</legend><div class="filter-pills">{recipient_controls}</div></fieldset>'
            if recipient_controls
            else ""
        )
        price_labels = {value: label for value, label in price_filters}
        price_labels_json = json.dumps(price_labels, ensure_ascii=False).replace("</", "<\/")
        recipient_labels_json = json.dumps(recipient_labels, ensure_ascii=False).replace("</", "<\/")
        body = f"""
<section class="search-page">
  <h1>Search the gift radar</h1>
  <p>Pinpoint curated gifts by combining keyword search with quick filters for price and recipient vibes.</p>
  <form id="search-page-form" class="search-page-form" action="/search.html" method="get" role="search">
    <div class="search-form">
      <label class="sr-only" for="search-query">Search curated gifts</label>
      <input id="search-query" type="search" name="q" placeholder="Type a gift, keyword, or category" aria-label="Search curated gifts" />
      <button type="submit" aria-label="Submit search">
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><line x1="20" y1="20" x2="16.65" y2="16.65"></line></svg>
      </button>
    </div>
    <div class="filter-toolbar">
      <p class="filter-summary">Layer filters to surface the exact gift energy you're chasing.</p>
      <fieldset class="filter-group">
        <legend>Price</legend>
        <div class="filter-pills">{price_filter_controls}</div>
      </fieldset>
      {recipient_fieldset}
      <div class="filter-actions">
        <span class="filter-summary" id="active-filter-summary">No quick filters applied.</span>
        <button type="button" id="clear-filters" class="filter-clear">Clear filters</button>
      </div>
    </div>
  </form>
  <div id="search-feedback" class="search-empty" role="status" aria-live="polite" aria-atomic="true">Use quick filters or start typing to reveal the latest gift ideas.</div>
  <ol id="search-results" class="search-results" aria-live="polite"></ol>
</section>
<script>
const PRODUCT_INDEX = {dataset};
const PRICE_LABELS = {price_labels_json};
const RECIPIENT_LABELS = {recipient_labels_json};
const form = document.getElementById('search-page-form');
const input = document.getElementById('search-query');
const feedback = document.getElementById('search-feedback');
const resultsList = document.getElementById('search-results');
const filterSummary = document.getElementById('active-filter-summary');
const priceInputs = Array.from(document.querySelectorAll('input[name="price-filter"]'));
const recipientInputs = Array.from(document.querySelectorAll('input[name="recipient-filter"]'));
const clearButton = document.getElementById('clear-filters');

function activePrice() {
  const checked = priceInputs.find((input) => input.checked);
  return checked ? checked.value : 'any';
}

function activeRecipients() {
  return recipientInputs.filter((input) => input.checked).map((input) => input.value);
}

function updateFilterSummary(priceValue, recipientValues) {
  if (!filterSummary) return;
  const parts = [];
  if (priceValue !== 'any' && PRICE_LABELS[priceValue]) {
    parts.push(PRICE_LABELS[priceValue]);
  }
  const labels = recipientValues
    .map((value) => RECIPIENT_LABELS[value] || '')
    .filter((label) => label);
  if (labels.length) {
    parts.push(labels.join(', '));
  }
  filterSummary.textContent = parts.length
    ? `Filters active: ${parts.join(' • ')}`
    : 'No quick filters applied.';
}

let currentQuery = '';

function updateUrl() {
  const url = new URL(window.location.href);
  if (currentQuery) {
    url.searchParams.set('q', currentQuery);
  } else {
    url.searchParams.delete('q');
  }
  const priceValue = activePrice();
  if (priceValue && priceValue !== 'any') {
    url.searchParams.set('price', priceValue);
  } else {
    url.searchParams.delete('price');
  }
  url.searchParams.delete('recipient');
  for (const value of activeRecipients()) {
    url.searchParams.append('recipient', value);
  }
  window.history.replaceState(null, '', url.toString());
}

function renderResults(query) {
  currentQuery = query;
  resultsList.innerHTML = '';
  const priceValue = activePrice();
  const recipientValues = activeRecipients();
  const normalized = query.toLowerCase();
  const hasQuery = normalized.length > 0;
  const hasFilters = priceValue !== 'any' || recipientValues.length > 0;
  if (!hasQuery && !hasFilters) {
    feedback.textContent = 'Use quick filters or start typing to reveal the latest gift ideas.';
    updateFilterSummary(priceValue, recipientValues);
    return;
  }
  const matches = PRODUCT_INDEX.filter((item) => {
    const matchesQuery = !normalized ||
      item.title.toLowerCase().includes(normalized) ||
      item.summary.toLowerCase().includes(normalized) ||
      (item.category && item.category.toLowerCase().includes(normalized)) ||
      (item.keywordBlob && item.keywordBlob.includes(normalized));
    const matchesPrice = priceValue === 'any' || item.priceBucket === priceValue;
    const matchesRecipients = !recipientValues.length || recipientValues.every((value) => item.recipientSlugs.includes(value));
    return matchesQuery && matchesPrice && matchesRecipients;
  }).slice(0, 30);
  if (!matches.length) {
    feedback.textContent = 'No matching gifts yet — try another keyword or adjust the filters.';
    updateFilterSummary(priceValue, recipientValues);
    return;
  }
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
    const meta = document.createElement('div');
    meta.className = 'search-result-meta';
    if (match.price) {
      const price = document.createElement('span');
      price.className = 'result-badge result-price';
      price.textContent = match.price;
      meta.appendChild(price);
    } else if (match.priceLabel) {
      const bucket = document.createElement('span');
      bucket.className = 'result-badge result-price';
      bucket.textContent = match.priceLabel;
      meta.appendChild(bucket);
    }
    if (match.category) {
      const categoryBadge = document.createElement('span');
      categoryBadge.className = 'result-badge result-category';
      categoryBadge.textContent = match.category;
      meta.appendChild(categoryBadge);
    }
    if (Array.isArray(match.recipientTags)) {
      for (const tag of match.recipientTags.slice(0, 3)) {
        const tagEl = document.createElement('span');
        tagEl.className = 'result-badge result-recipient';
        tagEl.textContent = tag;
        meta.appendChild(tagEl);
      }
    }
    if (meta.childElementCount) {
      li.appendChild(meta);
    }
    frag.appendChild(li);
  }
  resultsList.appendChild(frag);
  const priceLabel = priceValue !== 'any' ? PRICE_LABELS[priceValue] : '';
  const recipientLabelsActive = recipientValues
    .map((value) => (RECIPIENT_LABELS[value] || '').replace(/^For\s+/i, ''))
    .filter((label) => label);
  let suffix = '';
  if (priceLabel) {
    suffix += ` in ${priceLabel}`;
  }
  if (recipientLabelsActive.length) {
    suffix += ` for ${recipientLabelsActive.join(', ')}`;
  }
  feedback.textContent = `Showing ${matches.length} conversion-ready picks${suffix}.`;
  updateFilterSummary(priceValue, recipientValues);
}

const params = new URLSearchParams(window.location.search);
const initialQuery = (params.get('q') || '').trim();
const initialPrice = params.get('price') || 'any';
const initialRecipients = params.getAll('recipient');

const priceDefault = priceInputs.find((input) => input.value === initialPrice);
if (priceDefault) {
  priceDefault.checked = true;
} else if (priceInputs.length) {
  priceInputs[0].checked = true;
}

const recipientPreset = new Set(initialRecipients);
for (const checkbox of recipientInputs) {
  checkbox.checked = recipientPreset.has(checkbox.value);
}

input.value = initialQuery;
renderResults(initialQuery);

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const value = input.value.trim();
  renderResults(value);
  updateUrl();
});

input.addEventListener('input', (event) => {
  const value = event.target.value.trim();
  renderResults(value);
  updateUrl();
});

for (const radio of priceInputs) {
  radio.addEventListener('change', () => {
    renderResults(currentQuery);
    updateUrl();
  });
}

for (const checkbox of recipientInputs) {
  checkbox.addEventListener('change', () => {
    renderResults(currentQuery);
    updateUrl();
  });
}

if (clearButton) {
  clearButton.addEventListener('click', () => {
    input.value = '';
    if (priceInputs.length) {
      priceInputs[0].checked = true;
    }
    for (const checkbox of recipientInputs) {
      checkbox.checked = false;
    }
    renderResults('');
    updateUrl();
    input.focus();
  });
}
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

    def _write_random_page(self, products: List[Product]) -> None:
        if not products:
            return
        product_paths = [f"/{self._product_path(product)}" for product in products]
        dataset = json.dumps(product_paths, ensure_ascii=False).replace("</", "<\\/")
        fallback = html.escape(product_paths[0])
        body = f"""
<section class=\"random-redirect\">
  <h1>Loading a surprise pick…</h1>
  <p>We’re spinning up a random product to keep your inspiration flowing.</p>
  <p><a href=\"{fallback}\">Take me there now</a> if you don’t want to wait.</p>
  <noscript>Enable JavaScript for the instant redirect or browse the <a href=\"/latest.html\">latest drops</a>.</noscript>
</section>
<script>
const PRODUCT_PATHS = {dataset};
if (PRODUCT_PATHS.length) {
  const index = Math.floor(Math.random() * PRODUCT_PATHS.length);
  const target = PRODUCT_PATHS[index] || PRODUCT_PATHS[0];
  if (target) {
    window.location.replace(target);
  }
}
</script>
"""
        context = PageContext(
            title=f"Surprise me — {self.settings.site_name}",
            description="Jump to a random trending gift idea for quick inspiration.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/random.html",
            body=body,
            noindex=True,
        )
        self._write_page(self.output_dir / "random.html", context)

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
        offers: List[dict[str, object]] = []
        if product.link:
            offer: dict[str, object] = {"@type": "Offer", "url": product.link}
            if price_value:
                offer.update(
                    {
                        "price": price_value,
                        "priceCurrency": currency or "USD",
                        "availability": "https://schema.org/InStock",
                    }
                )
            offers.append(offer)
        for entry in product.alternate_links:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            if not url:
                continue
            label = entry.get("label")
            offer = {"@type": "Offer", "url": url}
            if price_value:
                offer.update(
                    {
                        "price": price_value,
                        "priceCurrency": currency or "USD",
                        "availability": "https://schema.org/InStock",
                    }
                )
            if label:
                offer["seller"] = {"@type": "Organization", "name": label}
            offers.append(offer)
        if offers:
            data["offers"] = offers[0] if len(offers) == 1 else offers
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

    def _price_bucket(self, price: str | None) -> tuple[str | None, str | None]:
        if not price:
            return None, None
        value, _currency = self._extract_price_components(price)
        if not value:
            return None, None
        try:
            amount = float(value)
        except ValueError:
            return None, None
        if amount < 25:
            return "under-25", "Under $25"
        if amount < 50:
            return "25-50", "$25 – $50"
        if amount < 100:
            return "50-100", "$50 – $100"
        return "over-100", "$100+"

    def _filter_slug(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return normalized or "general"

    def _format_recipient_tag(self, raw: str | None) -> str | None:
        candidate = (raw or "").strip()
        if not candidate:
            return None
        lower = candidate.lower()
        occasion_map = {
            "gift exchange": "Gift Exchange",
            "white elephant": "White Elephant",
            "stocking stuffer": "Stocking Stuffer",
            "stocking stuffers": "Stocking Stuffers",
        }
        if lower in occasion_map:
            return occasion_map[lower]
        cleaned = re.sub(r"\bgift ideas?\b", "", candidate, flags=re.I)
        cleaned = re.sub(r"\bgifts?\b", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\bfor\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"[-_/]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            cleaned = candidate.strip()
        base_lower = cleaned.lower()
        if base_lower.startswith("for "):
            cleaned = cleaned[4:].strip()
            base_lower = cleaned.lower()
        direct_terms = {
            "men",
            "man",
            "women",
            "woman",
            "him",
            "her",
            "mom",
            "moms",
            "dad",
            "dads",
            "parents",
            "kids",
            "kid",
            "teen",
            "teens",
            "boyfriend",
            "girlfriend",
            "husband",
            "wife",
            "brother",
            "sister",
            "grandma",
            "grandpa",
            "family",
            "friend",
            "friends",
            "coworker",
            "coworkers",
            "boss",
            "teacher",
            "baby",
        }
        if base_lower in direct_terms:
            return f"For {cleaned.title()}"
        if "him" in base_lower:
            return f"For {cleaned.title()}"
        if "her" in base_lower:
            return f"For {cleaned.title()}"
        if base_lower.endswith("s") and base_lower[:-1] in direct_terms:
            return f"For {cleaned.title()}"
        return None

    def _recipient_tags(self, category: Category | None) -> List[str]:
        if not category:
            return []
        tags: List[str] = []
        for keyword in category.keywords:
            formatted = self._format_recipient_tag(keyword)
            if formatted:
                tags.append(formatted)
        name_tag = self._format_recipient_tag(category.name)
        if name_tag:
            tags.append(name_tag)
        ordered: List[str] = []
        seen: set[str] = set()
        for tag in tags:
            if tag not in seen:
                ordered.append(tag)
                seen.add(tag)
        return ordered

    def _merchant_links(self, product: Product) -> List[dict[str, str]]:
        links: List[dict[str, str]] = []
        if product.link:
            links.append(
                {
                    "label": "Amazon",
                    "url": product.link,
                    "rel": "noopener sponsored",
                }
            )
        for entry in product.alternate_links:
            url = entry.get("url") if isinstance(entry, dict) else None
            if not url:
                continue
            label = entry.get("label") if isinstance(entry, dict) else None
            rel = entry.get("rel") if isinstance(entry, dict) else None
            links.append(
                {
                    "label": label or "Shop",
                    "url": url,
                    "rel": rel or "noopener",
                }
            )
        unique_links: List[dict[str, str]] = []
        seen_urls: set[str] = set()
        for link in links:
            if link["url"] in seen_urls:
                continue
            seen_urls.add(link["url"])
            unique_links.append(link)
        return unique_links

    def _share_links_markup(self, product: Product) -> str:
        share_target = product.share_url or self._absolute_url(self._product_path(product))
        encoded_url = quote_plus(share_target)
        encoded_title = quote_plus(product.title)
        twitter_icon = (
            '<svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor">'
            '<path d="M23 3a10.9 10.9 0 01-3.14 1.53A4.48 4.48 0 0016.11 3c-2.63 0-4.77 2.14-4.77 4.77 0 .37.04.74.12 1.09A12.94 12.94 0 013 4.11a4.77 4.77 0 001.48 6.36 4.41 4.41 0 01-2.16-.6v.06c0 2.28 1.63 4.18 3.8 4.62a4.5 4.5 0 01-2.14.08 4.79 4.79 0 004.47 3.32A9 9 0 012 19.54 12.73 12.73 0 008.29 21c8.3 0 12.84-6.88 12.84-12.84 0-.2 0-.39-.01-.58A9.18 9.18 0 0023 3z"/></svg>'
        )
        pinterest_icon = (
            '<svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor">'
            '<path d="M12.04 2C7.5 2 4 5.37 4 9.85c0 3.09 1.8 4.84 2.84 4.84.44 0 .7-1.21.7-1.54 0-.4-1.02-1.24-1.02-2.89 0-3.42 2.62-5.81 6.07-5.81 2.95 0 5.08 1.84 5.08 4.86 0 3.42-1.73 5.79-3.98 5.79-1.25 0-2.18-1.03-1.88-2.29.36-1.51 1.06-3.15 1.06-4.25 0-.98-.53-1.8-1.62-1.8-1.28 0-2.3 1.32-2.3 3.09 0 1.13.38 1.89.38 1.89s-1.31 5.54-1.55 6.52c-.46 1.94-.07 4.31-.04 4.55.02.15.22.19.31.07.13-.17 1.79-2.22 2.36-4.27.16-.59.91-3.62.91-3.62.45.86 1.76 1.61 3.15 1.61 4.15 0 6.96-3.48 6.96-8.17C20.02 5.17 16.9 2 12.04 2z"/></svg>'
        )
        twitter_url = f"https://twitter.com/intent/tweet?text={encoded_title}&url={encoded_url}"
        pinterest_url = (
            f"https://www.pinterest.com/pin/create/button/?url={encoded_url}&description={encoded_title}"
        )
        if product.image:
            pinterest_url += f"&media={quote_plus(product.image)}"
        links = [
            ("Twitter", twitter_url, twitter_icon),
            ("Pinterest", pinterest_url, pinterest_icon),
        ]
        rendered: List[str] = []
        for label, href, icon in links:
            rendered.append(
                f'<a class="share-link" href="{html.escape(href)}" target="_blank" rel="noopener" aria-label="Share on {label}">{icon}</a>'
            )
        return "".join(rendered)

    def _product_card(self, product: Product) -> str:
        description = html.escape(product.summary or "Discover why we love this find.")
        image = html.escape(product.image or "")
        category_badge = ""
        category = self._category_lookup.get(product.category_slug)
        if category:
            category_badge = f'<span class="card-badge">{html.escape(category.name)}</span>'
        price_html = (
            f'<span class="card-price">{html.escape(product.price)}</span>'
            if product.price
            else ""
        )
        rating_html = ""
        if product.rating and product.total_reviews:
            rating_html = (
                f'<span class="card-rating" aria-label="{product.rating:.1f} out of 5 stars based on {product.total_reviews:,} reviews">'
                '<svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>'
                f'{product.rating:.1f}<span class="card-rating-count">({product.total_reviews:,})</span></span>'
            )
        meta_parts = [part for part in (price_html, rating_html) if part]
        meta_html = (
            f'<div class="card-meta">{"".join(meta_parts)}</div>'
            if meta_parts
            else ""
        )
        detail_path = f"/{self._product_path(product)}"
        merchant_links = self._merchant_links(product)
        outbound_buttons = []
        for link in merchant_links[:2]:
            url = html.escape(link["url"])
            label = html.escape(link.get("label", "Shop"))
            rel = html.escape(link.get("rel", "noopener"))
            outbound_buttons.append(
                f'<a class="cta-secondary" href="{url}" target="_blank" rel="{rel}">{label}</a>'
            )
        cta_row = "".join(
            [f'<a class="button-link" href="{html.escape(detail_path)}">Read the hype</a>']
            + outbound_buttons
        )
        share_links = self._share_links_markup(product)
        share_html = (
            f'<div class="card-share"><span>Share</span>{share_links}</div>'
            if share_links
            else ""
        )
        return f"""
<article class="card">
  <a class="card-media" href="{html.escape(detail_path)}">
    <img src="{image}" alt="{html.escape(product.title)}" loading="lazy" decoding="async" />
    {category_badge}
  </a>
  <div class="card-content">
    <h3><a href="{html.escape(detail_path)}">{html.escape(product.title)}</a></h3>
    <p>{description}</p>
    {meta_html}
    <div class="card-actions">
      <div class="card-cta-row">{cta_row}</div>
      {share_html}
    </div>
  </div>
</article>
"""
    def _category_card(self, category: Category) -> str:
        return f"""
<article class=\"card\">
  <a class=\"card-media\" href=\"/{self._category_path(category.slug)}\">
    <img src=\"https://source.unsplash.com/600x400/?{html.escape(category.slug)}\" alt=\"{html.escape(category.name)}\" loading=\"lazy\" decoding=\"async\" />
  </a>
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
