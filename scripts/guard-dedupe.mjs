import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..");
const DATA_FILE = path.join(ROOT_DIR, "data", "products.json");
const COOLDOWN_DAYS = Number.parseInt(process.env.DEDUPE_COOLDOWN_DAYS ?? "30", 10);

const readProducts = async () => {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed?.products)) {
      return [];
    }
    return parsed.products;
  } catch (error) {
    if (error.code === "ENOENT") {
      return [];
    }
    throw error;
  }
};

const parseTimestamp = (value) => {
  if (!value || typeof value !== "string") {
    return null;
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return null;
  }
  return new Date(timestamp);
};

const differenceInDays = (a, b) => {
  const ms = Math.abs(a.getTime() - b.getTime());
  return ms / (1000 * 60 * 60 * 24);
};

const dedupeKey = (product) => {
  const asin = product?.asin;
  const category = product?.primary_category || product?.category || product?.category_slug;
  if (!asin || !category) {
    return null;
  }
  return `${asin}:${category}`;
};

const main = async () => {
  const products = await readProducts();
  if (products.length === 0) {
    console.log("No products found; skipping dedupe guard.");
    return;
  }

  const map = new Map();
  const duplicates = [];

  for (const product of products) {
    const key = dedupeKey(product);
    if (!key) {
      continue;
    }
    const updatedAt =
      parseTimestamp(product.updated_at) ||
      parseTimestamp(product.updatedAt) ||
      new Date();
    const entry = map.get(key);
    if (entry) {
      if (differenceInDays(updatedAt, entry.updatedAt) < COOLDOWN_DAYS) {
        duplicates.push({ key, previous: entry.updatedAt.toISOString(), current: updatedAt.toISOString() });
      } else if (updatedAt > entry.updatedAt) {
        map.set(key, { updatedAt });
      }
    } else {
      map.set(key, { updatedAt });
    }
  }

  if (duplicates.length > 0) {
    console.error("Duplicate products detected within cooldown window:");
    for (const dup of duplicates) {
      console.error(`  ${dup.key} (existing: ${dup.previous}, candidate: ${dup.current})`);
    }
    process.exitCode = 1;
    throw new Error("Cooldown guard failed");
  }

  console.log(`Dedupe guard passed (${products.length} products checked).`);
};

main().catch((error) => {
  if (process.exitCode !== 1) {
    console.error("Failed to evaluate dedupe guard", error);
    process.exitCode = 1;
  }
});
