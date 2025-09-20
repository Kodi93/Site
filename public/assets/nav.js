const root = document.documentElement;
root.classList.add("has-nav-js");

const toggle = document.querySelector("[data-nav-toggle]");
const panel = document.querySelector("[data-nav-panel]");

if (toggle && panel) {
  const focusableSelectors =
    'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])';
  const collapseMedia = window.matchMedia("(max-width: 900px)");
  let isOpen = false;
  let lastFocused = null;
  const tabindexDataAttribute = "data-nav-tabindex";
  const tabindexSentinel = "__nav_none__";

  function updatePanelAccessibility() {
    if (collapseMedia.matches) {
      panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
    } else {
      panel.removeAttribute("aria-hidden");
    }
  }

  function setPanelFocusability(disabled) {
    if (disabled) {
      const focusable = panel.querySelectorAll(focusableSelectors);
      focusable.forEach((element) => {
        if (!element.hasAttribute(tabindexDataAttribute)) {
          const stored = element.hasAttribute("tabindex")
            ? element.getAttribute("tabindex")
            : tabindexSentinel;
          element.setAttribute(tabindexDataAttribute, stored);
        }
        element.setAttribute("tabindex", "-1");
      });
      return;
    }

    const storedElements = panel.querySelectorAll(`[${tabindexDataAttribute}]`);
    storedElements.forEach((element) => {
      const stored = element.getAttribute(tabindexDataAttribute);
      if (stored === tabindexSentinel) {
        element.removeAttribute("tabindex");
      } else if (stored !== null) {
        element.setAttribute("tabindex", stored);
      }
      element.removeAttribute(tabindexDataAttribute);
    });
  }

  function setState(open, { focus = true } = {}) {
    if (isOpen === open) {
      updatePanelAccessibility();
      return;
    }
    isOpen = open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    panel.classList.toggle("is-open", open);
    document.body.classList.toggle("nav-open", open);
    setPanelFocusability(collapseMedia.matches && !open);
    updatePanelAccessibility();

    if (open) {
      lastFocused = document.activeElement;
      const focusTarget = panel.querySelector(focusableSelectors) || toggle;
      focusTarget.focus({ preventScroll: true });
      return;
    }

    if (!focus) return;
    const returnTarget = lastFocused && document.contains(lastFocused) ? lastFocused : toggle;
    returnTarget.focus({ preventScroll: true });
  }

  function openNav() {
    setState(true);
  }

  function closeNav(options = {}) {
    setState(false, options);
  }

  toggle.addEventListener("click", (event) => {
    event.preventDefault();
    if (isOpen) {
      closeNav();
    } else {
      openNav();
    }
  });

  panel.addEventListener("click", (event) => {
    if (!isOpen) return;
    const anchor = event.target.closest("a[href]");
    if (anchor) {
      closeNav({ focus: false });
    }
  });

  document.addEventListener("pointerdown", (event) => {
    if (!isOpen) return;
    if (panel.contains(event.target) || toggle.contains(event.target)) return;
    closeNav({ focus: false });
  });

  function handleKeydown(event) {
    if (!isOpen) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeNav();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = panel.querySelectorAll(focusableSelectors);
    if (!focusable.length) {
      event.preventDefault();
      toggle.focus({ preventScroll: true });
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey) {
      if (active === first || !panel.contains(active)) {
        event.preventDefault();
        last.focus({ preventScroll: true });
      }
      return;
    }
    if (active === last) {
      event.preventDefault();
      first.focus({ preventScroll: true });
    }
  }

  document.addEventListener("keydown", handleKeydown);

  function handleBreakpointChange(event) {
    if (!event.matches) {
      closeNav({ focus: false });
    } else {
      updatePanelAccessibility();
      setPanelFocusability(event.matches && !isOpen);
    }
  }

  if (typeof collapseMedia.addEventListener === "function") {
    collapseMedia.addEventListener("change", handleBreakpointChange);
  } else if (typeof collapseMedia.addListener === "function") {
    collapseMedia.addListener(handleBreakpointChange);
  }

  updatePanelAccessibility();
  setPanelFocusability(collapseMedia.matches && !isOpen);
  toggle.setAttribute("aria-expanded", "false");
}
