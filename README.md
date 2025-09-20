# GiftGrab Automation

This repository contains the fully automated pipeline that powers the GiftGrab affiliate site. It collects inventory from the eBay Browse API (and optionally Amazon PA-API), applies thirty-day cooldowns to items and topics, and renders a static site with evergreen roundup guides, JSON-LD metadata, sitemaps, and RSS feeds. Everything runs on the Python standard library.

## Commands

All entry points live in `giftgrab/cli.py` and are executed with `python -m giftgrab.cli`:

| Command | Description |
| --- | --- |
| `python -m giftgrab.cli update` | Fetch products from eBay, merge curated JSON feeds under `data/retailers/`, enforce the 30-day item cooldown, and persist the catalog to `data/items.json`. Builds fail if fewer than 50 products remain. |
| `python -m giftgrab.cli roundups --limit 15` | Generate at least fifteen roundup guides, update `data/topics_history.json`, and render the static site to `public/` with canonical URLs, WebSite JSON-LD, ItemList JSON-LD for each guide, and Product JSON-LD for every card/page. |
| `python -m giftgrab.cli check` | Lightweight QA gate that ensures the catalog has ≥50 products, ≥15 guides, no duplicate slugs, and that `public/sitemap.xml`, `public/robots.txt`, and `public/rss.xml` exist. |
| `python -m giftgrab.cli ebay "coffee gifts" --limit 5 --marketplace EBAY_US` | Run a quick Browse API query to validate credentials and inspect normalized eBay inventory. |

The recommended Netlify build command is:

```bash
python -m giftgrab.cli update && python -m giftgrab.cli roundups --limit 15
```

## Data layout

Generated artifacts live under `data/`:

- `items.json` – current inventory.
- `seen_items.json` – 30-day cooldown ledger keyed by product ID.
- `topics_history.json` – recently used roundup topics to avoid repetition.
- `guides.json` – metadata for the latest set of published guides.

The static site is written to `public/` and includes `guides/`, `categories/`, `products/`, `sitemap.xml`, `robots.txt`, and `rss.xml`.

## Environment variables

### Retailer credentials

- `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` – required to call the eBay Browse API.
- `EBAY_CAMPAIGN_ID` (optional) – appended to outbound eBay URLs when present.
- `EBAY_MARKETPLACE_ID` (optional) – overrides the default `EBAY_US` marketplace header for Browse API requests.
- `AMAZON_PAAPI_ACCESS_KEY` and `AMAZON_PAAPI_SECRET_KEY` (optional) – enable Amazon PA-API requests.
- `AMAZON_ASSOCIATE_TAG` – applied to every Amazon URL; defaults to the site’s required tag when unset.
- `AMAZON_MARKETPLACE` (optional) – defaults to `www.amazon.com`.

The pipeline works with eBay alone when Amazon credentials are absent. When Amazon keys are later provided, the PA-API signer is already wired and ready.

### Site metadata

- `SITE_NAME`, `SITE_BASE_URL`, `SITE_DESCRIPTION`
- `SITE_LOGO_URL`, `SITE_FAVICON_URL`
- `SITE_TWITTER`, `SITE_FACEBOOK`, `SITE_CONTACT_EMAIL`
- `SITE_KEYWORDS` (comma-separated list)
- `SITE_ANALYTICS_ID` or `SITE_ANALYTICS_SNIPPET` (snippet wins)
- `ADSENSE_CLIENT_ID`, `ADSENSE_SLOT`, `ADSENSE_RAIL_SLOT`

### Netlify function secret

Set `ACCOUNT_DELETION_TOKEN` in the Netlify environment. The `netlify/functions/accountDeletion.js` handler validates incoming requests against this token and returns `401` on mismatch, `204` on success. Rotate this token periodically and update the Netlify environment value accordingly.

## Continuous delivery

`.github/workflows/refresh.yml` schedules a daily build (09:07 America/New_York) and can also be triggered manually. It runs the `update` and `roundups` commands and then deploys `public/` through Netlify using the configured secrets: `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`, `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, and optional Amazon credentials.

## Output features

- Guides include 20 ranked products, price filters for “Under $X” topics, and deterministic blurbs between 120–160 characters.
- All affiliate anchors use `rel="sponsored nofollow noopener"`. Amazon URLs always include the configured associate tag, and eBay links append `campid` when supplied.
- Each page emits WebSite JSON-LD with a search `potentialAction`. Guide pages add ItemList JSON-LD, and every product card/page emits Product JSON-LD with offers when pricing is known.
- Generated pages include Open Graph and Twitter Card tags, optional AdSense units gated on `ADSENSE_CLIENT_ID`, and GA4 snippets when analytics variables are present.
- `public/sitemap.xml`, `public/robots.txt`, and `public/rss.xml` are regenerated on every build to match the latest guides and products.

With credentials configured and the GitHub workflow enabled, the site refreshes itself daily while staying compliant with affiliate disclosure and SEO best practices.
