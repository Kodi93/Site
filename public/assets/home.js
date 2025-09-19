const guideSection = document.querySelector('[data-home-guides]');

if (guideSection) {
  const toggle = guideSection.querySelector('[data-home-guide-toggle="true"]');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const hiddenCards = guideSection.querySelectorAll('[data-home-guide-hidden="true"]');
      hiddenCards.forEach((card) => {
        card.removeAttribute('hidden');
        card.removeAttribute('data-home-guide-hidden');
      });
      toggle.setAttribute('aria-expanded', 'true');
      toggle.hidden = true;
    });
  }
}

function initProductSection(section) {
  const grid = section.querySelector('[data-product-grid]');
  const sentinel = section.querySelector('[data-product-sentinel]');
  const source = section.querySelector('[data-product-source]');
  if (!grid || !source) {
    if (sentinel) sentinel.remove();
    return;
  }

  let entries;
  try {
    const raw = source.textContent || '[]';
    entries = JSON.parse(raw);
  } catch (error) {
    console.error('[home] Failed to parse product payload', error);
    if (sentinel) sentinel.remove();
    return;
  }

  if (!Array.isArray(entries) || !entries.length) {
    if (sentinel) sentinel.remove();
    return;
  }

  let index = 0;
  const batchAttr = Number(section.getAttribute('data-product-batch'));
  const batchSize = Number.isFinite(batchAttr) && batchAttr > 0 ? batchAttr : 6;
  let observer = null;

  function appendBatch() {
    const next = entries.slice(index, index + batchSize);
    next.forEach((markup) => {
      if (typeof markup === 'string' && markup.trim()) {
        grid.insertAdjacentHTML('beforeend', markup);
      }
    });
    index += next.length;
    if (index >= entries.length) {
      if (observer) observer.disconnect();
      if (sentinel) sentinel.remove();
    }
  }

  if ('IntersectionObserver' in window && sentinel) {
    observer = new IntersectionObserver(
      (records) => {
        for (const record of records) {
          if (record.isIntersecting) {
            appendBatch();
            break;
          }
        }
      },
      { rootMargin: '400px 0px' },
    );
    observer.observe(sentinel);
  } else {
    appendBatch();
  }
}

const productSection = document.querySelector('[data-home-products]');
if (productSection) {
  initProductSection(productSection);
}
