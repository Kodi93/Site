const catalogs = document.querySelectorAll('[data-product-catalog]');

catalogs.forEach((catalog) => {
  initCatalog(catalog);
});

function parseNumber(value) {
  if (value === undefined || value === null || value === '') {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function readSelectedOption(select) {
  if (!select) {
    return null;
  }
  if (typeof select.selectedOptions !== 'undefined' && select.selectedOptions.length) {
    return select.selectedOptions[0];
  }
  if (typeof select.selectedIndex === 'number' && select.selectedIndex >= 0) {
    return select.options[select.selectedIndex] || null;
  }
  return null;
}

function initCatalog(catalog) {
  const grid = catalog.querySelector('[data-product-grid]');
  if (!grid) {
    return;
  }

  const cards = Array.from(grid.querySelectorAll('[data-product-card]'));
  if (!cards.length) {
    return;
  }

  const form = catalog.querySelector('[data-product-form]');
  const searchInput = catalog.querySelector('[data-product-search]');
  const categorySelect = catalog.querySelector('[data-product-filter="category"]');
  const priceSelect = catalog.querySelector('[data-product-filter="price"]');
  const summary = catalog.querySelector('[data-product-summary]');
  const emptyMessage = catalog.querySelector('[data-product-empty]');
  const total = cards.length;
  const totalLabel = total.toLocaleString();

  const entries = cards.map((card) => {
    let keywords = card.dataset.productKeywords || '';
    if (!keywords) {
      const fallback = [
        card.dataset.productTitle,
        card.dataset.productBrand,
        card.dataset.productCategory,
      ]
        .filter(Boolean)
        .join(' ');
      keywords = fallback;
    }
    keywords = keywords.toLowerCase();

    return {
      card,
      keywords,
      category: (card.dataset.productCategory || '').toLowerCase(),
      price: parseNumber(card.dataset.productPrice),
    };
  });

  function readPriceSelection(select) {
    if (!select || !select.value) {
      return { min: null, max: null, missing: false };
    }
    const option = readSelectedOption(select);
    if (!option) {
      return { min: null, max: null, missing: false };
    }
    return {
      min: parseNumber(option.dataset.productMin),
      max: parseNumber(option.dataset.productMax),
      missing: option.dataset.productMissing === 'true',
    };
  }

  function applyFilters() {
    const query = (searchInput?.value || '').trim().toLowerCase();
    const category = (categorySelect?.value || '').trim().toLowerCase();
    const priceSelection = readPriceSelection(priceSelect);
    const hasPriceFilter =
      priceSelection.missing || priceSelection.min !== null || priceSelection.max !== null;

    let visibleCount = 0;

    entries.forEach((entry) => {
      let matches = true;

      if (query && !entry.keywords.includes(query)) {
        matches = false;
      }

      if (matches && category && entry.category !== category) {
        matches = false;
      }

      if (matches) {
        if (priceSelection.missing) {
          if (entry.price !== null) {
            matches = false;
          }
        } else if (priceSelection.min !== null || priceSelection.max !== null) {
          if (entry.price === null) {
            matches = false;
          } else {
            if (priceSelection.min !== null && entry.price < priceSelection.min) {
              matches = false;
            }
            if (priceSelection.max !== null && entry.price >= priceSelection.max) {
              matches = false;
            }
          }
        }
      }

      entry.card.hidden = !matches;
      if (matches) {
        visibleCount += 1;
      }
    });

    if (summary) {
      summary.textContent = `Showing ${visibleCount.toLocaleString()} of ${totalLabel} products`;
      summary.dataset.productCount = String(visibleCount);
    }

    if (emptyMessage) {
      emptyMessage.hidden = visibleCount !== 0;
    }

    const hasActiveFilters = Boolean(query || category || hasPriceFilter);
    if (hasActiveFilters) {
      catalog.dataset.productActive = 'true';
    } else {
      delete catalog.dataset.productActive;
    }

    if (searchInput) {
      searchInput.classList.toggle('has-value', Boolean(query));
    }
    if (categorySelect) {
      categorySelect.classList.toggle('has-selection', Boolean(category));
    }
    if (priceSelect) {
      priceSelect.classList.toggle('has-selection', hasPriceFilter);
    }
  }

  const scheduleApply = () => {
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(() => {
        applyFilters();
      });
    } else {
      applyFilters();
    }
  };

  if (form) {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
    });
    form.addEventListener('reset', () => {
      scheduleApply();
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', scheduleApply);
  }
  if (categorySelect) {
    categorySelect.addEventListener('change', applyFilters);
  }
  if (priceSelect) {
    priceSelect.addEventListener('change', applyFilters);
  }

  applyFilters();
}
