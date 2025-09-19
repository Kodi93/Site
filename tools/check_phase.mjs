import fs from "node:fs";
import path from "node:path";
import fetch from "node-fetch";

const ROOT = process.cwd();
const PUBLIC_DIR = path.join(ROOT, "public");
const BANNED_PHRASES = ["fresh drops", "active vibes"];
const PRODUCT_IMAGE_LIMIT = 100;

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
  if (!html.includes('<img src="/assets/logo.svg"')) {
    throw new Error(`Header logo not found in ${filePath}`);
  }
  const navMatch = html.match(/<nav class=["']site-nav["'][^>]*>([\s\S]*?)<\/nav>/i);
  if (!navMatch) {
    throw new Error(`Primary navigation missing in ${filePath}`);
  }
  const linkCount = (navMatch[1].match(/<a\b/gi) || []).length;
  if (linkCount < 6) {
    throw new Error(`Primary navigation should include at least 6 links in ${filePath}`);
  }
  const footerMatch = html.match(/<footer[^>]*class=["']site-footer["'][^>]*>([\s\S]*?)<\/footer>/i);
  if (!footerMatch) {
    throw new Error(`Missing site footer in ${filePath}`);
  }
  if (!/href=["']\/faq\//i.test(footerMatch[1])) {
    throw new Error(`Footer must include a /faq/ link in ${filePath}`);
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
    const sources = extractProductImageSources(html, filePath);
    for (const src of sources) {
      productImages.add(src);
    }
  }

  const homeHtml = readHtml(homePath);
  ensureHeaderFooter(homeHtml, homePath);
  const guideHtml = readHtml(guidePath);
  ensureHeaderFooter(guideHtml, guidePath);

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

  console.log("Phase-1 checks passed.");
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
