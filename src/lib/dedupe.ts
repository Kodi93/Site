export interface DedupeSource {
  asin: string;
  category: string;
}

export const dedupeKey = (payload: DedupeSource): string => {
  return `${payload.asin}:${payload.category}`;
};

export default dedupeKey;
