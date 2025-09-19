import fs from "node:fs";
import path from "node:path";
import fetch from "node-fetch";

const ROOT = process.cwd();
const PUBLIC_DIR = path.join(ROOT, "public");
const THEME_PATH = path.join(PUBLIC_DIR, "assets", "theme.css");
const BANNED_PHRASES = ["fresh drops", "active vibes"];
const PRODUCT_IMAGE_LIMIT = 100;
const NAV_LINKS = [
  "Home",
  "For Him",
  "For Her",
  "Tech",
  "Gamers",
  "Fandom",
  "Homebody",
  "Guides",
  "FAQ",
];

function escapeRegExp(input) {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function readHtml(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function gatherHtmlFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...gatherHtmlFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".html")) {
      files.push(fullPath);
    }
  }
  return files;
}

function ensureStylesheetLink(html, filePath) {
  const matches = html.match(/<link[^>]+rel=["']stylesheet["'][^>]*>/gi) || [];
  if (matches.length !== 1) {
    throw new Error(`Expected exactly one stylesheet link in ${filePath}, found ${matches.length}`);
  }
  if (!/href=["']\/assets\/theme\.css["']/.test(matches[0])) {
    throw new Error(`Stylesheet link must point to /assets/theme.css in ${filePath}`);
  }
}

function ensureNoStyleTags(html, filePath) {
  if (/<style\b/i.test(html)) {
    throw new Error(`Inline <style> tag detected in ${filePath}`);
  }
}

function ensureHeaderFooter(html, filePath) {
  if (!/<header[^>]*class=["']site-header["']/i.test(html)) {
    throw new Error(`Missing site header in ${filePath}`);
  }
  if (!html.includes('<img src="/assets/grabgifts.svg"')) {
    throw new Error(`Header logo not found in ${filePath}`);
  }
  const navMatch = html.match(/<nav class=["']site-nav["'][^>]*>([\s\S]*?)<\/nav>/i);
  if (!navMatch) {
    throw new Error(`Primary navigation missing in ${filePath}`);
  }
  const linkMatches = Array.from(navMatch[1].matchAll(/<a[^>]*>([^<]+)<\/a>/gi)).map((match) =>
    match[1].trim(),
  );
  for (const expected of NAV_LINKS) {
    if (!linkMatches.includes(expected)) {
      throw new Error(`Navigation link "${expected}" missing in ${filePath}`);
    }
  }
  const footerMatch = html.match(/<footer[^>]*class=["']site-footer["'][^>]*>([\s\S]*?)<\/footer>/i);
  if (!footerMatch) {
    throw new Error(`Missing site footer in ${filePath}`);
  }
  if (!/href=["']\/faq\//i.test(footerMatch[1])) {
    throw new Error(`Footer must include a /faq/ link in ${filePath}`);
  }
}

function ensureHero(homeHtml, filePath) {
  if (!/<section[^>]+class=["']hero["']/i.test(homeHtml)) {
    throw new Error(`Hero section missing in ${filePath}`);
  }
  if (!/grabgifts<\/h1>/i.test(homeHtml)) {
    throw new Error(`Hero title must be lowercase grabgifts in ${filePath}`);
  }
  if (!homeHtml.includes("Grab Gifts surfaces viral-ready Amazon finds")) {
    throw new Error(`Hero tagline sentence one missing in ${filePath}`);
  }
  if (!homeHtml.includes("Launch scroll-stopping gift funnels")) {
    throw new Error(`Hero tagline sentence two missing in ${filePath}`);
  }
  const actions = homeHtml.match(/<div[^>]*class=["']hero-actions["'][^>]*>([\s\S]*?)<\/div>/i);
  if (!actions) {
    throw new Error(`Hero actions missing in ${filePath}`);
  }
  const actionMarkup = actions[1];
  const buttons = [
    { href: "/guides/", label: "Explore today's drops" },
    { href: "/surprise/", label: "Spin up a surprise" },
    { href: "/changelog/", label: "See the live changelog" },
  ];
  for (const { href, label } of buttons) {
    const pattern = new RegExp(
      `<a[^>]+href=["']${escapeRegExp(href)}["'][^>]*>${escapeRegExp(label)}</a>`,
      "i",
    );
    if (!pattern.test(actionMarkup)) {
      throw new Error(`Hero button "${label}" linking to ${href} missing in ${filePath}`);
    }
  }
}

function ensureGradientTheme() {
  if (!fs.existsSync(THEME_PATH)) {
    throw new Error("theme.css missing from assets");
  }
  const css = fs.readFileSync(THEME_PATH, "utf8").toLowerCase();
  for (const color of ["#2a0c6a", "#9b0f62", "#0a0810"]) {
    if (!css.includes(color)) {
      throw new Error(`Gradient color ${color} missing from theme.css`);
    }
  }
}

function ensureNoBannedContent(html, filePath) {
  for (const phrase of BANNED_PHRASES) {
    if (html.toLowerCase().includes(phrase)) {
      throw new Error(`Banned phrase "${phrase}" detected in ${filePath}`);
    }
  }
  if (html.includes("★")) {
    throw new Error(`Star characters are not allowed in ${filePath}`);
  }
}

function extractProductImageSources(html, filePath) {
  const sources = [];
  const cardRegex = /<(li|article)\s+class=["']card["'][^>]*>([\s\S]*?)<\/\1>/gi;
  let match;
  while ((match = cardRegex.exec(html)) !== null) {
    const cardMarkup = match[0];
    if (!/target=\"_blank\"/i.test(cardMarkup) && !/rel=\"sponsored/i.test(cardMarkup)) {
      continue;
    }
    const imgMatch = cardMarkup.match(/<img\s+[^>]*src=["']([^"']+)["']/i);
    if (!imgMatch) {
      throw new Error(`Product card missing <img> in ${filePath}`);
    }
    sources.push(imgMatch[1]);
  }
  return sources;
}

async function headRequest(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, { method: "HEAD", signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HEAD ${response.status}`);
    }
  } catch (error) {
    throw new Error(`Image request failed for ${url}: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    clearTimeout(timeout);
  }
}

async function main() {
  if (!fs.existsSync(PUBLIC_DIR)) {
    throw new Error("public directory not found. Run the build before check_phase.");
  }

  const homePath = path.join(PUBLIC_DIR, "index.html");
  if (!fs.existsSync(homePath)) {
    throw new Error("Home page missing");
  }
  const guideDir = path.join(PUBLIC_DIR, "guides");
  let guidePath = null;
  if (fs.existsSync(guideDir)) {
    const guideEntries = gatherHtmlFiles(guideDir).filter((file) => file.endsWith("index.html"));
    guidePath = guideEntries[0] || null;
  }
  if (!guidePath) {
    throw new Error("No guide page found for verification");
  }

  const htmlFiles = gatherHtmlFiles(PUBLIC_DIR);
  const productImages = new Set();

  for (const filePath of htmlFiles) {
    const html = readHtml(filePath);
    ensureStylesheetLink(html, filePath);
    ensureNoStyleTags(html, filePath);
    ensureNoBannedContent(html, filePath);
    ensureHeaderFooter(html, filePath);
    const sources = extractProductImageSources(html, filePath);
    for (const src of sources) {
      productImages.add(src);
    }
  }

  const homeHtml = readHtml(homePath);
  ensureHero(homeHtml, homePath);

  const guidesIndexPath = path.join(PUBLIC_DIR, "guides", "index.html");
  if (!fs.existsSync(guidesIndexPath)) {
    throw new Error("/guides/index.html is missing");
  }
  const surprisePath = path.join(PUBLIC_DIR, "surprise", "index.html");
  if (!fs.existsSync(surprisePath)) {
    throw new Error("/surprise/index.html is missing");
  }
  const changelogPath = path.join(PUBLIC_DIR, "changelog", "index.html");
  if (!fs.existsSync(changelogPath)) {
    throw new Error("/changelog/index.html is missing");
  }

  const faqPath = path.join(PUBLIC_DIR, "faq", "index.html");
  if (!fs.existsSync(faqPath)) {
    throw new Error("/faq/index.html is missing");
  }

  const sitemapPath = path.join(PUBLIC_DIR, "sitemap.xml");
  if (!fs.existsSync(sitemapPath)) {
    throw new Error("sitemap.xml missing");
  }
  const sitemap = fs.readFileSync(sitemapPath, "utf8");
  if (!/\<loc\>[^<]*\/faq\/\<\/loc\>/.test(sitemap)) {
    throw new Error("/faq/ not listed in sitemap.xml");
  }

  const imagesToCheck = Array.from(productImages).slice(0, PRODUCT_IMAGE_LIMIT);
  for (const src of imagesToCheck) {
    await headRequest(src);
  }

  ensureGradientTheme();

  console.log("Phase-1 checks passed.");
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
