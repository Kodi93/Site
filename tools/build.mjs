import fs from "node:fs";
import path from "node:path";
import { pickTopics } from "./topics.mjs";
import { priceNumber } from "./util.mjs";

const IN = path.join("data", "items.json");
const PUB = "public";
const SITE_NAME = "grabgifts";
const SITE_DESCRIPTION =
  "Grab Gifts surfaces viral-ready Amazon finds with conversion copy and plug-and-play affiliate automation. Launch scroll-stopping gift funnels that convert on autopilot.";

const BASE_TEMPLATE_PATH = path.join("templates", "base.html");
const HEADER_PATH = path.join("templates", "partials", "header.html");
const FOOTER_PATH = path.join("templates", "partials", "footer.html");
const THEME_PATH = path.join(PUB, "assets", "theme.css");
const FEED_DIR = path.join(PUB, "assets", "feed");
const FEED_PAGE_SIZE = 18;
const GUIDE_LEDGER_PATH = path.join("data", "guides.json");

const FEED_MODES = [
  {
    id: "recent",
    label: "Most Recent",
    description: "Catch the newest arrivals as soon as we publish them.",
    empty: "New gifts are loading soon—check back for fresh picks.",
    sort: (items) =>
      items
        .slice()
        .sort((a, b) => {
          const diff = parseTimestamp(b.updated_at || b.updatedAt) - parseTimestamp(a.updated_at || a.updatedAt);
          if (diff !== 0) return diff;
          return (a.title || "").localeCompare(b.title || "");
        }),
  },
  {
    id: "trending",
    label: "Trending",
    description: "Browse the crowd-pleasers rising to the top of our catalog.",
    empty: "No trending picks right now—check back after the next refresh.",
    sort: (items) =>
      items
        .slice()
        .sort((a, b) => {
          const reviewDiff = Number(b.rating_count || b.ratingCount || 0) - Number(a.rating_count || a.ratingCount || 0);
          if (reviewDiff !== 0) return reviewDiff;
          const ratingDiff = Number(b.rating || 0) - Number(a.rating || 0);
          if (ratingDiff !== 0) return ratingDiff;
          const updatedDiff =
            parseTimestamp(b.updated_at || b.updatedAt) - parseTimestamp(a.updated_at || a.updatedAt);
          if (updatedDiff !== 0) return updatedDiff;
          return (a.title || "").localeCompare(b.title || "");
        }),
  },
];
const PROTECTED_FILES = new Set(
  [BASE_TEMPLATE_PATH, HEADER_PATH, FOOTER_PATH, THEME_PATH].map((p) =>
    path.resolve(p),
  ),
);

const BASE_TEMPLATE = applyIncludes(
  fs.readFileSync(BASE_TEMPLATE_PATH, "utf8").replace(/^\ufeff/, ""),
  {
    "partials/header.html": readPartial(HEADER_PATH),
    "partials/footer.html": readPartial(FOOTER_PATH),
  },
);

function readPartial(partialPath) {
  return fs.readFileSync(partialPath, "utf8").replace(/^\ufeff/, "").trim();
}

function applyIncludes(template, includes) {
  let output = template;
  for (const [includePath, markup] of Object.entries(includes)) {
    const pattern = new RegExp(
      `([\\t ]*)\{%\\s*include\\s+['"]${includePath.replace(/\//g, "\\/")}['"]\\s*%\}`,
      "g",
    );
    output = output.replace(pattern, (_, indent) => indentMarkup(markup, indent));
  }
  return output;
}

function indentMarkup(markup, indent) {
  const trimmed = markup.trim();
  if (!trimmed) return "";
  return trimmed
    .split(/\r?\n/)
    .map((line) => (line ? `${indent}${line}` : ""))
    .join("\n");
}

