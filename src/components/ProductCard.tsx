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
  category?: string | null;
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

const UPDATED_DATE_FORMAT = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

const formatUpdatedAt = (updatedAt: string): string => {
  if (!updatedAt) {
    return "Unknown";
  }
  const parsed = new Date(updatedAt);
  if (Number.isNaN(parsed.getTime())) {
    return updatedAt.slice(0, 10);
  }
  return UPDATED_DATE_FORMAT.format(parsed);
};

const formatAvailabilityLabel = (availability?: string | null): string | undefined => {
  if (!availability) {
    return undefined;
  }
  let label = availability.trim();
  const schemaMatch = label.match(/schema\.org\/(.+)$/i);
  if (schemaMatch) {
    label = schemaMatch[1];
  }
  label = label.replace(/^https?:\/\//i, "");
  label = label.replace(/[_-]+/g, " ");
  label = label.replace(/([a-z])([A-Z])/g, "$1 $2");
  return label
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
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

  const availabilityLabel = formatAvailabilityLabel(product.availability);
  const metaTags = [] as string[];
  if (product.brand) {
    metaTags.push(product.brand);
  }
  if (product.category) {
    metaTags.push(product.category);
  }
  if (availabilityLabel) {
    metaTags.push(availabilityLabel);
  }

  const ratingLabel = product.rating != null ? product.rating.toFixed(1).replace(/\.0$/, "") : undefined;
  const reviewLabel =
    product.reviews != null && product.reviews > 0
      ? `${product.reviews.toLocaleString()} ${product.reviews === 1 ? "review" : "reviews"}`
      : undefined;

  return (
    <>
      <link rel="canonical" href={canonicalUrl} />
      <article className="product-card">
        {product.image ? (
          <div className="product-card__media">
            <img
              src={product.image}
              alt={product.title}
              loading="lazy"
              width={640}
              height={640}
            />
          </div>
        ) : null}
        <div className="product-card__body">
          {metaTags.length ? (
            <ul className="product-card__tags">
              {metaTags.map((tag, index) => (
                <li key={`${tag}-${index}`}>{tag}</li>
              ))}
            </ul>
          ) : null}
          <h2 className="product-card__title">{product.title}</h2>
          {product.price ? <p className="product-card__price">{product.price}</p> : null}
          {ratingLabel ? (
            <div className="product-card__rating" aria-label={`Rated ${ratingLabel} out of 5`}>
              <span className="product-card__rating-icon" aria-hidden="true">
                ★
              </span>
              <span className="product-card__rating-score">{ratingLabel}</span>
              {reviewLabel ? <span className="product-card__rating-count">({reviewLabel})</span> : null}
            </div>
          ) : null}
          {product.description ? (
            <p className="product-card__description">{product.description}</p>
          ) : null}
          <a
            className="button product-card__cta"
            href={aff(product.amazonUrl)}
            target="_blank"
            rel="sponsored nofollow noopener"
          >
            View on Amazon
          </a>
          <p className="product-card__updated">Updated {formatUpdatedAt(product.updatedAt)}</p>
        </div>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schemaPayload }} />
      </article>
    </>
  );
};

export default ProductCard;
