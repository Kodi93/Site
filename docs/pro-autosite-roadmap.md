# Professionalizing GrabGifts.net Within the Existing Python Stack

The production site at [grabgifts.net](https://grabgifts.net) already ships from this repository's Python static generator. The roadmap below adapts the automation, SEO, and monetization upgrades that were scoped for a Next.js/Netlify rewrite so they reinforce (rather than replace) the current architecture.

## 1. Architecture Alignment and Pipeline Orchestration
- **Stay on the Python toolchain.** The daily automation still runs through `giftgrab/cli.py` and `giftgrab/pipeline.py`, which coordinate data refreshes, content generation, and publishing. The goal is to extend these modules instead of recreating them in another runtime.
- **Respect the repository layout described in [`README.md`](../README.md).** Assets land under `giftgrab/` (logic), `data/` (inputs), and `public/` (build output). New capabilities—scheduled ingesters, monitoring hooks, or storefront tweaks—should live alongside the existing modules (`amazon.py`, `generator.py`, `repository.py`) so they slot naturally into the pipeline.
- **Scheduled automation.** `giftgrab/pipeline.py` already exposes idempotent functions for ingestion and site builds. Wire any cron or serverless jobs to call those entry points, keeping retry and error reporting in Python so we can add observability without scattering logic across stacks.

## 2. SEO Copy & Quality Gates (Python-first)
- **Reuse `giftgrab/text.py`.** This module owns helper functions such as `make_title`, `make_meta`, and `make_intro`. Enhancements (see commit) refine their heuristics while preserving signatures so existing callers in `giftgrab/blog.py` and `giftgrab/generator.py` continue to work.
- **Maintain the guardrails in `giftgrab/quality.py`.** The `passes_seo` function enforces title length, description bounds, and minimum body copy length. Any future thresholds should be implemented here and consumed by the sitemap builder in `giftgrab/generator.py` to keep low-quality pages out of the index automatically.
- **Document copy expectations.** Product metadata must stay within search-friendly ranges (titles ≤ 60 chars, descriptions 140–155 chars) and avoid spam phrases. We now have regression tests to lock those behaviours in place.

## 3. Generator, Metadata, and Monetization Enhancements
- **Head markup and JSON-LD.** `giftgrab/generator.py` remains responsible for `<head>` tags, Open Graph/Twitter metadata, canonical URLs, and Schema.org payloads. Iterate there when adjusting structured data or analytics snippets.
- **AdSense and affiliate compliance.** The generator already injects Google AdSense units, GA4 loaders (when configured), and outbound affiliate disclosures. Keep those concerns centralized in the HTML templates that `generator.py` renders so the CLI build outputs stay production-ready.
- **Sitemap and robots discipline.** The sitemap builder inside `generator.py` references `passes_seo` to exclude thin pages. Continue using that flow so automated quality gates stay in sync with our SEO heuristics.
- **Ingestion quality gates.** Refresh routines in `giftgrab/amazon.py` and `giftgrab/repository.py` can call `passes_seo` (or related helpers) before promoting products to the live catalog, ensuring stale or incomplete items do not leak into builds.

## 4. Next Steps After This Commit
- **Amazon PA-API monitoring.** Extend `giftgrab/amazon.py` to log rate limits and response anomalies; route failures through the existing CLI so external schedulers can alert via webhooks.
- **Retailer stubs.** Add placeholder loaders in `giftgrab/retailers.py` that outline credential requirements for eBay or Impact once their feeds are prioritized, matching the Python interface other ingesters already use.
- **Analytics & error reporting.** When adding GA4 or webhook integrations, keep configuration in `giftgrab/config.py` to minimize environment sprawl and make the behaviour testable.

This plan preserves the proven Python static generator while introducing the professional polish (SEO text, metadata, monetization, and automation discipline) that the business requested.
