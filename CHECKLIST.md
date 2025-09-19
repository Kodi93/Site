# Phase-1 Checklist

- [ ] Gradient theme with grabgifts logo visible in the sticky navbar on every page.
- [ ] All pages render through `templates/base.html` and load only `/assets/theme.css` (no inline styles).
- [ ] Header and footer include required navigation, with the disclosure moved exclusively to `/faq/`.
- [ ] Product cards render only when a verified image is available; ingestion fails when image HEAD checks do not return 200.
- [ ] Protected layout files remain unchanged by generators.
- [ ] `tools/check_phase.mjs` passes to confirm Phase-1 gate compliance.
