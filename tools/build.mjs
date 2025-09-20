import fs from "node:fs";
import path from "node:path";
import slugify from "slugify";
import { pickTopics } from "./topics.mjs";
import { hash, priceNumber } from "./util.mjs";

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

function formatUpdatedLabel(value) {
  const timestamp = parseTimestamp(value);
  if (!timestamp) return "";
  return new Date(timestamp).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function prepareProduct(raw) {
  if (!raw) return null;
  const title = String(raw.title || "").trim();
  const url = String(raw.url || "").trim();
  const image = String(raw.image || "").trim();
  if (!title || !url || !image) return null;

  let id = String(raw.id || "").trim();
  if (!id) {
    id = hash(url || title);
  }

  const slugSeed = [title, id].filter(Boolean).join("-");
  let slug = slugify(slugSeed, { lower: true, strict: true });
  if (!slug) {
    slug = slugify(`${title}-${hash(slugSeed || url || title)}`, {
      lower: true,
      strict: true,
    });
  }
  if (!slug) {
    slug = `item-${hash(slugSeed || url || title)}`;
  }

  const priceTextRaw = raw.price_text || raw.price;
  const priceText = typeof priceTextRaw === "number" ? `$${priceTextRaw.toFixed(2)}` : String(priceTextRaw || "").trim();
  const brand = raw.brand ? String(raw.brand).trim() : "";
  const category = raw.category ? String(raw.category).trim() : raw.category;
  const updatedAt = raw.updated_at || raw.updatedAt || new Date().toISOString();
  const ratingValue = Number(raw.rating);
  const rating = Number.isFinite(ratingValue) && ratingValue > 0 ? Number(ratingValue.toFixed(1)) : null;
  const descriptionSource = raw.description || raw.blurb || "";
  const description = stripBannedPhrases(descriptionSource);

  return {
    ...raw,
    id,
    title,
    url,
    image,
    slug,
    pageUrl: `/products/${slug}/`,
    priceText,
    brand,
    category,
    updatedAt,
    rating,
    description,
  };
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

function renderWithBase(content, { head = "" } = {}) {
  let html = BASE_TEMPLATE;
  const headMarkup = head || "";
  html = html.replace(/\{\{\s*head\|safe\s*\}\}/g, headMarkup);
  html = html.replace(/\{\{\s*head\s*\}\}/g, escapeHtml(headMarkup));
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
  const parts = ['<article class="card">'];
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
  parts.push("</a>");
  parts.push("</article>");
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

function renderProductPreviewCard(item) {
  if (!item || !item.title || !item.image) return "";
  const metaParts = [];
  const category = formatCategory(item);
  if (category) metaParts.push(escapeHtml(category));
  if (item.brand) metaParts.push(escapeHtml(item.brand));
  const meta = metaParts.length
    ? `<p class="feed-card-meta">${metaParts.join(" • ")}</p>`
    : "";
  const priceDisplay = item.priceText || item.price;
  const price = priceDisplay ? `<p class="feed-card-price">${escapeHtml(priceDisplay)}</p>` : "";
  const href = item.pageUrl || item.url || "#";
  const isInternal = href.startsWith("/");
  const linkAttrs = isInternal
    ? `class="feed-card-link" href="${escapeHtml(href)}"`
    : `class="feed-card-link" href="${escapeHtml(href)}" rel="sponsored nofollow noopener" target="_blank"`;
  const idAttr = item.id ? ` data-product-id="${escapeHtml(String(item.id))}"` : "";
  const media = `<div class="feed-card-media"><img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}" loading="lazy"></div>`;
  return [
    `<article class="feed-card" data-home-product-card="true"${idAttr}>`,
    `<a ${linkAttrs}>`,
    media,
    '<div class="feed-card-body">',
    meta,
    `<h3 class="feed-card-title">${escapeHtml(item.title)}</h3>`,
    price,
    '</div>',
    '</a>',
    '</article>',
  ]
    .filter(Boolean)
    .join("\n");
}

function renderProductPage(product) {
  if (!product || !product.title || !product.slug) return "";
  const tags = [];
  const category = formatCategory(product);
  if (category) tags.push(escapeHtml(category));
  if (product.brand) tags.push(escapeHtml(product.brand));
  const tagsMarkup = tags.length
    ? `<ul class="product-card__tags">${tags.map((tag) => `<li>${tag}</li>`).join("")}</ul>`
    : "";
  const priceDisplay = product.priceText || product.price;
  const priceMarkup = priceDisplay ? `<p class="product-card__price">${escapeHtml(priceDisplay)}</p>` : "";
  const ratingValue = Number(product.rating);
  const ratingLabel = Number.isFinite(ratingValue) && ratingValue > 0 ? ratingValue.toFixed(1).replace(/\.0$/, "") : "";
  const ratingMarkup = ratingLabel
    ? `<div class="product-card__rating" aria-label="Rated ${escapeHtml(ratingLabel)} out of 5"><span class="product-card__rating-icon" aria-hidden="true">★</span><span class="product-card__rating-score">${escapeHtml(ratingLabel)}</span></div>`
    : "";
  const descriptionText = product.description && String(product.description).trim()
    ? String(product.description).trim()
    : "Check the listing for the latest details.";
  const descriptionMarkup = escapeHtml(descriptionText);
  const updatedLabel = formatUpdatedLabel(product.updatedAt);
  const updatedMarkup = updatedLabel
    ? `<p class="product-card__updated">Updated ${escapeHtml(updatedLabel)}</p>`
    : "";
  const imageMarkup = product.image
    ? `<div class="product-card__media"><img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.title)}" loading="lazy"></div>`
    : "";
  const body = [
    '<article class="product-card product-card--page">',
    imageMarkup,
    '<div class="product-card__body">',
    tagsMarkup,
    `<h1 class="product-card__title">${escapeHtml(product.title)}</h1>`,
    priceMarkup,
    ratingMarkup,
    `<p class="product-card__description">${descriptionMarkup}</p>`,
    `<a class="button product-card__cta" rel="sponsored nofollow noopener" target="_blank" href="${escapeHtml(product.url)}">Shop now</a>`,
    updatedMarkup,
    '</div>',
    '</article>',
  ]
    .filter(Boolean)
    .join("\n");

  const head = [
    `<title>${escapeHtml(product.title)} – ${escapeHtml(SITE_NAME)}</title>`,
    `<meta name="description" content="${escapeHtml(descriptionText)}">`,
    `<link rel="canonical" href="/products/${escapeHtml(product.slug)}/">`,
  ].join("\n");

  return renderWithBase(body, { head });
}

function renderProductsIndexPage(products) {
  const cards = products
    .map((item) => renderProductPreviewCard(item))
    .filter(Boolean)
    .join("\n");
  const sections = [
    '<section class="page-header">',
    '<h1>All products</h1>',
    '<p>Every grabgifts find in one catalog.</p>',
    '</section>',
  ];
  if (cards) {
    sections.push('<section class="feed-section">');
    sections.push('<div class="feed-list" data-product-grid>');
    sections.push(cards);
    sections.push('</div>');
    sections.push('</section>');
  } else {
    sections.push('<p class="empty-state">No products are available right now.</p>');
  }

  const head = [
    `<title>Products – ${escapeHtml(SITE_NAME)}</title>`,
    '<meta name="description" content="Browse every product in the grabgifts catalog.">',
    '<link rel="canonical" href="/products/">',
  ].join("\n");

  return renderWithBase(sections.join("\n"), { head });
}

function writeProductPages(products) {
  if (!Array.isArray(products) || !products.length) {
    return;
  }
  const sorted = products.slice().sort((a, b) => {
    const diff = parseTimestamp(b.updatedAt || b.updated_at) - parseTimestamp(a.updatedAt || a.updated_at);
    if (diff !== 0) return diff;
    return (a.title || "").localeCompare(b.title || "");
  });
  const indexHtml = renderProductsIndexPage(sorted);
  writeFile(path.join(PUB, "products", "index.html"), indexHtml);
  for (const product of sorted) {
    if (!product || !product.slug) continue;
    const html = renderProductPage(product);
    if (!html) continue;
    writeFile(path.join(PUB, "products", product.slug, "index.html"), html);
  }
}
function renderGuidePage(title, slug, items, summary) {
  const polishedTitle = polishGuideTitle(title);
  const description = stripBannedPhrases(summary || `Explore curated picks for ${polishedTitle}.`);
  const cards = items
    .map((item) => renderGuideCard(item))
    .filter(Boolean)
    .join("\n");
  const sections = [
    '<section class="panel page-section guide-page">',
    '<div class="page-header section-heading">',
    `<h1>${escapeHtml(polishedTitle)}</h1>`,
    `<p>${escapeHtml(description)}</p>`,
    '</div>',
  ];
  if (cards) {
    sections.push(`<div class=\"grid guide-grid\">${cards}</div>`);
  } else {
    sections.push('<p class="empty-state">No items are available for this guide right now.</p>');
  }
  sections.push('</section>');
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

function renderHomePage(guides, feed, products, totalGuideCount = 0) {
  const hero = ['<section class="hero">', `<h1>${escapeHtml(SITE_NAME)}</h1>`];
  const description = stripBannedPhrases(SITE_DESCRIPTION);
  if (description) {
    hero.push(`<p>${escapeHtml(description)}</p>`);
  }

  const guideCount =
    Number.isFinite(totalGuideCount) && totalGuideCount > 0
      ? totalGuideCount
      : Array.isArray(guides)
      ? guides.length
      : 0;

  let productTotal = 0;
  let latestTimestamp = 0;
  const brandSet = new Set();
  if (Array.isArray(products)) {
    productTotal = products.length;
    for (const item of products) {
      if (!item) continue;
      if (item.brand) {
        brandSet.add(item.brand);
      }
      const timestamp = parseTimestamp(item.updated_at || item.updatedAt);
      if (timestamp > latestTimestamp) {
        latestTimestamp = timestamp;
      }
    }
  }
  const brandTotal = brandSet.size;
  const lastRefreshLabel = latestTimestamp
    ? new Date(latestTimestamp).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : '';

  const heroStats = [];
  if (guideCount) {
    heroStats.push(
      '<li>' +
        `<span class="hero-meta__value">${escapeHtml(guideCount.toLocaleString('en-US'))}</span>` +
        '<span class="hero-meta__label">Guides live</span>' +
        '</li>',
    );
  }
  if (productTotal) {
    heroStats.push(
      '<li>' +
        `<span class="hero-meta__value">${escapeHtml(productTotal.toLocaleString('en-US'))}</span>` +
        '<span class="hero-meta__label">Products tracked</span>' +
        '</li>',
    );
  }
  if (brandTotal) {
    heroStats.push(
      '<li>' +
        `<span class="hero-meta__value">${escapeHtml(brandTotal.toLocaleString('en-US'))}</span>` +
        '<span class="hero-meta__label">Brands covered</span>' +
        '</li>',
    );
  }
  if (lastRefreshLabel) {
    heroStats.push(
      '<li>' +
        `<span class="hero-meta__value">${escapeHtml(lastRefreshLabel)}</span>` +
        '<span class="hero-meta__label">Last refresh</span>' +
        '</li>',
    );
  }
  if (heroStats.length) {
    hero.push('<ul class="hero-meta" aria-label="Grabgifts highlights">');
    hero.push(heroStats.join('\n'));
    hero.push('</ul>');
  }

  hero.push('<div class="hero-actions">');
  hero.push('<a class="button" href="/guides/">Explore today\'s drops</a>');
  hero.push('<a class="button button-secondary" href="/surprise/">Spin up a surprise</a>');
  hero.push('<a class="button button-ghost" href="/changelog/">See the live changelog</a>');
  hero.push('</div>');

  const heroSupport = [
    'Automation keeps the catalog deduped and stage-ready.',
    'Conversion copy, SEO, and imagery tuned for high-intent moments.',
    'Affiliate links ship with compliance-first guardrails.',
  ];
  if (heroSupport.length) {
    hero.push('<div class="hero-support">');
    hero.push('<p class="hero-support__lede">What each refresh delivers</p>');
    hero.push('<ul class="hero-support__list">');
    hero.push(heroSupport.map((line) => `<li>${escapeHtml(line)}</li>`).join('\n'));
    hero.push('</ul>');
    hero.push('</div>');
  }

  hero.push('</section>');
  const heroMarkup = hero.filter(Boolean).join('\n');

  const sortedGuides = Array.isArray(guides) ? guides.slice() : [];
  sortedGuides.sort((a, b) => {
    const diff = parseTimestamp(b.createdAt) - parseTimestamp(a.createdAt);
    if (diff !== 0) return diff;
    return (polishGuideTitle(a.title) || '').localeCompare(polishGuideTitle(b.title) || '');
  });
  const guideCards = [];
  sortedGuides.forEach((guide, index) => {
    if (!guide || !guide.slug || !guide.title) return;
    const attrs = ['class="card"', 'data-home-guide-card="true"'];
    if (index >= 5) {
      attrs.push('hidden');
      attrs.push('data-home-guide-hidden="true"');
    }
    const title = polishGuideTitle(guide.title);
    const teaser = stripBannedPhrases(
      guide.summary || `Dive into the latest ${title} recommendations.`,
    );
    guideCards.push(
      `<article ${attrs.join(' ')}>` +
        `<h2><a href=\"/guides/${escapeHtml(guide.slug)}/\">${escapeHtml(title)}</a></h2>` +
        `<p>${escapeHtml(teaser)}</p>` +
        '</article>',
    );
  });
  const guidesSectionParts = [
    '<section id="guide-list" class="panel section-block" data-home-guides>',
    '<div class="page-header section-heading">',
    "<h2>Today's drops</h2>",
    '<p>Browse the guides refreshed for the latest grabgifts catalog.</p>',
    '</div>',
  ];
  if (guideCards.length) {
    guidesSectionParts.push('<div class="grid guide-grid">');
    guidesSectionParts.push(guideCards.join('\n'));
    guidesSectionParts.push('</div>');
    if (guideCards.length > 5) {
      guidesSectionParts.push(
        '<button class="button" type="button" data-home-guide-toggle="true" aria-expanded="false">See more guides</button>',
      );
    }
  } else {
    guidesSectionParts.push('<p class="empty-state">Guides are being prepared. Check back soon.</p>');
  }
  guidesSectionParts.push('</section>');
  const guidesSection = guidesSectionParts.join('\n');

  const sortedProducts = Array.isArray(products) ? products.slice() : [];
  sortedProducts.sort((a, b) => {
    const diff = parseTimestamp(b.updated_at || b.updatedAt) - parseTimestamp(a.updated_at || a.updatedAt);
    if (diff !== 0) return diff;
    return (a.title || '').localeCompare(b.title || '');
  });
  const productInitial = [];
  const productRemaining = [];
  sortedProducts.forEach((item) => {
    const card = renderProductPreviewCard(item);
    if (!card) return;
    if (productInitial.length < 10) {
      productInitial.push(card);
    } else {
      productRemaining.push(card);
    }
  });

  let productSection = '';
  if (productInitial.length) {
    const sectionParts = [
      '<section class="panel section-block feed-section" id="latest-products" data-home-products data-product-batch="6">',
      '<div class="page-header section-heading">',
      '<h2>Fresh product drops</h2>',
      '<p>Catch the newest arrivals across the catalog.</p>',
      '</div>',
      `<div class="feed-list" data-product-grid>${productInitial.join('\n')}</div>`,
    ];
    if (productRemaining.length) {
      sectionParts.push('<div class="feed-sentinel" data-product-sentinel></div>');
      sectionParts.push(
        '<script type="application/json" data-product-source>' +
          escapeHtml(JSON.stringify(productRemaining)) +
          '</script>',
      );
    }
    sectionParts.push('</section>');
    productSection = sectionParts.join('\n');
  } else {
    productSection = [
      '<section class="panel section-block feed-section" id="latest-products">',
      '<div class="page-header section-heading">',
      '<h2>Fresh product drops</h2>',
      '<p>New arrivals will appear here soon.</p>',
      '</div>',
      '<p class="empty-state">We will restock this feed after the next automation run.</p>',
      '</section>',
    ].join('\n');
  }

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
      '<section class="panel section-block feed-section" id="latest">',
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

  const content = [heroMarkup, guidesSection, productSection, feedSection].filter(Boolean).join('\n');
  return renderWithBase(content);
}

function renderFaqPage() {
  const body = [
    '<section class="panel page-section">',
    '<div class="page-header section-heading">',
    '<h1>FAQ &amp; disclosure</h1>',
    '<p>Learn how grabgifts curates daily picks and how affiliate links support the project.</p>',
    '</div>',
    '<div class="prose">',
    '<p>GrabGifts may earn commissions from qualifying purchases made through outbound links. We only feature items that fit our curated guides.</p>',
    '<p>Questions? Contact us at <a href="mailto:support@grabgifts.net">support@grabgifts.net</a>.</p>',
    '</div>',
    '</section>',
  ];
  return renderWithBase(body.join('\n'));
}

function renderGuidesIndexPage(guides) {
  const sorted = Array.isArray(guides) ? guides.slice() : [];
  sorted.sort((a, b) => {
    return (polishGuideTitle(a.title) || '').localeCompare(polishGuideTitle(b.title) || '');
  });
  const cards = sorted
    .filter((guide) => guide && guide.slug && guide.title)
    .map((guide) => {
      const title = polishGuideTitle(guide.title);
      const teaser = stripBannedPhrases(
        guide.summary || `Explore what made ${title} trend on grabgifts.`,
      );
      return (
        '<article class="card">' +
        `<h2><a href=\"/guides/${escapeHtml(guide.slug)}/\">${escapeHtml(title)}</a></h2>` +
        `<p>${escapeHtml(teaser)}</p>` +
        '</article>'
      );
    });
  const body = [
    '<section class="panel page-section">',
    '<div class="page-header section-heading">',
    '<h1>All guides</h1>',
    '<p>Every grabgifts collection in one place.</p>',
    '</div>',
  ];
  if (cards.length) {
    body.push('<div class="grid guide-grid">');
    body.push(cards.join('\n'));
    body.push('</div>');
  } else {
    body.push('<p class="empty-state">No guides are available right now.</p>');
  }
  body.push('</section>');
  return renderWithBase(body.join('\n'));
}

function renderSurprisePage(guides) {
  const entries = Array.isArray(guides) ? guides.filter((guide) => guide && guide.slug) : [];
  const links = entries.map((guide) => ({
    url: `/guides/${guide.slug}/`,
    title: polishGuideTitle(guide.title),
  }));
  const body = [
    '<section class="panel page-section">',
    '<div class="page-header section-heading">',
    '<h1>Spin up a surprise</h1>',
    '<p>We send you to a random guide from today\'s drops.</p>',
    '</div>',
  ];
  if (links.length) {
    const urls = links.map((entry) => entry.url);
    body.push('<div class="prose">');
    body.push("<p>Hold tight—we're picking something for you.</p>");
    body.push(
      `<script>const guides = ${escapeHtml(JSON.stringify(urls))};if(guides.length){const target = guides[Math.floor(Math.random()*guides.length)];window.location.href = target;}</script>`,
    );
    const listItems = links
      .map((entry) => `<li><a href=\"${escapeHtml(entry.url)}\">${escapeHtml(entry.title)}</a></li>`)
      .join('');
    body.push(
      `<noscript><p>Enable JavaScript to jump automatically. Until then, pick a guide below.</p><ul class=\"link-list\">${listItems}</ul></noscript>`,
    );
    body.push('</div>');
  } else {
    body.push('<p class="empty-state">No guides are available right now. Check back soon.</p>');
  }
  body.push('</section>');
  return renderWithBase(body.join('\n'));
}

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatTimelineLabel(value) {
  const timestamp = parseTimestamp(value);
  if (!timestamp) return '';
  const date = new Date(timestamp);
  const month = MONTH_NAMES[date.getUTCMonth()] || '';
  const day = String(date.getUTCDate()).padStart(2, '0');
  const year = date.getUTCFullYear();
  const hours = String(date.getUTCHours()).padStart(2, '0');
  const minutes = String(date.getUTCMinutes()).padStart(2, '0');
  return `${month} ${day}, ${year} ${hours}:${minutes} UTC`;
}

function renderChangelogPage(guides) {
  const entries = Array.isArray(guides) ? guides.slice() : [];
  entries.sort((a, b) => parseTimestamp(b.createdAt) - parseTimestamp(a.createdAt));
  const items = entries
    .filter((guide) => guide && guide.slug && guide.title)
    .map((guide) => {
      const timestamp = parseTimestamp(guide.createdAt);
      const iso = timestamp ? new Date(timestamp).toISOString() : '';
      const label = formatTimelineLabel(guide.createdAt);
      const title = polishGuideTitle(guide.title);
      return (
        '<li>' +
        `<time datetime=\"${escapeHtml(iso)}\">${escapeHtml(label)}</time>` +
        `<a href=\"/guides/${escapeHtml(guide.slug)}/\">${escapeHtml(title)}</a>` +
        '</li>'
      );
    });
  const body = [
    '<section class="panel page-section">',
    '<div class="page-header section-heading">',
    '<h1>Live changelog</h1>',
    '<p>Follow every update we push into grabgifts.</p>',
    '</div>',
  ];
  if (items.length) {
    body.push('<ul class="timeline">');
    body.push(items.join('\n'));
    body.push('</ul>');
  } else {
    body.push('<p class="empty-state">No updates yet. Check back soon.</p>');
  }
  body.push('</section>');
  return renderWithBase(body.join('\n'));
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
  const rawItems = JSON.parse(fs.readFileSync(IN, "utf8"));
  const products = Array.isArray(rawItems)
    ? rawItems
        .map((item) => prepareProduct(item))
        .filter((item) => item && item.title && item.url)
    : [];
  const plan = pickTopics(products, 15);

  const ledgerEntries = loadGuideLedger();
  const ledgerMap = new Map(
    ledgerEntries
      .filter((entry) => entry && entry.slug)
      .map((entry) => [entry.slug, entry]),
  );
  let made = 0;
  for (const { title, slug } of plan.topics) {
    const picks = filterByTopic(title, products);
    const picksWithImages = picks.filter((item) => item.image);
    if (picksWithImages.length < 10) continue;
    const polishedTitle = polishGuideTitle(title);
    const summary = stripBannedPhrases(
      picksWithImages[0]?.title || `Top picks for ${polishedTitle}`,
    );
    const html = renderGuidePage(polishedTitle, slug, picksWithImages, summary);
    writeFile(path.join(PUB, "guides", slug, "index.html"), html);
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

  const feedState = writeFeedData(products);
  const homeHtml = renderHomePage(guidesForDisplay, feedState, products, trimmedLedger.length);
  writeFile(path.join(PUB, "index.html"), homeHtml);
  const guidesIndexHtml = renderGuidesIndexPage(trimmedLedger);
  writeFile(path.join(PUB, "guides", "index.html"), guidesIndexHtml);
  const surpriseHtml = renderSurprisePage(trimmedLedger);
  writeFile(path.join(PUB, "surprise", "index.html"), surpriseHtml);
  const changelogHtml = renderChangelogPage(trimmedLedger);
  writeFile(path.join(PUB, "changelog", "index.html"), changelogHtml);
  const faqHtml = renderFaqPage();
  writeFile(path.join(PUB, "faq", "index.html"), faqHtml);
  writeProductPages(products);

  if (made < 15) {
    console.error("Generated guides:", made);
    process.exit(1);
  }
  plan.commit();
  console.info("Generated guides:", made);
}

main();
