const feedRoots = document.querySelectorAll("[data-feed-root]");

if (!feedRoots.length) {
  return;
}

feedRoots.forEach((root) => initFeed(root));

function toNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function initFeed(root) {
  const feedEl = root.querySelector("[data-feed]");
  if (!feedEl) {
    return;
  }

  const listEl = feedEl.querySelector("[data-feed-list]");
  if (!listEl) {
    console.warn("[feed] Missing feed list container");
    return;
  }

  const statusEl = root.querySelector("[data-feed-status]");
  const loadMoreButton = root.querySelector("[data-feed-more]");
  const sentinel = root.querySelector("[data-feed-sentinel]");
  const descriptionEl = root.querySelector("[data-feed-description]");
  const tabs = Array.from(root.querySelectorAll("[data-feed-tab]"));

  const templates = new Map();
  root.querySelectorAll("template[data-feed-template]").forEach((template) => {
    const key = template.dataset.feedTemplate;
    if (!key) return;
    templates.set(key, template.innerHTML.trim());
  });

  const configNodes = Array.from(root.querySelectorAll("script[data-feed-state]"));
  const configs = [];
  for (const node of configNodes) {
    const id = node.dataset.feedState;
    if (!id) continue;
    try {
      const payload = JSON.parse(node.textContent || "{}");
      configs.push({ id, data: payload });
    } catch (error) {
      console.error(`[feed] Failed to parse config for ${id}`, error);
    }
  }

  if (!configs.length) {
    return;
  }

  const defaultIdRaw = root.dataset.feedDefault || "";
  const fallbackId = configs[0]?.id || "";
  const defaultId = configs.some((cfg) => cfg.id === defaultIdRaw) ? defaultIdRaw : fallbackId;

  const modes = new Map();
  for (const { id, data } of configs) {
    const emptyMessage = data.empty || "More gifts are loading soon—check back for fresh picks.";
    const templateMarkup = templates.get(id) || "";
    const initialMarkup =
      id === defaultId
        ? listEl.innerHTML
        : templateMarkup || `<p class=\"feed-empty\">${emptyMessage}</p>`;
    const totalPages = toNumber(data.totalPages);
    const currentPage = toNumber(data.currentPage);
    const done =
      (!data.nextPage || !String(data.nextPage).trim()) &&
      (totalPages === 0 || (currentPage > 0 && totalPages > 0 && currentPage >= totalPages));
    modes.set(id, {
      id,
      label: data.label || id,
      description: data.description || "",
      pageSize: toNumber(data.pageSize),
      totalItems: toNumber(data.totalItems),
      totalPages,
      currentPage,
      nextPage: data.nextPage || "",
      baseHref: data.baseHref || "",
      manifestHref: data.manifestHref || "",
      empty: emptyMessage,
      emptyMarkup: `<p class=\"feed-empty\">${emptyMessage}</p>`,
      savedHtml: initialMarkup,
      seenIds: new Set(),
      isLoading: false,
      statusMessage: "",
      done,
    });
  }

  if (!modes.size) {
    return;
  }

  const defaultMode = modes.get(defaultId);
  if (defaultMode) {
    refreshSeenIds(defaultMode);
  }

  let activeModeId = null;
  let observer = null;

  function collectSeenIds() {
    const ids = new Set();
    listEl.querySelectorAll("[data-feed-id]").forEach((node) => {
      const id = node.getAttribute("data-feed-id");
      if (id) ids.add(id);
    });
    return ids;
  }

  function refreshSeenIds(mode) {
    mode.seenIds = collectSeenIds();
  }

  function updateTabs(selectedId) {
    tabs.forEach((tab) => {
      const id = tab.dataset.feedTab;
      const selected = id === selectedId;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", selected ? "true" : "false");
      tab.setAttribute("tabindex", selected ? "0" : "-1");
    });
  }

  function updateButtonState(mode) {
    if (!loadMoreButton) return;
    const hasMore = Boolean(mode.nextPage);
    loadMoreButton.hidden = !hasMore;
    loadMoreButton.disabled = mode.isLoading;
    loadMoreButton.setAttribute("aria-disabled", hasMore ? "false" : "true");
    loadMoreButton.setAttribute("aria-busy", mode.isLoading ? "true" : "false");
  }

  function updateStatusForMode(mode) {
    if (!statusEl) return;
    if (mode.isLoading) {
      statusEl.textContent = "Loading new picks…";
      statusEl.hidden = false;
    } else if (mode.statusMessage) {
      statusEl.textContent = mode.statusMessage;
      statusEl.hidden = false;
    } else if (mode.done) {
      statusEl.textContent = "You're all caught up.";
      statusEl.hidden = false;
    } else {
      statusEl.textContent = "";
      statusEl.hidden = true;
    }
  }

  function setLoading(mode, loading) {
    mode.isLoading = loading;
    feedEl.classList.toggle("is-loading", loading);
    updateButtonState(mode);
    updateStatusForMode(mode);
  }

  function applyState(mode) {
    feedEl.dataset.feedMode = mode.id;
    feedEl.dataset.feedPage = String(mode.currentPage || 0);
    if (mode.totalPages) {
      feedEl.dataset.feedTotal = String(mode.totalPages);
    } else {
      delete feedEl.dataset.feedTotal;
    }
    if (mode.totalItems) {
      feedEl.dataset.feedTotalItems = String(mode.totalItems);
    } else {
      delete feedEl.dataset.feedTotalItems;
    }
    if (mode.pageSize) {
      feedEl.dataset.feedPageSize = String(mode.pageSize);
    } else {
      delete feedEl.dataset.feedPageSize;
    }
    if (mode.nextPage) {
      feedEl.dataset.feedNext = mode.nextPage;
    } else {
      delete feedEl.dataset.feedNext;
    }
    if (mode.done) {
      feedEl.setAttribute("data-feed-complete", "");
    } else {
      feedEl.removeAttribute("data-feed-complete");
    }
    if (descriptionEl) {
      descriptionEl.textContent = mode.description || "";
    }
    updateButtonState(mode);
    updateStatusForMode(mode);
  }

  function updateObserver(mode) {
    if (!observer || !sentinel) return;
    observer.disconnect();
    if (!mode.done && mode.nextPage) {
      observer.observe(sentinel);
    }
  }

  function ensureListContent(mode) {
    if (!listEl.children.length) {
      listEl.innerHTML = mode.emptyMarkup;
    }
    refreshSeenIds(mode);
    mode.savedHtml = listEl.innerHTML;
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

  function appendItems(mode, items) {
    if (!Array.isArray(items) || !items.length) return 0;
    const fragment = document.createDocumentFragment();
    let appended = 0;
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      const id = item.id;
      if (id && mode.seenIds.has(id)) continue;
      const card = createFeedCard(item);
      if (!card) continue;
      if (id) mode.seenIds.add(id);
      fragment.appendChild(card);
      appended += 1;
    }
    if (fragment.childNodes.length) {
      listEl.querySelectorAll(".feed-empty").forEach((node) => node.remove());
      listEl.appendChild(fragment);
      mode.savedHtml = listEl.innerHTML;
    }
    return appended;
  }

  async function loadPage(mode, pageNumber) {
    const url = mode.baseHref ? `${mode.baseHref}/page-${pageNumber}.json` : mode.nextPage;
    if (!url) {
      mode.done = true;
      mode.nextPage = "";
      applyState(mode);
      if (observer) observer.disconnect();
      return;
    }
    mode.statusMessage = "";
    setLoading(mode, true);
    if (statusEl) {
      statusEl.textContent = "Loading new picks…";
      statusEl.hidden = false;
    }
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`Failed to load feed page ${pageNumber}: ${response.status}`);
      const payload = await response.json();
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const appended = appendItems(mode, items);

      const resolvedPage = Number(payload?.page);
      if (Number.isFinite(resolvedPage) && resolvedPage > 0) {
        mode.currentPage = resolvedPage;
      } else {
        mode.currentPage = pageNumber;
      }
      if (typeof payload?.totalPages === "number") {
        mode.totalPages = payload.totalPages;
      }
      if (typeof payload?.totalItems === "number") {
        mode.totalItems = payload.totalItems;
      }
      if (typeof payload?.pageSize === "number") {
        mode.pageSize = payload.pageSize;
      }

      const nextPage = mode.currentPage + 1;
      if (mode.totalPages && nextPage > mode.totalPages) {
        mode.nextPage = "";
        mode.done = true;
      } else {
        mode.nextPage = `${mode.baseHref}/page-${nextPage}.json`;
        mode.done = false;
      }

      if (!mode.nextPage) {
        mode.done = true;
      }

      if (appended) {
        mode.statusMessage = "";
      } else if (!mode.nextPage) {
        mode.statusMessage = "";
      } else {
        mode.statusMessage = "No more gifts to show right now. Check back soon.";
      }

      applyState(mode);
      updateObserver(mode);
    } catch (error) {
      console.error("[feed]", error);
      mode.statusMessage = "We couldn't load more gifts right now. Try again in a moment.";
      applyState(mode);
    } finally {
      setLoading(mode, false);
      if (mode.done && observer) {
        observer.disconnect();
      }
    }
  }

  async function queueLoad() {
    if (!activeModeId) return;
    const mode = modes.get(activeModeId);
    if (!mode || mode.isLoading || mode.done) return;
    const nextPage = (mode.currentPage || 0) + 1;
    if (mode.totalPages && nextPage > mode.totalPages) {
      mode.done = true;
      mode.nextPage = "";
      applyState(mode);
      if (observer) observer.disconnect();
      return;
    }
    await loadPage(mode, nextPage);
  }

  function activateMode(modeId) {
    if (!modeId || !modes.has(modeId)) return;
    if (activeModeId === modeId) return;

    if (activeModeId) {
      const previous = modes.get(activeModeId);
      if (previous) {
        previous.savedHtml = listEl.innerHTML;
      }
    }

    activeModeId = modeId;
    const mode = modes.get(modeId);
    if (!mode) return;

    listEl.innerHTML = mode.savedHtml;
    ensureListContent(mode);
    updateTabs(modeId);
    mode.statusMessage = "";
    applyState(mode);
    updateObserver(mode);
  }

  tabs.forEach((tab) => {
    tab.setAttribute("role", "tab");
    tab.addEventListener("click", () => {
      if (tab.disabled) return;
      activateMode(tab.dataset.feedTab || "");
    });
  });

  if (loadMoreButton) {
    loadMoreButton.addEventListener("click", () => {
      queueLoad();
    });
  }

  if ("IntersectionObserver" in window && sentinel) {
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
  }

  activateMode(defaultId);
}
