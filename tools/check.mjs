import fs from "node:fs";
import path from "node:path";

const items = JSON.parse(fs.readFileSync("data/items.json", "utf8"));
if (new Set(items.map((i) => i.id)).size !== items.length) throw new Error("Duplicate item IDs");
if (items.length < 50) throw new Error("Too few items");
if (!fs.existsSync("public/guides")) throw new Error("Guides missing");

function assertLayout(html, context) {
  if (!html.includes('<link rel="stylesheet" href="/assets/theme.css">')) {
    throw new Error(`${context}: missing theme stylesheet link`);
  }
  const stylesheetLinks = html.match(/<link\b[^>]*rel=['"]stylesheet['"][^>]*>/gi) || [];
  if (stylesheetLinks.length !== 1) {
    throw new Error(`${context}: expected exactly one stylesheet link, found ${stylesheetLinks.length}`);
  }
  if (/<style\b/i.test(html)) {
    throw new Error(`${context}: inline <style> tags detected`);
  }
  const brandMatch = html.match(/<a[^>]*class=["'][^"']*\bbrand\b[^"']*["'][^>]*href=["']\/["'][^>]*>/i);
  if (!brandMatch) {
    throw new Error(`${context}: missing brand link to /`);
  }
  const navMatch = html.match(/<nav[^>]*class=["'][^"']*\bsite-nav\b[^"']*["'][^>]*>[\s\S]*?<\/nav>/i);
  if (!navMatch) {
    throw new Error(`${context}: missing primary navigation`);
  }
  const linkCount = (navMatch[0].match(/<a\b[^>]*href=/gi) || []).length;
  if (linkCount < 6) {
    throw new Error(`${context}: primary navigation has fewer than 6 links`);
  }
}

const homePath = path.join("public", "index.html");
if (!fs.existsSync(homePath)) throw new Error("Homepage missing");
const homeHtml = fs.readFileSync(homePath, "utf8");
assertLayout(homeHtml, "homepage");

const guidesDir = path.join("public", "guides");
const guideEntries = fs
  .readdirSync(guidesDir, { withFileTypes: true })
  .filter((entry) => entry.isDirectory());
if (guideEntries.length === 0) throw new Error("No guides found");
const guideHtml = fs.readFileSync(path.join(guidesDir, guideEntries[0].name, "index.html"), "utf8");
assertLayout(guideHtml, `guide ${guideEntries[0].name}`);

console.info("QA OK");
