const DEFAULT_TAG = "kayce25-20";

const sanitizeUrl = (url: string): URL => {
  try {
    return new URL(url);
  } catch (error) {
    throw new Error(`Invalid URL passed to aff(): ${url}`);
  }
};

export const aff = (url: string): string => {
  const result = sanitizeUrl(url);
  const tag = process.env.AFFIL_TAG ?? DEFAULT_TAG;
  if (tag && !result.searchParams.has("tag")) {
    result.searchParams.set("tag", tag);
  }
  return result.toString();
};

export default aff;
