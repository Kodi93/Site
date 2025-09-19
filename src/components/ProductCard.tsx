import React, { useMemo } from "react";
import { aff } from "../lib/affiliate";

export interface ProductCardData {
  slug: string;
  title: string;
  amazonUrl: string;
  price?: string | null;
  image?: string | null;
  description?: string | null;
  brand?: string | null;
  rating?: number | null;
  reviews?: number | null;
  updatedAt: string;
  availability?: string | null;
}

export interface ProductCardProps {
  product: ProductCardData;
  canonicalBaseUrl?: string;
}

const DEFAULT_BASE_URL = "https://www.grabgifts.net";
const ISO_DATE_LENGTH = 10;

const sanitizeBaseUrl = (value: string): string => {
  return value.endsWith("/") ? value.slice(0, -1) : value;
};

const parsePrice = (price: string | null | undefined): number | undefined => {
  if (!price) {
    return undefined;
  }
  const match = price.match(/[0-9]+(?:\.[0-9]{1,2})?/);
  if (!match) {
    return undefined;
  }
  return Number.parseFloat(match[0]);
};

const detectCurrency = (price: string | null | undefined): string => {
  if (!price) {
    return "USD";
  }
  const symbol = price.trim().charAt(0);
  switch (symbol) {
    case "€":
      return "EUR";
    case "£":
      return "GBP";
    case "¥":
      return "JPY";
    case "C":
      if (price.trim().startsWith("CA$")) {
        return "CAD";
      }
      break;
    default:
      break;
  }
  return "USD";
};

const formatUpdatedAt = (updatedAt: string): string => {
  if (!updatedAt) {
    return "Unknown";
  }
  return updatedAt.slice(0, ISO_DATE_LENGTH);
};

const normalizeAvailability = (availability?: string | null): string => {
  if (!availability) {
    return "https://schema.org/InStock";
  }
  if (availability.startsWith("http")) {
    return availability;
  }
  return `https://schema.org/${availability}`;
};

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  canonicalBaseUrl = DEFAULT_BASE_URL,
}) => {
  const canonicalUrl = `${sanitizeBaseUrl(canonicalBaseUrl)}/p/${product.slug}`;

  const schemaPayload = useMemo(() => {
    const offerPrice = parsePrice(product.price ?? undefined);
    const payload = {
      "@context": "https://schema.org",
      "@type": "Product",
      name: product.title,
      image: product.image ?? undefined,
      description: product.description ?? undefined,
      brand: product.brand ?? undefined,
      aggregateRating:
        product.rating != null
          ? {
              "@type": "AggregateRating",
              ratingValue: product.rating,
              reviewCount: product.reviews ?? undefined,
            }
          : undefined,
      offers:
        offerPrice != null
          ? {
              "@type": "Offer",
              priceCurrency: detectCurrency(product.price ?? undefined),
              price: offerPrice,
              availability: normalizeAvailability(product.availability),
              url: aff(product.amazonUrl),
            }
          : undefined,
    } as const;
    return JSON.stringify(payload, (_, value) => (value === undefined ? undefined : value));
  }, [product.amazonUrl, product.availability, product.brand, product.description, product.image, product.price, product.rating, product.reviews, product.title]);

  return (
    <>
      <link rel="canonical" href={canonicalUrl} />
      <article className="product-card">
        {product.image ? (
          <img
            src={product.image}
            alt={product.title}
            loading="lazy"
            width={640}
            height={640}
          />
        ) : null}
        <h3 className="product-card__title">{product.title}</h3>
        {product.description ? (
          <p className="product-card__description">{product.description}</p>
        ) : null}
        <a
          className="product-card__cta"
          href={aff(product.amazonUrl)}
          target="_blank"
          rel="sponsored nofollow noopener"
        >
          View on Amazon
        </a>
        <p className="text-xs text-slate-500">Updated {formatUpdatedAt(product.updatedAt)}</p>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schemaPayload }} />
      </article>
    </>
  );
};

export default ProductCard;
