"""Static site generator responsible for producing the HTML pages."""
from __future__ import annotations

import html
import logging
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
  background: var(--bg);
  color: var(--text);
}

a {
  color: var(--brand);
  text-decoration: none;
}

a:hover {
  color: var(--brand-dark);
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
  padding: 1rem 1.5rem;
}

.logo {
  font-weight: 700;
  font-size: 1.2rem;
}

.nav-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.95rem;
}

main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem;
}

.hero {
  text-align: center;
  padding: 2.5rem 1rem 1.5rem;
}

.hero h1 {
  font-size: clamp(2.2rem, 4vw, 3rem);
  margin-bottom: 0.75rem;
}

.hero p {
  color: var(--muted);
  margin: 0 auto;
  max-width: 650px;
}

.grid {
  display: grid;
  gap: 1.5rem;
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
  transition: transform 120ms ease, box-shadow 120ms ease;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.15);
}

.card img {
  width: 100%;
  height: 200px;
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

.button-link, .cta-button {
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
}

.button-link:hover, .cta-button:hover {
  background: var(--brand-dark);
  transform: translateY(-1px);
  box-shadow: 0 18px 30px rgba(224, 72, 80, 0.35);
}

.category-hero {
  display: grid;
  gap: 2rem;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  align-items: center;
  margin-bottom: 2rem;
}

.category-hero h1 {
  font-size: clamp(2rem, 3.2vw, 2.6rem);
  margin: 0;
}

.category-hero p {
  color: var(--muted);
  font-size: 1.05rem;
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
  font-size: clamp(2rem, 3vw, 2.5rem);
  margin: 0;
}

.product-meta .price-callout {
  font-weight: 600;
  color: var(--brand-dark);
}

.feature-list {
  padding-left: 1.1rem;
}

.cta-row {
  margin-top: 1.25rem;
}

footer {
  border-top: 1px solid var(--border);
  margin-top: 3rem;
  padding: 2rem 0;
  text-align: center;
  color: var(--muted);
  font-size: 0.9rem;
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

@media (max-width: 680px) {
  nav {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }
  .nav-links {
    flex-wrap: wrap;
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

    def build(self, categories: List[Category], products: List[Product]) -> None:
        logger.info("Generating site with %s products", len(products))
        self._write_assets()
        self.preload_navigation(categories)
        products_sorted = sorted(products, key=lambda p: p.updated_at, reverse=True)
        self._write_index(categories, products_sorted[:12], products_sorted)
        for category in categories:
            category_products = [
                product
                for product in products_sorted
                if product.category_slug == category.slug
            ]
            self._write_category_page(category, category_products)
            for product in category_products:
                self._write_product_page(product, category)
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
        adsense_slot = ""
        if self.settings.adsense_client_id and self.settings.adsense_slot:
            adsense_slot = (
                "<div class=\"adsense-slot\">"
                f"<ins class=\"adsbygoogle\" style=\"display:block\" data-ad-client=\"{self.settings.adsense_client_id}\" "
                f"data-ad-slot=\"{self.settings.adsense_slot}\" data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>"
                "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"
                "</div>"
            )
        return f"""
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{meta_title}</title>
    <meta name=\"description\" content=\"{meta_description}\" />
    <link rel=\"canonical\" href=\"{canonical}\" />
    <link rel=\"stylesheet\" href=\"/assets/styles.css\" />
    {adsense}
    <meta property=\"og:type\" content=\"website\" />
    <meta property=\"og:title\" content=\"{meta_title}\" />
    <meta property=\"og:description\" content=\"{meta_description}\" />
    <meta property=\"og:url\" content=\"{canonical}\" />
    <meta property=\"og:site_name\" content=\"{html.escape(self.settings.site_name)}\" />
  </head>
  <body>
    <header>
      <nav>
        <a href=\"/index.html\" class=\"logo\">{html.escape(self.settings.site_name)}</a>
        <div class=\"nav-links\">{nav_links}</div>
      </nav>
    </header>
    <main>
      {context.body}
      {adsense_slot}
    </main>
    <footer>
      <p>Updated {html.escape(datetime.utcnow().strftime('%b %d, %Y'))}. Powered by automated Amazon affiliate curation.</p>
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
  <h1>{html.escape(self.settings.site_name)}</h1>
  <p>{html.escape(self.settings.description)}</p>
  <a class=\"button-link\" href=\"{cta_href}\">Browse curated gems</a>
</section>
"""
        category_cards = "".join(
            self._category_card(category) for category in categories
        )
        featured_cards = "".join(
            self._product_card(product) for product in featured_products
        )
        body = f"""
{hero}
<section>
  <h2>Explore by vibe</h2>
  <div class=\"grid\">{category_cards}</div>
</section>
<section>
  <h2>Fresh finds added today</h2>
  <div class=\"grid\">{featured_cards}</div>
</section>
"""
        context = PageContext(
            title=f"{self.settings.site_name} — Daily curated Amazon gift ideas",
            description=self.settings.description,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/index.html",
            body=body,
        )
        self._write_page(self.output_dir / "index.html", context)

    def _write_category_page(self, category: Category, products: List[Product]) -> None:
        cards = "".join(self._product_card(product) for product in products)
        body = f"""
<div class=\"breadcrumbs\"><a href=\"/index.html\">Home</a> &rsaquo; {html.escape(category.name)}</div>
<section class=\"category-hero\">
  <div>
    <h1>{html.escape(category.name)}</h1>
    <p>{html.escape(category.blurb)}</p>
  </div>
  <a class=\"button-link\" href=\"https://www.amazon.com/s?k={html.escape('+'.join(category.keywords))}&tag={html.escape(self.settings.amazon_partner_tag or '')}\" target=\"_blank\" rel=\"noopener sponsored\">Shop full Amazon results</a>
</section>
<section>
  <div class=\"grid\">{cards}</div>
</section>
"""
        context = PageContext(
            title=f"{category.name} — {self.settings.site_name}",
            description=category.blurb,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/{self._category_path(category.slug)}",
            body=body,
        )
        path = self.categories_dir / category.slug / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(path, context)

    def _write_product_page(self, product: Product, category: Category) -> None:
        price_line = f"<p class=\"price-callout\">{html.escape(product.price)}</p>" if product.price else ""
        rating_line = (
            f"<p class=\"review-callout\">{product.rating:.1f} / 5.0 ({product.total_reviews:,} reviews)</p>"
            if product.rating and product.total_reviews
            else ""
        )
        body = f"""
<div class=\"breadcrumbs\"><a href=\"/index.html\">Home</a> &rsaquo; <a href=\"/{self._category_path(category.slug)}\">{html.escape(category.name)}</a></div>
<div class=\"product-page\">
  <div>
    <img src=\"{html.escape(product.image or '')}\" alt=\"{html.escape(product.title)}\" loading=\"lazy\" />
  </div>
  <div class=\"product-meta\">
    <h1>{html.escape(product.title)}</h1>
    {price_line}
    {rating_line}
    {product.blog_content or ''}
    <p class=\"cta-row\"><a class=\"cta-button\" href=\"{html.escape(product.link)}\" target=\"_blank\" rel=\"noopener sponsored\">Grab it on Amazon</a></p>
  </div>
</div>
"""
        context = PageContext(
            title=f"{product.title} — {category.name} gift idea",
            description=product.summary or self.settings.description,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/{self._product_path(product)}",
            body=body,
        )
        path = self.products_dir / product.slug / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(path, context)

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

    def _product_card(self, product: Product) -> str:
        description = html.escape(product.summary or "Discover why we love this find.")
        image = html.escape(product.image or "")
        return f"""
<article class=\"card\">
  <a href=\"/{self._product_path(product)}\"><img src=\"{image}\" alt=\"{html.escape(product.title)}\" loading=\"lazy\" /></a>
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
  <a href=\"/{self._category_path(category.slug)}\"><img src=\"https://source.unsplash.com/600x400/?{html.escape(category.slug)}\" alt=\"{html.escape(category.name)}\" /></a>
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
