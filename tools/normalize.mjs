import { hash, clean, clamp, withAffiliate, polish } from "./util.mjs";

export function normalizeItem(src){
  const id = src.asin || src.id || hash(src.url||src.title);
  return {
    id,
    source: src.source,
    title: clean(src.title),
    blurb: src.blurb ? polish(src.blurb) : undefined,
    url: withAffiliate(src.url),
    image: src.image,
    price: src.price ? String(src.price) : undefined,
    rating: clamp(src.rating, 0, 5),
    brand: src.brand,
    category: src.category,
    updatedAt: new Date().toISOString(),
  };
}
