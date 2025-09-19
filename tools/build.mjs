import fs from "node:fs";
import path from "node:path";
import { pickTopics } from "./topics.mjs";
import { priceNumber } from "./util.mjs";

const IN = path.join("data", "items.json");
const PUB = "public";
const SITE_NAME = "GrabGifts";
const SITE_URL = "https://grabgifts.net";
const SITE_DESCRIPTION = "Gift ideas for every fan, friend, and family member.";

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
    throw new Error("Protected layout file");
  }
}

function writeFile(target, html) {
  ensureNotProtected(target);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, html);
}

function renderWithBase({ content, pageTitle, headExtras = [] }) {
  const safeTitle = (pageTitle && pageTitle.trim()) || SITE_NAME;
  let html = BASE_TEMPLATE;
  html = html.replace(
    /\{\{\s*page_title\s+or\s+"GrabGifts"\s*\}\}/g,
    escapeHtml(safeTitle),
  );
  html = html.replace(/\{\{\s*content\|safe\s*\}\}/g, content);
  html = html.replace(/\{\{\s*content\s*\}\}/g, content);
  if (headExtras.length) {
    const block = headExtras.map((tag) => `  ${tag}`).join("\n");
    html = html.replace("</head>", `${block}\n</head>`);
  }
  return html;
}

function renderDocument({
  title,
  description,
  canonicalPath,
  bodyContent,
  extraHead = [],
}) {
  const canonical = canonicalUrl(canonicalPath);
  const safeDescription = escapeHtml(description);
  const headParts = [
    `<link rel=\"canonical\" href=\"${canonical}\">`,
    `<meta name=\"description\" content=\"${safeDescription}\">`,
    "<meta name=\"robots\" content=\"index,follow\">",
    "<meta property=\"og:type\" content=\"website\">",
    `<meta property=\"og:title\" content=\"${escapeHtml(title)}\">`,
    `<meta property=\"og:description\" content=\"${safeDescription}\">`,
    `<meta property=\"og:url\" content=\"${canonical}\">`,
    `<meta property=\"og:site_name\" content=\"${escapeHtml(SITE_NAME)}\">`,
    "<meta name=\"twitter:card\" content=\"summary_large_image\">",
    `<meta name=\"twitter:title\" content=\"${escapeHtml(title)}\">`,
    `<meta name=\"twitter:description\" content=\"${safeDescription}\">`,
    `<meta name=\"twitter:url\" content=\"${canonical}\">`,
    `<link rel=\"alternate\" type=\"application/rss+xml\" title=\"${escapeHtml(
      SITE_NAME,
    )} RSS\" href=\"/rss.xml\">`,
    ...extraHead,
  ];
  return renderWithBase({ content: bodyContent, pageTitle: title, headExtras: headParts });
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
  return renderDocument({
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
  return renderDocument({
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
