import fs from "node:fs";
import path from "node:path";
import { pickTopics } from "./topics.mjs";
import { priceNumber } from "./util.mjs";

const IN = path.join("data", "items.json");
const PUB = "public";
const SITE_NAME = "GrabGifts";
const SITE_DESCRIPTION =
  "GrabGifts curates trending products daily. Smart picks, clean layouts, zero clutter.";

const BASE_TEMPLATE_PATH = path.join("templates", "base.html");
const HEADER_PATH = path.join("templates", "partials", "header.html");
const FOOTER_PATH = path.join("templates", "partials", "footer.html");
const THEME_PATH = path.join(PUB, "assets", "theme.css");
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

function renderHomePage(guides) {
  const intro = [
    `<h1>${escapeHtml(SITE_NAME)}</h1>`,
    `<p>${escapeHtml(stripBannedPhrases(SITE_DESCRIPTION))}</p>`,
  ];
  let cards = "";
  if (guides.length) {
    const items = guides.slice(0, 8).map((guide) => {
      const summary = guide.summary
        ? escapeHtml(stripBannedPhrases(guide.summary))
        : "Explore thoughtful ideas for every list.";
      const displayTitle = polishGuideTitle(guide.title);
      return [
        "<li class=\"card\">",
        `<a href=\"/guides/${escapeHtml(guide.slug)}/\">`,
        `<h3>${escapeHtml(displayTitle)}</h3>`,
        `<p>${summary}</p>`,
        "</a>",
        "</li>",
      ].join("");
    });
    cards = `<ol class=\"grid\">${items.join("\n")}\n</ol>`;
  }
  const content = cards ? [...intro, cards].join("\n") : intro.join("\n");
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

  const guidesForHome = [];
  let made = 0;
  for (const { title, slug } of plan.topics) {
    const picks = filterByTopic(title, items);
    const picksWithImages = picks.filter((item) => item.image);
    if (picksWithImages.length < 10) continue;
    const polishedTitle = polishGuideTitle(title);
    const html = renderGuidePage(polishedTitle, slug, picksWithImages);
    writeFile(path.join(PUB, "guides", slug, "index.html"), html);
    guidesForHome.push({
      title: polishedTitle,
      slug,
      summary: picksWithImages[0]?.title || `Top picks for ${polishedTitle}`,
    });
    made++;
  }

  const homeHtml = renderHomePage(guidesForHome);
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
