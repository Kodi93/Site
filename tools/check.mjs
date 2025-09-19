import fs from "node:fs";
import path from "node:path";

const items = JSON.parse(fs.readFileSync("data/items.json", "utf8"));
if (new Set(items.map((i) => i.id)).size !== items.length) throw new Error("Duplicate item IDs");
if (items.length < 50) throw new Error("Too few items");
if (!fs.existsSync("public/guides")) throw new Error("Guides missing");

function assertNavStructure(html, context) {
  const brandMatch = html.match(/<a[^>]*class=\"[^\"]*\bbrand\b[^\"]*\"[^>]*href=\"\/\"[^>]*>/i);
  if (!brandMatch) {
    throw new Error(`${context}: missing brand link to /`);
  }
  const navMatches = html.match(/<nav[^>]*class=\"[^\"]*\bsite-nav\b[^\"]*\"[^>]*>[\s\S]*?<\/nav>/gi) || [];
  if (navMatches.length !== 1) {
    throw new Error(`${context}: expected exactly one site-nav, found ${navMatches.length}`);
  }
  const linkCount = (navMatches[0].match(/<a\b[^>]*href=/gi) || []).length;
  if (linkCount < 6) {
    throw new Error(`${context}: primary navigation has fewer than 6 links`);
  }
}

const homePath = path.join("public", "index.html");
if (!fs.existsSync(homePath)) throw new Error("Homepage missing");
const homeHtml = fs.readFileSync(homePath, "utf8");
assertNavStructure(homeHtml, "homepage");

const guidesDir = path.join("public", "guides");
const guideEntries = fs
  .readdirSync(guidesDir, { withFileTypes: true })
  .filter((entry) => entry.isDirectory());
if (guideEntries.length === 0) throw new Error("No guides found");
const guideHtml = fs.readFileSync(path.join(guidesDir, guideEntries[0].name, "index.html"), "utf8");
assertNavStructure(guideHtml, `guide ${guideEntries[0].name}`);

console.info("QA OK");
