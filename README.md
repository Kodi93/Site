# Curated Gift Radar

An automated static site generator that pulls trending gift ideas from Amazon's Product Advertising API, writes hype-heavy blurbs for each item, and publishes them into ten easy-to-browse categories (think "Gifts for Him", "Tech & Gadgets", and more). The build also injects Google AdSense placements and your Amazon affiliate links so the site can monetize from day one.

## Features

- **Ten opinionated categories** tuned for gift discovery, mirroring the browsing experience of sites like *dudeiwantthat.com*.
- **Daily automation pipeline** that fetches fresh products per category, generates long-form promotional copy, and rebuilds the static HTML site.
- **Affiliate-ready links** that enforce your Amazon partner tag on every product card and category deep-link.
- **AdSense support** baked into the base layout so ads render on each page once you provide your client and slot IDs.
- **SEO-friendly pages** with dynamic metadata, schema.org markup, RSS feed, and sitemaps that advertise last-modified times.
- **No external dependencies** – the tooling runs entirely on Python’s standard library so it can execute in constrained hosting environments.

## Project layout

```
├── giftgrab/
│   ├── amazon.py           # Minimal Amazon PA-API client with AWS signature v4 signing
│   ├── blog.py             # Marketing copy generator for each product page
│   ├── cli.py              # Entry point for running the automation pipeline
│   ├── config.py           # Site settings, category definitions, and path helpers
│   ├── generator.py        # Static site renderer (HTML/CSS) and feed/sitemap builder
│   ├── models.py           # Dataclasses for Product and Category records
│   ├── pipeline.py         # Orchestrates fetching, content generation, and persistence
│   ├── repository.py       # JSON-backed persistence layer for product data
│   └── utils.py            # Misc helpers (slugify, timestamp, JSON IO)
├── data/.gitkeep           # Placeholder so the data directory exists in git
├── public/                 # (ignored) where the generated site is written
├── requirements.txt        # Placeholder noting that only stdlib is required
├── tests/                  # Unit tests covering critical behaviour
└── README.md               # This file
```

## Prerequisites

You will need:

- Python 3.11+ (the standard library client relies on `hmac` and modern typing features).
- Valid Amazon Product Advertising API (PA-API) credentials: an access key, secret key, and associate tag.
- A configured Google AdSense account (client ID and optional slot ID) if you want ad units injected.

No `pip install` step is required because the project only uses the Python standard library.

## Configuration

The CLI reads configuration from environment variables so you can keep secrets outside of source control.

| Variable | Required | Description |
| --- | --- | --- |
| `AMAZON_PAAPI_ACCESS_KEY` | Yes (for `update`) | AWS access key for PA-API 5 requests |
| `AMAZON_PAAPI_SECRET_KEY` | Yes (for `update`) | AWS secret key for PA-API 5 requests |
| `AMAZON_ASSOCIATE_TAG` | Yes | Your Amazon affiliate tag appended to every link |
| `AMAZON_MARKETPLACE` | No | Marketplace domain (default `www.amazon.com`) |
| `AMAZON_API_HOST` | No | API host (default `webservices.amazon.com`) |
| `SITE_NAME` | No | Display name shown in the header |
| `SITE_DESCRIPTION` | No | Homepage meta description |
| `SITE_BASE_URL` | No | Canonical base URL used in sitemaps and canonical tags |
| `ADSENSE_CLIENT_ID` | No | Google AdSense client ID (format `ca-pub-XXXXXXXX`) |
| `ADSENSE_SLOT` | No | Optional AdSense slot for in-content ads |
| `SITE_TWITTER` / `SITE_FACEBOOK` | No | Social handles exposed in structured data |
| `SITE_LANGUAGE` | No | Language code applied to the `<html lang>` attribute |
| `SITE_LOCALE` | No | Locale value used for Open Graph metadata |
| `SITE_LOGO_URL` | No | Absolute URL for your logo used in structured data and Open Graph fallbacks |
| `SITE_FAVICON_URL` | No | Absolute URL for the favicon referenced in page `<head>` |

## Usage

1. **Initial data fetch and site build**

   ```bash
   export AMAZON_PAAPI_ACCESS_KEY=...
   export AMAZON_PAAPI_SECRET_KEY=...
   export AMAZON_ASSOCIATE_TAG=yourtag-20
   export ADSENSE_CLIENT_ID=ca-pub-xxxxxxxxxxxxxxxx
   export SITE_BASE_URL=https://gifts.example.com

   python -m giftgrab.cli update --item-count 6
   ```

   The command will:

   - fetch `item-count` products for each of the ten categories,
   - auto-write persuasive blog copy for every item,
   - persist everything to `data/products.json`,
   - render the full static site into the `public/` folder (index, categories, product pages, RSS, and sitemap).

2. **Regenerate site without hitting Amazon**

   If you only changed styles or copy templates, skip the API requests and rebuild from stored data:

   ```bash
   python -m giftgrab.cli generate
   ```

3. **Schedule daily automation**

   Use cron (or a serverless scheduler) to refresh the catalogue automatically every morning:

   ```cron
   # Run at 6:00 AM server time
   0 6 * * * cd /var/www/gifts && /usr/bin/env -S bash -lc 'python -m giftgrab.cli update --item-count 8'
   ```

   The script is idempotent – products are upserted by ASIN so existing items get refreshed while new finds are appended.

## Deploying the static site

The generated HTML lives in `public/`. You can deploy it to any static hosting provider:

- **Netlify / Vercel / Cloudflare Pages** – point the build command to `python -m giftgrab.cli update` and publish the `public` directory.
- **Amazon S3 + CloudFront** – sync the `public/` folder to S3 and enable CDN caching.
- **Traditional hosting** – rsync the directory to your web server's document root.

Because the output is static, the site is fast, cache-friendly, and inexpensive to host.

## Running tests

```bash
python -m unittest
```

The suite covers slug generation, affiliate link enforcement, blog copy rendering, and JSON persistence logic.

## Extending the system

- Adjust or add categories in `giftgrab/config.py` – the pipeline automatically loops over whatever is defined there.
- Tweak the marketing copy templates in `giftgrab/blog.py` to change the tone of the generated blurbs.
- Override the CSS in `giftgrab/generator.py` if you want a different visual identity.
- Hook in your favourite deployment mechanism by scripting around the CLI commands.

## Caveats

- Amazon’s PA-API has request throttling; keep `--item-count` reasonable (6–10 per category) or throttle the scheduler.
- The project does not ship with API credentials – be sure to set the required environment variables before running `update`.
- The Unsplash hero images are loaded at runtime; swap to your own static assets for guaranteed availability.

Happy curating!
