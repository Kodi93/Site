import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..");
const DATA_FILE = path.join(ROOT_DIR, "data", "products.json");
const PUBLIC_DIR = path.join(ROOT_DIR, "public");
const SITEMAP_FILE = path.join(PUBLIC_DIR, "sitemap.xml");

const STATIC_ROUTES = [
  "/",
  "/guides",
  "/categories/for-him",
  "/categories/for-her",
  "/categories/for-a-techy",
  "/categories/for-gamers",
  "/categories/for-fandom",
  "/categories/homebody-upgrades",
];

const formatUrl = (base, route) => {
  const normalized = route.startsWith("/") ? route : `/${route}`;
  return new URL(normalized, base).toString();
};

const readJson = async (file) => {
  try {
    const content = await fs.readFile(file, "utf8");
    return JSON.parse(content);
  } catch (error) {
    if (error.code === "ENOENT") {
      return null;
    }
    throw error;
  }
};

const slugify = (value) => {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-")
    .trim();
};

const resolveProductSlug = (product) => {
  if (typeof product.slug === "string" && product.slug.length > 0) {
    return product.slug;
  }
  if (product.title && product.asin) {
    return slugify(`${product.title}-${product.asin}`);
  }
  return null;
};

const buildEntries = async () => {
  const baseUrl = process.env.SITE_BASE_URL ?? "https://www.grabgifts.net";
  const now = new Date().toISOString();
  const entries = STATIC_ROUTES.map((route) => ({
    loc: formatUrl(baseUrl, route),
    lastmod: now,
  }));

  const data = await readJson(DATA_FILE);
  const products = Array.isArray(data?.products) ? data.products : [];
  for (const product of products) {
    if (!product) {
      continue;
    }
    const slug = resolveProductSlug(product);
    if (!slug) {
      continue;
    }
    const lastmod = product.updated_at || product.updatedAt || now;
    entries.push({
      loc: formatUrl(baseUrl, `/p/${slug}`),
      lastmod,
    });
  }
  return entries;
};

const writeSitemap = async (entries) => {
  const urlset = entries
    .map((entry) => {
      const lastmod = entry.lastmod ? `\n    <lastmod>${entry.lastmod}</lastmod>` : "";
      return `  <url>\n    <loc>${entry.loc}</loc>${lastmod}\n  </url>`;
    })
    .join("\n");
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urlset}\n</urlset>\n`;
  await fs.mkdir(PUBLIC_DIR, { recursive: true });
  await fs.writeFile(SITEMAP_FILE, xml, "utf8");
};

const main = async () => {
  const entries = await buildEntries();
  await writeSitemap(entries);
  console.log(`Wrote ${entries.length} entries to ${SITEMAP_FILE}`);
};

main().catch((error) => {
  console.error("Failed to build sitemap", error);
  process.exitCode = 1;
});
