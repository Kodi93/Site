# GrabGifts Automation

This repository contains the automation pipeline behind [grabgifts.net](https://grabgifts.net). The Node.js tooling fetches
giftable products from the eBay Browse API (and optionally Amazon PA-API), normalizes the data, and publishes at least fifteen
roundup guides per day while respecting thirty-day cooldowns for both products and topics. The generated site is fully static,
served from the `public/` directory, and deploys to Netlify via GitHub Actions.

## Prerequisites

- Node.js 20+
- npm 9+
- eBay App ID authorised for the Browse API. The pipeline uses the app-only OAuth flow and does not require a client secret.
- (Optional) Amazon Product Advertising API credentials if you want to mix Amazon items into the catalogue.

Install dependencies once after cloning the repository:

```bash
npm install
```

## Daily automation workflow

The automation is implemented in `tools/` and wired to npm scripts:

| Command | Description |
| --- | --- |
| `npm run update` | Calls the eBay (and optional Amazon) search endpoints, normalizes results, deduplicates IDs, and writes `data/items.json`. Items cannot reappear for 30 days thanks to the `data/seen_items.json` cache. |
| `npm run build` | Selects at least fifteen fresh topics, filters relevant products, renders HTML guides under `public/guides/<slug>/index.html`, and regenerates `public/sitemap.xml`. Topics also observe a 30-day cooldown via `data/topics_history.json`. |
| `npm run check` | Ensures the generated inventory has at least 50 unique items and that guides were produced before deploying. |

Guides automatically include affiliate disclosures, JSON-LD ItemList markup, lazy-loaded images, and outbound links annotated with
`rel="sponsored nofollow noopener"`. The helper in `tools/util.mjs` also injects the `kayce25-20` Amazon affiliate tag whenever an
Amazon URL is detected.

### Data directory

All generated data lives in `data/`:

- `items.json` – normalized inventory sourced in the latest run.
- `seen_items.json` – 30-day cooldown log keyed by item ID/ASIN.
- `topics_history.json` – recent topics used to avoid repeating roundup ideas inside the cooldown window.
- `.gitkeep` – ensures the directory is tracked when empty.

The `public/` folder contains the rendered static site, including a canonical `robots.txt` and sitemap.

## Secrets and environment variables

### GitHub Actions (`.github/workflows/refresh.yml`)

Configure the following repository secrets so the scheduled workflow can refresh content and deploy to Netlify:

- `EBAY_CLIENT_ID` (required) – eBay App ID used for the OAuth client-credentials exchange.
- `NETLIFY_AUTH_TOKEN` (required) – token with permission to deploy the target Netlify site.
- `NETLIFY_SITE_ID` (required) – identifier of the Netlify site that will receive deployments.
- `AMZ_ACCESS_KEY` (optional) – Amazon PA-API access key when Amazon sourcing is enabled.
- `AMZ_SECRET_KEY` (optional) – Amazon PA-API secret key when Amazon sourcing is enabled.

The workflow also sets `AMZ_PARTNER_TAG` to `kayce25-20` so Amazon links stay affiliate-ready.

### Netlify environment

Set these variables in the Netlify site configuration:

- `ACCOUNT_DELETION_TOKEN` (required) – shared secret for the account deletion webhook (see below).
- `AMZ_ACCESS_KEY` / `AMZ_SECRET_KEY` (optional) – Amazon credentials if you enable PA-API sourcing in Netlify builds.
- `EBAY_CLIENT_ID` (optional) – only needed if Netlify itself triggers `npm run update` during manual deploys.

## Scheduled refresh and deployment

`.github/workflows/refresh.yml` runs every day at 10:13 AM America/New_York (cron `13 10 * * *`) and is also exposed as a
manual “Run workflow” button. The job performs the following steps:

1. Checks out the repository and sets up Node.js 20.
2. Installs dependencies with `npm ci`.
3. Executes `npm run update`, `npm run build`, and `npm run check` with the appropriate secrets injected.
4. Deploys the generated `public/` directory to Netlify using `nwtgck/actions-netlify@v2`.

## Netlify Function hardening

`netlify/functions/accountDeletion.js` expects the Netlify environment variable `ACCOUNT_DELETION_TOKEN`. Incoming requests must
send this value via the `x-verification-token` header; otherwise the function responds with `401 Unauthorized`. When the header
matches, the function returns a `204 No Content` response. If the environment variable is missing, the handler exits with a 500
error so misconfigurations are easy to spot.

## Running locally

To generate content locally you will need an eBay App ID (and optionally Amazon credentials). Export the required environment
variables and run the npm scripts:

```bash
export EBAY_CLIENT_ID=your-ebay-app-id
npm run update
npm run build
npm run check
```

The scripts will populate `data/` and `public/`. If you lack real credentials, you can still lint the repository or inspect the
tooling, but the automation commands will exit early when the APIs reject the request.

## Repository structure

```
├── tools/                 # Node.js automation scripts
├── data/                  # Generated data files (items, cooldown history)
├── public/                # Static output (guides, robots.txt, sitemap.xml)
├── netlify/               # Netlify functions package (account deletion handler lives here)
├── .github/workflows/     # Scheduled refresh + deployment workflow
├── package.json           # npm scripts and dependencies
└── README.md              # This documentation
```

## Notes

- All outbound product links include `rel="sponsored nofollow noopener"` to comply with affiliate disclosures.
- Topic selection enforces a 30-day cooldown per slug, guaranteeing at least fifteen unique guides each day.
- Item reuse is prevented for 30 days using the `seen_items.json` ledger.
- `public/robots.txt` references the sitemap at `https://grabgifts.net/sitemap.xml` so crawlers can discover generated guides.

With the secrets configured and the scheduler enabled, the site rebuilds and deploys itself every day with fresh gift ideas.
