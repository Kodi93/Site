const feedRoot = document.querySelector("[data-feed]");

if (!feedRoot) {
  return;
}

const listEl = feedRoot.querySelector("[data-feed-list]");
if (!listEl) {
  console.warn("[feed] Missing feed list container");
  return;
}

const statusEl = feedRoot.querySelector("[data-feed-status]");
const loadMoreButton = feedRoot.querySelector("[data-feed-more]");
const sentinel = feedRoot.querySelector("[data-feed-sentinel]");
const manifestUrl = feedRoot.dataset.feedManifest;

const seenIds = new Set();
listEl.querySelectorAll("[data-feed-id]").forEach((node) => {
  const id = node.getAttribute("data-feed-id");
  if (id) seenIds.add(id);
});

const toNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const state = {
  currentPage: toNumber(feedRoot.dataset.feedPage),
  totalPages: toNumber(feedRoot.dataset.feedTotal),
  isLoading: false,
  done: feedRoot.hasAttribute("data-feed-complete"),
  manifest: null,
};

let observer = null;

feedRoot.dataset.feedPage = String(state.currentPage);
if (state.totalPages) {
  feedRoot.dataset.feedTotal = String(state.totalPages);
} else {
  delete feedRoot.dataset.feedTotal;
}

if (state.done) {
  if (statusEl) {
    statusEl.hidden = false;
    if (!statusEl.textContent) {
      statusEl.textContent = "You're all caught up.";
    }
  }
  if (loadMoreButton) {
    loadMoreButton.disabled = true;
    loadMoreButton.setAttribute("aria-disabled", "true");
  }
} else if (statusEl) {
  statusEl.hidden = true;
}

function setStatus(message, { hidden = false } = {}) {
  if (!statusEl) return;
  if (typeof message === "string" && message) {
    statusEl.textContent = message;
  }
  statusEl.hidden = hidden;
}

function setLoading(loading) {
  state.isLoading = loading;
  feedRoot.classList.toggle("is-loading", loading);
  if (loadMoreButton) {
    loadMoreButton.disabled = loading;
    loadMoreButton.setAttribute("aria-busy", loading ? "true" : "false");
  }
}

function markComplete() {
  state.done = true;
  feedRoot.setAttribute("data-feed-complete", "");
  delete feedRoot.dataset.feedNext;
  setStatus("You're all caught up.", { hidden: false });
  if (loadMoreButton) {
    loadMoreButton.disabled = true;
    loadMoreButton.setAttribute("aria-disabled", "true");
  }
  if (observer) {
    observer.disconnect();
  }
}

async function ensureManifest() {
  if (!manifestUrl || state.manifest) return;
  try {
    const response = await fetch(manifestUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`Failed to load feed manifest: ${response.status}`);
    const payload = await response.json();
    if (payload && typeof payload === "object") {
      state.manifest = payload;
      if (typeof payload.totalPages === "number") {
        state.totalPages = payload.totalPages;
        feedRoot.dataset.feedTotal = String(state.totalPages);
      }
    }
  } catch (error) {
    console.error("[feed]", error);
  }
}

function getPageUrl(page) {
  if (!page || (state.totalPages && page > state.totalPages)) return null;
  if (state.manifest && Array.isArray(state.manifest.pages)) {
    const entry = state.manifest.pages.find((item) => item && item.page === page);
    if (entry && entry.href) return entry.href;
  }
  return `/assets/feed/page-${page}.json`;
}

function createFeedCard(item) {
  if (!item || !item.title || !item.url || !item.image) return null;
  const article = document.createElement("article");
  article.className = "feed-card";
  if (item.id) article.dataset.feedId = item.id;

  const link = document.createElement("a");
  link.className = "feed-card-link";
  link.href = item.url;
  link.target = "_blank";
  link.rel = "sponsored nofollow noopener";

  const media = document.createElement("div");
  media.className = "feed-card-media";
  const img = document.createElement("img");
  img.src = item.image;
  img.alt = item.title;
  img.loading = "lazy";
  media.appendChild(img);

  const body = document.createElement("div");
  body.className = "feed-card-body";

  const metaParts = [];
  if (item.category) metaParts.push(item.category);
  if (item.brand) metaParts.push(item.brand);
  if (metaParts.length) {
    const meta = document.createElement("p");
    meta.className = "feed-card-meta";
    meta.textContent = metaParts.join(" • ");
    body.appendChild(meta);
  }

  const title = document.createElement("h3");
  title.className = "feed-card-title";
  title.textContent = item.title;
  body.appendChild(title);

  if (item.price) {
    const price = document.createElement("p");
    price.className = "feed-card-price";
    price.textContent = item.price;
    body.appendChild(price);
  }

  link.appendChild(media);
  link.appendChild(body);
  article.appendChild(link);
  return article;
}

function appendItems(items) {
  if (!Array.isArray(items)) return 0;
  const fragment = document.createDocumentFragment();
  let appended = 0;
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const id = item.id;
    if (id && seenIds.has(id)) continue;
    const card = createFeedCard(item);
    if (!card) continue;
    if (id) seenIds.add(id);
    fragment.appendChild(card);
    appended += 1;
  }
  if (fragment.childNodes.length) {
    listEl.querySelectorAll(".feed-empty").forEach((node) => node.remove());
    listEl.appendChild(fragment);
  }
  return appended;
}

async function loadPage(page) {
  await ensureManifest();
  const url = getPageUrl(page);
  if (!url) {
    markComplete();
    return;
  }
  setLoading(true);
  setStatus("Loading new picks…", { hidden: false });
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Failed to load feed page ${page}: ${response.status}`);
    const payload = await response.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    const appended = appendItems(items);

    const resolvedPage = Number(payload?.page);
    if (Number.isFinite(resolvedPage) && resolvedPage > 0) {
      state.currentPage = resolvedPage;
    } else {
      state.currentPage = page;
    }

    if (typeof payload?.totalPages === "number") {
      state.totalPages = payload.totalPages;
      feedRoot.dataset.feedTotal = String(state.totalPages);
    }

    feedRoot.dataset.feedPage = String(state.currentPage);

    const nextPage = state.currentPage + 1;
    const nextUrl = getPageUrl(nextPage);
    if (nextUrl && (!state.totalPages || nextPage <= state.totalPages)) {
      feedRoot.dataset.feedNext = nextUrl;
    } else {
      delete feedRoot.dataset.feedNext;
    }

    if (appended) {
      if (!nextUrl || (state.totalPages && nextPage > state.totalPages)) {
        markComplete();
      } else {
        setStatus("", { hidden: true });
      }
    } else if (!nextUrl || (state.totalPages && nextPage > state.totalPages)) {
      markComplete();
    } else {
      setStatus("No more gifts to show right now. Check back soon.", { hidden: false });
    }
  } catch (error) {
    console.error("[feed]", error);
    setStatus("We couldn't load more gifts right now. Try again in a moment.", {
      hidden: false,
    });
  } finally {
    setLoading(false);
  }
}

async function queueLoad() {
  if (state.isLoading || state.done) return;
  const nextPage = state.currentPage + 1 || 1;
  if (state.totalPages && nextPage > state.totalPages) {
    markComplete();
    return;
  }
  await loadPage(nextPage);
}

if (loadMoreButton) {
  loadMoreButton.addEventListener("click", () => {
    queueLoad();
  });
}

if ("IntersectionObserver" in window && sentinel && !state.done) {
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          queueLoad();
          break;
        }
      }
    },
    { rootMargin: "600px 0px" },
  );
  observer.observe(sentinel);
}