function escapeHtml(input) {
  return String(input)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseTimestamp(value) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function loadGuideLedger() {
  try {
    return JSON.parse(fs.readFileSync(GUIDE_LEDGER_PATH, "utf8"));
  } catch (error) {
    if (error && error.code !== "ENOENT") {
      console.warn("Failed to read guide ledger", error);
    }
    return [];
  }
}

function saveGuideLedger(entries) {
  fs.mkdirSync(path.dirname(GUIDE_LEDGER_PATH), { recursive: true });
  fs.writeFileSync(GUIDE_LEDGER_PATH, `${JSON.stringify(entries, null, 2)}\n`);
}

function compactObject(payload) {
  const output = {};
  for (const [key, value] of Object.entries(payload)) {
    if (value === undefined || value === null) continue;
    if (typeof value === "string" && !value.trim()) continue;
    output[key] = value;
  }
  return output;
}

function formatCategory(item) {
  if (item.category) return item.category;
  if (item.category_slug) {
    return titleCase(String(item.category_slug).replace(/[-_]+/g, " "));
  }
  return "";
}

function toFeedEntry(item) {
  return compactObject({
    id: item.id,
    title: item.title,
    url: item.url,
    image: item.image,
    price: item.price,
    brand: item.brand,
    category: formatCategory(item),
    updatedAt: item.updated_at || item.updatedAt,
  });
}

function ensureNotProtected(targetPath) {
  const resolved = path.resolve(targetPath);
  if (PROTECTED_FILES.has(resolved)) {
    throw new Error("Protected layout file");
  }
}

function writeFile(target, html) {
  ensureNotProtected(target);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, html);
}

function renderWithBase(content) {
  let html = BASE_TEMPLATE;
  html = html.replace(/\{\{\s*content\|safe\s*\}\}/g, content);
  html = html.replace(/\{\{\s*content\s*\}\}/g, escapeHtml(content));
  return html;
}

const BANNED_PHRASES = ["fresh drops", "active vibes"];
const STOPWORDS = new Set(["for", "a", "the", "and", "of"]);
const RIGHT_NOW_SUFFIX = /\s+right now\.?$/i;
const BEST_FOR_PATTERN = /^best\s+for\s+a\s+(.+?)\s+gifts(.*)$/i;
const TITLE_REPLACEMENTS = new Map([["Techy", "Tech"]]);

