import fs from "node:fs";
import path from "node:path";
import { pickTopics } from "./topics.mjs";
import { priceNumber } from "./util.mjs";

const IN = path.join("data", "items.json");
const PUB = "public";
const SITE_NAME = "GrabGifts";
const SITE_URL = "https://grabgifts.net";
const SITE_DESCRIPTION = "Gift ideas for every fan, friend, and family member.";

const HEADER_PATH = path.join("templates", "partials", "header.html");
const FOOTER_PATH = path.join("templates", "partials", "footer.html");
const THEME_PATH = path.join(PUB, "assets", "theme.css");
const PROTECTED_FILES = new Set(
  [HEADER_PATH, FOOTER_PATH, THEME_PATH].map((p) => path.resolve(p)),
);

const { doctype: DOC_TYPE, markup: HEADER_PARTIAL } = loadHeaderPartial(
  fs.readFileSync(HEADER_PATH, "utf8"),
);
const FOOTER_PARTIAL = normalizePartial(fs.readFileSync(FOOTER_PATH, "utf8"));

function loadHeaderPartial(raw) {
  const cleaned = raw.replace(/^\ufeff/, "");
  const match = cleaned.match(/^\s*<!doctype html>\s*/i);
  let doctype = "<!doctype html>";
  let markup = cleaned;
  if (match) {
    doctype = match[0].trim();
    markup = cleaned.slice(match[0].length);
  }
  return { doctype, markup: normalizePartial(markup) };
}

function normalizePartial(markup) {
  const trimmed = markup.trim();
  return trimmed ? `${trimmed}\n` : "";
}

function escapeHtml(input) {
  return String(input)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function canonicalUrl(pathname) {
  const base = new URL(SITE_URL);
  base.pathname = pathname.startsWith("/") ? pathname : `/${pathname}`;
  base.search = "";
  base.hash = "";
  return base.toString();
}

function ensureNotProtected(targetPath) {
  const resolved = path.resolve(targetPath);
  if (PROTECTED_FILES.has(resolved)) {
    throw new Error("Protected layout files may not be modified by content builds.");
  }
}

function writeFile(target, html) {
  ensureNotProtected(target);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, html);
}

function pageShell({ title, description, canonicalPath, bodyContent, extraHead = [] }) {
  const canonical = canonicalUrl(canonicalPath);
  const headParts = [
    "<meta charset=\"utf-8\">",
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
    `<title>${escapeHtml(title)}</title>`,
    `<link rel=\"canonical\" href=\"${canonical}\">`,
    `<meta name=\"description\" content=\"${escapeHtml(description)}\">`,
    "<meta name=\"robots\" content=\"index,follow\">",
    "<link rel=\"stylesheet\" href=\"/assets/theme.css\">",
    ...extraHead,
  ];
  return `${DOC_TYPE}\n<html lang=\"en\"><head>${headParts.join("\n")}</head><body>\n${HEADER_PARTIAL}<main><div class=\"wrap\">\n${bodyContent}\n</div></main>\n${FOOTER_PARTIAL}</body></html>`;
}

function renderGuideCard(item) {
  const parts = ["<li class=\"card\">"];
  parts.push(
    `<a href=\"${escapeHtml(item.url)}\" rel=\"sponsored nofollow noopener\" target=\"_blank\">`,
  );
  if (item.image) {
    parts.push(
      `<img src=\"${escapeHtml(item.image)}\" alt=\"${escapeHtml(item.title)}\" loading=\"lazy\">`,
    );
  }
  parts.push(`<h3>${escapeHtml(item.title)}</h3>`);
  if (item.price) {
    parts.push(`<p class=\"price\">${escapeHtml(item.price)}</p>`);
  }
  if (item.updatedAt) {
    const date = escapeHtml(item.updatedAt.split("T")[0]);
    parts.push(`<p class=\"updated\">Updated ${date}</p>`);
  }
  parts.push("</a></li>");
  return parts.join("");
}

function renderGuidePage(title, slug, items) {
  const cards = items.map((item) => renderGuideCard(item)).join("\n");
  const disclosure =
    "<p class=\"disclosure\">Affiliate disclosure: We may earn from qualifying purchases.</p>";
  const body = [`<h1>${escapeHtml(title)}</h1>`, disclosure, `<ol class=\"grid\">${cards}</ol>`];
  const ld = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: title,
    url: canonicalUrl(`/guides/${slug}/`),
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: item.url,
      name: item.title,
    })),
  };
  const extraHead = [`<script type=\"application/ld+json\">${JSON.stringify(ld)}</script>`];
  const description = `Top gift ideas for ${title}.`;
  return pageShell({
    title: `${title} — ${SITE_NAME}`,
    description,
    canonicalPath: `/guides/${slug}/`,
    bodyContent: body.join("\n"),
    extraHead,
  });
}

function renderHomePage(guides) {
  const intro = [
    `<h1>${escapeHtml(SITE_NAME)}</h1>`,
    `<p>${escapeHtml(SITE_DESCRIPTION)}</p>`,
  ];
  let cards = "<p class=\"disclosure\">Fresh guides are published daily.</p>";
  if (guides.length) {
    const items = guides.slice(0, 8).map((guide) => {
      const summary = guide.summary ? escapeHtml(guide.summary) : "Discover our latest picks.";
      return [
        "<li class=\"card\">",
        `<a href=\"/guides/${escapeHtml(guide.slug)}/\">`,
        `<h3>${escapeHtml(guide.title)}</h3>`,
        `<p>${summary}</p>`,
        "</a>",
        "</li>",
      ].join("");
    });
    cards = `<ol class=\"grid\">${items.join("\n")}\n</ol>`;
  }
  return pageShell({
    title: `${SITE_NAME} — Gift ideas & buying guides`,
    description: SITE_DESCRIPTION,
    canonicalPath: "/",
    bodyContent: [...intro, cards].join("\n"),
  });
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
    if (picks.length < 10) continue;
    const html = renderGuidePage(title, slug, picks);
    writeFile(path.join(PUB, "guides", slug, "index.html"), html);
    guidesForHome.push({
      title,
      slug,
      summary: picks[0]?.title || `Top picks for ${title}`,
    });
    made++;
  }

  const homeHtml = renderHomePage(guidesForHome);
  writeFile(path.join(PUB, "index.html"), homeHtml);

  if (made < 15) {
    console.error("Generated guides:", made);
    process.exit(1);
  }
  plan.commit();
  console.info("Generated guides:", made);
}

main();