function stripBannedPhrases(text) {
  let output = text;
  for (const phrase of BANNED_PHRASES) {
    const pattern = new RegExp(phrase, "ig");
    output = output.replace(pattern, "");
  }
  return output.trim();
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function titleCase(value) {
  return String(value).replace(/[A-Za-z]+/g, (word) => {
    if (/[A-Z]/.test(word.slice(1))) return word;
    if (word.length > 1 && word === word.toUpperCase()) return word;
    return word[0].toUpperCase() + word.slice(1).toLowerCase();
  });
}

function applyStopwords(text) {
  let firstWordSeen = false;
  return text.replace(/[A-Za-z]+/g, (segment) => {
    const lower = segment.toLowerCase();
    if (!firstWordSeen) {
      firstWordSeen = true;
      return segment;
    }
    if (STOPWORDS.has(lower)) {
      return lower;
    }
    return segment;
  });
}

function polishGuideTitle(title) {
  let text = (title || "").trim();
  if (!text) return "";
  text = text.replace(RIGHT_NOW_SUFFIX, "").trim();
  const match = text.match(BEST_FOR_PATTERN);
  if (match) {
    const subject = match[1].trim();
    const tail = match[2] || "";
    text = `Best ${subject} Gifts${tail}`;
  }
  text = text.replace(/\s+/g, " ").trim();
  text = applyStopwords(titleCase(text));
  for (const [source, target] of TITLE_REPLACEMENTS) {
    const pattern = new RegExp(`\\b${escapeRegExp(source)}\\b`, "g");
    text = text.replace(pattern, target);
  }
  return text.trim();
}

function formatGuideDate(value) {
  const timestamp = parseTimestamp(value);
  if (!timestamp) return "";
  return new Date(timestamp).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function renderGuideCard(item) {
  if (!item.image) return "";
  const parts = ["<li class=\"card\">"];
  parts.push(
    `<a href=\"${escapeHtml(item.url)}\" rel=\"sponsored nofollow noopener\" target=\"_blank\">`,
  );
  parts.push(
    `<img src=\"${escapeHtml(item.image)}\" alt=\"${escapeHtml(item.title)}\" loading=\"lazy\">`,
  );
  parts.push(`<h3>${escapeHtml(item.title)}</h3>`);
  if (item.price) {
    parts.push(`<p class=\"price\">${escapeHtml(item.price)}</p>`);
  }
  parts.push("</a></li>");
  return parts.join("");
}

function renderFeedItem(item) {
  if (!item || !item.title || !item.url || !item.image) return "";
  const metaParts = [];
  if (item.category) metaParts.push(escapeHtml(item.category));
  if (item.brand) metaParts.push(escapeHtml(item.brand));
  const meta = metaParts.length
    ? `<p class=\"feed-card-meta\">${metaParts.join(" • ")}</p>`
    : "";
  const price = item.price ? `<p class=\"feed-card-price\">${escapeHtml(item.price)}</p>` : "";
  const media = `<div class=\"feed-card-media\"><img src=\"${escapeHtml(item.image)}\" alt=\"${escapeHtml(item.title)}\" loading=\"lazy\"></div>`;
  const idAttr = item.id ? ` data-feed-id=\"${escapeHtml(item.id)}\"` : "";
  return [
    `<article class=\"feed-card\"${idAttr}>`,
    `<a class=\"feed-card-link\" href=\"${escapeHtml(item.url)}\" rel=\"sponsored nofollow noopener\" target=\"_blank\">`,
    media,
    '<div class="feed-card-body">',
    meta,
    `<h3 class=\"feed-card-title\">${escapeHtml(item.title)}</h3>`,
    price,
    "</div>",
    "</a>",
    "</article>",
  ]
    .filter(Boolean)
    .join("\n");
}

function renderGuidePreview(guide) {
  const summary = guide.summary
    ? escapeHtml(stripBannedPhrases(guide.summary))
    : "Explore thoughtful ideas for every list.";
  const title = polishGuideTitle(guide.title);
  const timestamp = guide.createdAt ? parseTimestamp(guide.createdAt) : 0;
  const isoDate = timestamp ? new Date(timestamp).toISOString() : "";
  const published = timestamp ? formatGuideDate(guide.createdAt) : "";
  const meta =
    isoDate && published
      ? `<p class=\"guide-card-meta\"><time datetime=\"${escapeHtml(isoDate)}\">${escapeHtml(published)}</time></p>`
      : "";
  return [
    '<li class="card guide-card">',
    `<a href=\"/guides/${escapeHtml(guide.slug)}/\">`,
    meta,
    `<h3>${escapeHtml(title)}</h3>`,
    `<p>${summary}</p>`,
    "</a>",
    "</li>",
  ].join("\n");
}

function renderGuidePage(title, slug, items) {
  const polishedTitle = polishGuideTitle(title);
  const cards = items
    .map((item) => renderGuideCard(item))
    .filter(Boolean)
    .join("\n");
  const sections = [`<h1>${escapeHtml(polishedTitle)}</h1>`];
  if (cards) {
    sections.push(`<ol class=\"grid\">${cards}</ol>`);
  } else {
    sections.push("<p>No items are available for this guide right now.</p>");
  }
  return renderWithBase(sections.join("\n"));
}

function buildFeedForMode(items, mode) {
  const sorted = mode.sort(items);
  const feedItems = sorted
    .filter((item) => item && item.image && item.url && item.title)
    .map((item) => toFeedEntry(item));

  const baseDir = path.join(FEED_DIR, mode.id);
  const baseHref = `/assets/feed/${mode.id}`;
  fs.mkdirSync(baseDir, { recursive: true });

  const totalPages = Math.ceil(feedItems.length / FEED_PAGE_SIZE);
  const manifest = {
    mode: mode.id,
    label: mode.label,
    description: mode.description,
    pageSize: FEED_PAGE_SIZE,
    totalItems: feedItems.length,
    totalPages,
    generatedAt: new Date().toISOString(),
    pages: [],
  };

  for (let index = 0; index < feedItems.length; index += FEED_PAGE_SIZE) {
    const page = Math.floor(index / FEED_PAGE_SIZE) + 1;
    const slice = feedItems.slice(index, index + FEED_PAGE_SIZE);
    const href = `${baseHref}/page-${page}.json`;
    manifest.pages.push({ page, href });
    writeFile(
      path.join(baseDir, `page-${page}.json`),
      `${JSON.stringify(
        {
          page,
          pageSize: FEED_PAGE_SIZE,
          totalPages,
          totalItems: feedItems.length,
          items: slice,
        },
        null,
        2,
      )}\n`,
    );
  }

  writeFile(path.join(baseDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);

  return {
    id: mode.id,
    label: mode.label,
    description: mode.description,
    empty: mode.empty,
    baseHref,
    manifestHref: `${baseHref}/manifest.json`,
    pageSize: FEED_PAGE_SIZE,
    totalItems: feedItems.length,
    totalPages,
    initialPage: feedItems.length ? 1 : 0,
    nextPage: totalPages > 1 ? `${baseHref}/page-2.json` : "",
    initialItems: feedItems.slice(0, FEED_PAGE_SIZE),
  };
}

function writeFeedData(items) {
  fs.rmSync(FEED_DIR, { recursive: true, force: true });
  const modes = FEED_MODES.map((mode) => buildFeedForMode(items, mode));
  const fallback = modes[0] || null;
  const defaultMode = modes.find((mode) => mode.totalItems > 0) || fallback;
  return {
    defaultMode: defaultMode ? defaultMode.id : null,
    modes,
  };
}

function renderHomePage(recentGuides, feed) {
  const hero = ['<section class="hero">', `<h1>${escapeHtml(SITE_NAME)}</h1>`];
  const description = stripBannedPhrases(SITE_DESCRIPTION);
  if (description) {
    hero.push(`<p>${escapeHtml(description)}</p>`);
  }
  const hasFeed = Array.isArray(feed?.modes) && feed.modes.some((mode) => mode.totalItems > 0);
  const heroActions = [];
  if (recentGuides.length) {
    heroActions.push('<a class="button" href="#guides">Catch this week\'s guides</a>');
  }
  if (hasFeed) {
    heroActions.push('<a class="button button-secondary" href="#latest">Scroll the gift feed</a>');
  }
  heroActions.push('<a class="button button-ghost" href="/guides/">View all guides</a>');
  if (heroActions.length) {
    hero.push('<div class="hero-actions">');
    hero.push(heroActions.join('\n'));
    hero.push('</div>');
  }
  hero.push('</section>');
  const heroMarkup = hero.filter(Boolean).join('\n');

  const guideCards = recentGuides
    .map((guide) => renderGuidePreview(guide))
    .filter(Boolean)
    .join('\n');
  const guidesSectionParts = [
    '<section class="feed-section" id="guides">',
    '<div class="feed-header">',
    "<h2>This week\'s guides</h2>",
    "<p>Catch up on everything we published across the last seven days.</p>",
    '</div>',
  ];
  if (guideCards) {
    guidesSectionParts.push(`<ol class="grid guide-grid">${guideCards}</ol>`);
  } else {
    guidesSectionParts.push(
      '<p class="feed-empty">Our next guides are publishing soon. Check back tomorrow for fresh picks.</p>',
    );
  }
  guidesSectionParts.push(
    '<div class="hero-actions"><a class="button button-ghost" href="/guides/">Browse every guide</a></div>',
  );
  guidesSectionParts.push('</section>');
  const guidesSection = guidesSectionParts.join('\n');

  let feedSection = '';
  if (Array.isArray(feed?.modes) && feed.modes.length) {
    const defaultModeId = feed.defaultMode || (feed.modes[0] && feed.modes[0].id) || '';
    const defaultMode = feed.modes.find((mode) => mode.id === defaultModeId) || feed.modes[0] || null;
    const tabs = feed.modes
      .map((mode) => {
        const isActive = defaultMode && mode.id === defaultMode.id;
        const disabled = mode.totalItems === 0 ? ' disabled' : '';
        const classes = ['feed-tab'];
        if (isActive) classes.push('is-active');
        const ariaSelected = isActive ? 'true' : 'false';
        const tabIndex = isActive ? '0' : '-1';
        return `<button class="${classes.join(' ')}" type="button" role="tab" aria-selected="${ariaSelected}" tabindex="${tabIndex}" data-feed-tab="${escapeHtml(mode.id)}"${disabled}>${escapeHtml(mode.label)}</button>`;
      })
      .join('');
    const defaultMarkup = defaultMode && defaultMode.initialItems.length
      ? defaultMode.initialItems.map((item) => renderFeedItem(item)).filter(Boolean).join('\n')
      : `<p class="feed-empty">${escapeHtml(defaultMode ? defaultMode.empty : 'More gifts are loading soon—check back for fresh picks.')}</p>`;
    const templates = feed.modes
      .filter((mode) => !defaultMode || mode.id !== defaultMode.id)
      .map((mode) => {
        const markup = mode.initialItems.length
          ? mode.initialItems.map((item) => renderFeedItem(item)).filter(Boolean).join('\n')
          : `<p class="feed-empty">${escapeHtml(mode.empty)}</p>`;
        return `<template data-feed-template="${escapeHtml(mode.id)}">${markup}</template>`;
      })
      .join('\n');
    const configs = feed.modes
      .map((mode) => {
        const payload = {
          id: mode.id,
          label: mode.label,
          description: mode.description,
          pageSize: mode.pageSize,
          totalItems: mode.totalItems,
          totalPages: mode.totalPages,
          currentPage: mode.initialPage,
          nextPage: mode.nextPage,
          baseHref: mode.baseHref,
          manifestHref: mode.manifestHref,
          empty: mode.empty,
        };
        return `<script type="application/json" data-feed-state="${escapeHtml(mode.id)}">${escapeHtml(
          JSON.stringify(payload),
        )}</script>`;
      })
      .join('\n');
    const feedAttributes = ['class="item-feed"', 'data-feed'];
    if (defaultMode) {
      feedAttributes.push(`data-feed-mode="${escapeHtml(defaultMode.id)}"`);
      feedAttributes.push(`data-feed-page="${defaultMode.initialPage}"`);
      feedAttributes.push(`data-feed-total="${defaultMode.totalPages}"`);
      feedAttributes.push(`data-feed-total-items="${defaultMode.totalItems}"`);
      feedAttributes.push(`data-feed-page-size="${defaultMode.pageSize}"`);
      if (defaultMode.nextPage) {
        feedAttributes.push(`data-feed-next="${escapeHtml(defaultMode.nextPage)}"`);
      } else {
        feedAttributes.push('data-feed-complete');
      }
    } else {
      feedAttributes.push('data-feed-mode=""');
      feedAttributes.push('data-feed-page="0"');
      feedAttributes.push('data-feed-total="0"');
      feedAttributes.push('data-feed-total-items="0"');
      feedAttributes.push(`data-feed-page-size="${FEED_PAGE_SIZE}"`);
      feedAttributes.push('data-feed-complete');
    }
    const descriptionText =
      (defaultMode && defaultMode.description) ||
      'Scroll through the latest gifts from across the catalog.';
    feedSection = [
      '<section class="feed-section" id="latest">',
      `<div class="feed-wrapper" data-feed-root data-feed-default="${escapeHtml(defaultMode ? defaultMode.id : '')}">`,
      '<div class="feed-header">',
      '<div class="feed-header-top">',
      '<h2>Live gift feed</h2>',
      `<div class="feed-tabs" role="tablist">${tabs}</div>`,
      '</div>',
      `<p data-feed-description>${escapeHtml(descriptionText)}</p>`,
      '</div>',
      `<div ${feedAttributes.join(' ')}>`,
      `<div class="feed-list" data-feed-list>${defaultMarkup}</div>`,
      '<button class="button feed-load-more" type="button" data-feed-more>Load more gifts</button>',
      '<p class="feed-status" data-feed-status aria-live="polite" hidden></p>',
      '<div class="feed-sentinel" data-feed-sentinel></div>',
      '</div>',
      templates,
      configs,
      '</div>',
      '<noscript><p class="feed-status">Enable JavaScript to load more gifts from the feed.</p></noscript>',
      '</section>',
    ]
      .filter(Boolean)
      .join('\n');
  }

  const content = [heroMarkup, guidesSection, feedSection].filter(Boolean).join('\n');
  return renderWithBase(content);
}

function renderFaqPage() {
  const body = [
    "<h1>Affiliate disclosure</h1>",
    "<p>GrabGifts may earn commissions from qualifying purchases made through outbound links. We only feature items that fit our curated guides.</p>",
    "<p>Questions? Contact us at support@grabgifts.net.</p>",
  ];
  return renderWithBase(body.join("\n"));
}

function filterByTopic(title, items) {
  const t = title.toLowerCase();
  const under = t.match(/under\s+\$(\d+)/i);
  let filtered = items;
  if (under) {
    const cap = Number(under[1]);
    filtered = filtered.filter((i) => priceNumber(i.price) <= cap);
  }
  const tokens = t.split(/\s+/);
  filtered = filtered.filter((i) => {
    const s = `${(i.category || "").toLowerCase()} ${(i.brand || "").toLowerCase()} ${i.title.toLowerCase()}`;
    return tokens.some((tok) => tok.length > 3 && s.includes(tok));
  });
  if (filtered.length < 10) filtered = items.slice(0, 20);
  return filtered.slice(0, 20);
}

function main() {
  const items = JSON.parse(fs.readFileSync(IN, "utf8"));
  const plan = pickTopics(items, 15);

  const ledgerEntries = loadGuideLedger();
  const ledgerMap = new Map(
    ledgerEntries
      .filter((entry) => entry && entry.slug)
      .map((entry) => [entry.slug, entry]),
  );
  let made = 0;
  for (const { title, slug } of plan.topics) {
    const picks = filterByTopic(title, items);
    const picksWithImages = picks.filter((item) => item.image);
    if (picksWithImages.length < 10) continue;
    const polishedTitle = polishGuideTitle(title);
    const html = renderGuidePage(polishedTitle, slug, picksWithImages);
    writeFile(path.join(PUB, "guides", slug, "index.html"), html);
    const summary = stripBannedPhrases(picksWithImages[0]?.title || `Top picks for ${polishedTitle}`);
    ledgerMap.set(slug, {
      title: polishedTitle,
      slug,
      summary,
      createdAt: new Date().toISOString(),
    });
    made++;
  }

  const updatedLedger = Array.from(ledgerMap.values())
    .filter((entry) => entry && entry.slug && entry.title)
    .map((entry) => ({
      slug: entry.slug,
      title: polishGuideTitle(entry.title),
      summary: entry.summary ? stripBannedPhrases(entry.summary) : '',
      createdAt: entry.createdAt || new Date().toISOString(),
    }))
    .sort((a, b) => parseTimestamp(b.createdAt) - parseTimestamp(a.createdAt));
  const trimmedLedger = updatedLedger.slice(0, 120);
  saveGuideLedger(trimmedLedger);

  const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const guidesForHome = trimmedLedger.filter((entry) => parseTimestamp(entry.createdAt) >= oneWeekAgo);
  const guidesFallback = guidesForHome.length ? guidesForHome : trimmedLedger.slice(0, 6);
  const guidesForDisplay = guidesFallback.slice(0, 12);

  const feedState = writeFeedData(items);
  const homeHtml = renderHomePage(guidesForDisplay, feedState);
  writeFile(path.join(PUB, "index.html"), homeHtml);
  const faqHtml = renderFaqPage();
  writeFile(path.join(PUB, "faq", "index.html"), faqHtml);

  if (made < 15) {
    console.error("Generated guides:", made);
    process.exit(1);
  }
  plan.commit();
  console.info("Generated guides:", made);
}

main();
