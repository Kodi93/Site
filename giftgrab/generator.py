"""Static site generator responsible for producing the HTML pages."""
from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List
from urllib.parse import quote_plus

from .config import OUTPUT_DIR, SiteSettings, ensure_directories
from .models import Category, PricePoint, Product
from .utils import PRICE_CURRENCY_SYMBOLS, parse_price_string

logger = logging.getLogger(__name__)

CURRENCY_SYMBOL_BY_CODE = {code: symbol for symbol, code in PRICE_CURRENCY_SYMBOLS.items()}

ASSETS_STYLES = """
:root {
  color-scheme: light dark;
  --brand: #ff2d6a;
  --brand-dark: #c4134a;
  --accent: #ffb224;
  --highlight: #0ea5e9;
  --bg: #fff7fb;
  --bg-muted: #ffecf3;
  --text: #2a1223;
  --muted: #806274;
  --muted-strong: #452138;
  --card: #ffffff;
  --card-elevated: #ffe3ef;
  --card-sheen: rgba(255, 255, 255, 0.92);
  --border: rgba(255, 45, 106, 0.12);
  --border-strong: rgba(255, 45, 106, 0.22);
  --overlay: rgba(255, 45, 106, 0.08);
  --pill-bg: rgba(255, 45, 106, 0.16);
  --pill-bg-hover: rgba(255, 45, 106, 0.28);
  --badge-bg: rgba(255, 178, 36, 0.18);
  --badge-color: #a25900;
  --price-bg: rgba(255, 45, 106, 0.2);
  --rating-bg: rgba(14, 165, 233, 0.18);
  --newsletter-bg: rgba(255, 45, 106, 0.08);
  --newsletter-border: rgba(255, 45, 106, 0.35);
  --input-bg: #ffffff;
  --input-border: rgba(255, 45, 106, 0.2);
  --shadow-soft: 0 16px 32px rgba(178, 46, 94, 0.12);
  --shadow-card: 0 28px 60px rgba(178, 46, 94, 0.18);
  --shadow-card-hover: 0 36px 72px rgba(178, 46, 94, 0.24);
  --header-bg: rgba(255, 255, 255, 0.88);
  --hero-glow: radial-gradient(120% 120% at 50% 0%, rgba(255, 45, 106, 0.12) 0%, rgba(255, 178, 36, 0.08) 45%, transparent 100%);
  --theme-track: rgba(255, 45, 106, 0.24);
  --theme-thumb: #ffffff;
  font-family: 'Manrope', 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

:root[data-theme='dark'] {
  color-scheme: dark light;
  --bg: #19031f;
  --bg-muted: #23062a;
  --text: #ffeef7;
  --muted: #d39ab5;
  --muted-strong: #ffd9e7;
  --card: #200625;
  --card-elevated: #2b0b31;
  --card-sheen: rgba(48, 9, 56, 0.82);
  --border: rgba(255, 143, 181, 0.24);
  --border-strong: rgba(255, 143, 181, 0.36);
  --overlay: rgba(255, 45, 106, 0.24);
  --pill-bg: rgba(255, 45, 106, 0.32);
  --pill-bg-hover: rgba(255, 45, 106, 0.46);
  --badge-bg: rgba(255, 178, 36, 0.34);
  --badge-color: #ffd59a;
  --price-bg: rgba(255, 45, 106, 0.38);
  --rating-bg: rgba(14, 165, 233, 0.32);
  --newsletter-bg: rgba(255, 45, 106, 0.3);
  --newsletter-border: rgba(255, 178, 36, 0.44);
  --input-bg: rgba(30, 8, 36, 0.74);
  --input-border: rgba(255, 178, 36, 0.38);
  --shadow-soft: 0 18px 40px rgba(0, 0, 0, 0.52);
  --shadow-card: 0 32px 70px rgba(0, 0, 0, 0.6);
  --shadow-card-hover: 0 40px 80px rgba(0, 0, 0, 0.68);
  --header-bg: rgba(20, 4, 28, 0.86);
  --hero-glow: radial-gradient(120% 120% at 50% 0%, rgba(255, 45, 106, 0.26) 0%, rgba(255, 178, 36, 0.2) 45%, rgba(12, 0, 20, 0.92) 100%);
  --theme-track: rgba(255, 45, 106, 0.38);
  --theme-thumb: #2a0733;
}

html {
  scroll-behavior: smooth;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  background-image:
    radial-gradient(120% 120% at 0% 0%, rgba(255, 45, 106, 0.12) 0%, transparent 55%),
    radial-gradient(120% 120% at 100% 0%, rgba(255, 178, 36, 0.12) 0%, transparent 60%),
    var(--hero-glow);
  background-attachment: fixed;
  color: var(--text);
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  transition: background 0.35s ease, color 0.35s ease;
}

img {
  max-width: 100%;
  display: block;
  border-radius: 12px;
}

a {
  color: var(--brand);
  text-decoration: none;
  transition: color 0.2s ease, opacity 0.2s ease;
}

a:hover,
a:focus {
  color: var(--brand-dark);
}

:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

button,
input {
  font: inherit;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.skip-link {
  position: absolute;
  left: -999px;
  top: 0;
  background: var(--brand);
  color: #fff;
  padding: 0.6rem 1rem;
  border-radius: 0 0 12px 12px;
  font-weight: 600;
  z-index: 1000;
}

.skip-link:focus {
  left: 1rem;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

header {
  background: var(--header-bg);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid rgba(255, 45, 106, 0.16);
  box-shadow: 0 18px 40px rgba(178, 46, 94, 0.14);
  transition: background 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease;
}

:root[data-theme='dark'] header {
  box-shadow: 0 22px 48px rgba(0, 0, 0, 0.45);
  border-color: rgba(255, 45, 106, 0.28);
}

nav {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  padding: 1.1rem 2rem;
}

.logo {
  font-weight: 700;
  font-size: 1.3rem;
  letter-spacing: -0.01em;
  color: var(--text);
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.logo::before {
  content: '';
  width: 14px;
  height: 14px;
  border-radius: 6px;
  transform: rotate(12deg);
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow: 0 0 0 4px rgba(255, 45, 106, 0.18), 0 8px 18px rgba(255, 178, 36, 0.25);
}

:root[data-theme='dark'] .logo::before {
  box-shadow: 0 0 0 4px rgba(255, 45, 106, 0.35), 0 10px 22px rgba(255, 178, 36, 0.28);
}

.nav-groups {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.nav-links {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.96rem;
}

.nav-links a {
  color: var(--muted);
  font-weight: 500;
  position: relative;
  padding-bottom: 0.2rem;
}

.nav-links a::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: 0;
  height: 2px;
  width: 100%;
  background: linear-gradient(135deg, var(--brand), var(--accent));
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.25s ease;
}

.nav-links a:hover::after,
.nav-links a:focus::after {
  transform: scaleX(1);
}

.nav-links a:hover,
.nav-links a:focus {
  color: var(--brand);
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.nav-actions a {
  color: var(--muted);
  font-weight: 500;
}

.nav-actions a:hover,
.nav-actions a:focus {
  color: var(--brand);
}

.pill-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55rem 0.95rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 45, 106, 0.24);
  font-weight: 600;
  color: var(--brand);
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.16), rgba(255, 178, 36, 0.12));
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.pill-link:hover,
.pill-link:focus {
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.26), rgba(255, 178, 36, 0.2));
  color: var(--brand);
  transform: translateY(-2px);
  border-color: rgba(255, 45, 106, 0.36);
  box-shadow: 0 14px 28px rgba(255, 45, 106, 0.18);
}

.search-form {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 999px;
  border: 1px solid rgba(255, 45, 106, 0.16);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(18px);
}

:root[data-theme='dark'] .search-form {
  background: rgba(36, 10, 44, 0.68);
  border-color: rgba(255, 178, 36, 0.32);
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.4);
}

.search-form input {
  border: none;
  background: transparent;
  font-size: 0.95rem;
  padding: 0.35rem 0.1rem 0.35rem 0.35rem;
  color: var(--text);
  min-width: 200px;
}

.search-form input::placeholder {
  color: var(--muted);
}

.search-form input:focus {
  outline: none;
}

.search-form button {
  border: none;
  background: transparent;
  color: var(--muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.search-form button:hover,
.search-form button:focus {
  color: var(--accent);
}

.search-filters {
  margin: 1.4rem 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  align-items: center;
}

.search-filters label {
  font-weight: 600;
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}

.search-filters select {
  padding: 0.4rem 0.65rem;
  border-radius: 10px;
  border: 1px solid rgba(255, 45, 106, 0.2);
  background: var(--card-sheen);
  color: var(--muted-strong);
  font-size: 0.92rem;
  cursor: pointer;
  box-shadow: 0 12px 26px rgba(178, 46, 94, 0.12);
}

.search-meta {
  margin: 0.3rem 0 0;
  font-size: 0.9rem;
  color: var(--muted);
}

.theme-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.theme-toggle-input {
  position: absolute;
  opacity: 0;
  inset: 0;
}

.theme-toggle-label {
  display: inline-grid;
  grid-auto-flow: column;
  align-items: center;
  gap: 0.55rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card);
  cursor: pointer;
  transition: color 0.2s ease, background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  box-shadow: var(--shadow-soft);
}

:root[data-theme='dark'] .theme-toggle-label {
  border-color: rgba(148, 163, 184, 0.3);
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.35);
}

.theme-toggle-text {
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--muted);
  transition: color 0.2s ease;
}

.theme-toggle-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  width: 18px;
  height: 18px;
  transition: color 0.2s ease, opacity 0.2s ease;
  opacity: 0.45;
}

.theme-toggle-track {
  position: relative;
  width: 52px;
  height: 26px;
  border-radius: 999px;
  background: var(--theme-track);
  padding: 3px;
  display: inline-flex;
  align-items: center;
  transition: background 0.25s ease, box-shadow 0.25s ease;
}

.theme-toggle-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--theme-thumb);
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.25);
  transform: translateX(0);
  transition: transform 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
}

:root[data-theme='dark'] .theme-toggle-thumb {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.theme-toggle-input:checked + .theme-toggle-label {
  border-color: rgba(255, 45, 106, 0.32);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-text {
  color: var(--brand);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-track {
  background: linear-gradient(135deg, var(--brand), var(--accent));
  box-shadow: 0 12px 26px rgba(255, 45, 106, 0.32);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-thumb {
  transform: translateX(26px);
  box-shadow: 0 8px 18px rgba(255, 45, 106, 0.35);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-icon--moon,
.theme-toggle-input:not(:checked) + .theme-toggle-label .theme-toggle-icon--sun {
  color: var(--brand);
  opacity: 1;
}

.theme-toggle-label:hover {
  background: var(--overlay);
}

main {
  flex: 1;
  width: 100%;
  transition: color 0.35s ease;
}

.page-shell {
  max-width: 1320px;
  margin: 0 auto;
  padding: 2.5rem 2rem 4rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
  width: 100%;
}

.page-main {
  flex: 1;
  min-width: 0;
}

main > section + section {
  margin-top: 3.5rem;
}

.ad-rail {
  background: linear-gradient(180deg, var(--card-sheen) 0%, var(--card) 100%);
  border: 1px solid rgba(255, 45, 106, 0.16);
  border-radius: 24px;
  box-shadow: var(--shadow-card);
  padding: 1.5rem;
  width: 100%;
}

:root[data-theme='dark'] .ad-rail {
  border-color: rgba(255, 178, 36, 0.25);
}

.ad-rail-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}

.ad-rail-label {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  background: var(--pill-bg);
  border: 1px solid rgba(255, 45, 106, 0.18);
  border-radius: 999px;
  padding: 0.3rem 0.75rem;
}

.hero {
  position: relative;
  text-align: center;
  padding: 3.75rem 1.8rem;
  margin: 0 auto 3.75rem;
  max-width: 1020px;
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.14), rgba(255, 178, 36, 0.1)), var(--card);
  border-radius: 32px;
  border: 1px solid rgba(255, 45, 106, 0.16);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  backdrop-filter: blur(6px);
}

.hero::before {
  content: '';
  position: absolute;
  inset: -25%;
  background:
    radial-gradient(circle at 20% 20%, rgba(255, 45, 106, 0.25), transparent 55%),
    radial-gradient(circle at 80% 25%, rgba(255, 178, 36, 0.18), transparent 55%),
    conic-gradient(from 140deg at 50% 50%, rgba(249, 115, 22, 0.25), transparent 65%);
  opacity: 0.85;
  filter: blur(0.5px);
  pointer-events: none;
}

.hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.32), transparent 65%);
  opacity: 0.6;
  pointer-events: none;
}

.hero > * {
  position: relative;
  z-index: 1;
}

.hero .eyebrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0.8rem;
  border-radius: 999px;
  background: rgba(255, 45, 106, 0.16);
  color: var(--brand);
  border: 1px solid rgba(255, 45, 106, 0.22);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 1.15rem;
  box-shadow: 0 12px 26px rgba(255, 45, 106, 0.2);
  backdrop-filter: blur(6px);
}

.hero h1 {
  font-size: clamp(2.5rem, 4.5vw, 3.4rem);
  margin-bottom: 0.85rem;
  font-weight: 800;
  letter-spacing: -0.015em;
}

.hero p {
  color: var(--muted-strong);
  opacity: 0.9;
  margin: 0 auto;
  max-width: 650px;
  font-size: 1.08rem;
}

.hero-actions {
  margin-top: 2rem;
  display: flex;
  justify-content: center;
  gap: 0.9rem;
  flex-wrap: wrap;
}

.hero-actions.align-left {
  justify-content: flex-start;
}

.button-link,
.cta-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.85rem 1.25rem;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 55%, rgba(249, 115, 22, 0.92) 100%);
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.04em;
  box-shadow: 0 22px 48px rgba(255, 45, 106, 0.32);
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
  white-space: nowrap;
}

.button-link:hover,
.button-link:focus,
.cta-button:hover,
.cta-button:focus {
  transform: translateY(-2px);
  box-shadow: 0 30px 60px rgba(255, 45, 106, 0.38);
  filter: brightness(1.05);
}

.cta-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.8rem 1.15rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 178, 36, 0.24);
  font-weight: 600;
  color: var(--accent);
  background: rgba(255, 178, 36, 0.12);
  box-shadow: 0 16px 32px rgba(255, 178, 36, 0.18);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  cursor: pointer;
}

.cta-secondary:hover,
.cta-secondary:focus {
  background: rgba(255, 178, 36, 0.2);
  color: var(--accent);
  transform: translateY(-2px);
  border-color: rgba(255, 178, 36, 0.42);
  box-shadow: 0 24px 48px rgba(255, 178, 36, 0.24);
}

.section-heading {
  text-align: center;
  margin-bottom: 2rem;
}

.section-heading h2 {
  margin-bottom: 0.6rem;
  font-size: clamp(1.9rem, 3vw, 2.5rem);
}

.section-heading p {
  margin: 0 auto;
  color: var(--muted);
  max-width: 640px;
}

.news-feed {
  margin-top: 3.5rem;
}

.feed-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 1.75rem;
}

.feed-header h2 {
  margin-bottom: 0.35rem;
}

.feed-header p {
  margin: 0;
  color: var(--muted);
  max-width: 520px;
}

.feed-controls {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem;
  border-radius: 999px;
  background: var(--card-sheen);
  border: 1px solid var(--border);
  box-shadow: 0 14px 28px rgba(178, 46, 94, 0.12);
}

:root[data-theme='dark'] .feed-controls {
  background: rgba(36, 10, 44, 0.78);
  border-color: rgba(255, 178, 36, 0.38);
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.45);
}

.feed-sort {
  border: none;
  background: transparent;
  color: var(--muted);
  font-weight: 600;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.feed-sort:hover,
.feed-sort:focus {
  color: var(--brand);
  background: rgba(255, 45, 106, 0.14);
}

.feed-sort.is-active {
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.22), rgba(255, 178, 36, 0.2));
  color: var(--brand);
  box-shadow: 0 18px 32px rgba(255, 45, 106, 0.24);
}

:root[data-theme='dark'] .feed-sort.is-active {
  color: var(--accent);
}

.feed-grid {
  display: grid;
  gap: 1.75rem;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}

.is-hidden {
  display: none !important;
}

.feed-sentinel {
  margin: 2rem auto 0;
  text-align: center;
}

.feed-sentinel[hidden] {
  display: none !important;
}

.feed-more {
  border: none;
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.14), rgba(255, 178, 36, 0.18));
  color: var(--brand);
  font-weight: 600;
  padding: 0.85rem 2.4rem;
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 18px 38px rgba(178, 46, 94, 0.18);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.feed-more:hover,
.feed-more:focus {
  transform: translateY(-2px);
  box-shadow: 0 22px 44px rgba(178, 46, 94, 0.22);
}

.feed-card {
  position: relative;
}

.feed-empty {
  text-align: center;
  color: var(--muted);
  padding: 2.5rem 1rem;
  border: 1px dashed var(--border);
  border-radius: 18px;
  background: var(--card-sheen);
}

.grid {
  display: grid;
  gap: 1.75rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.card {
  position: relative;
  background: linear-gradient(180deg, var(--card-sheen) 0%, var(--card) 100%);
  border-radius: 26px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
  border: 1px solid rgba(255, 45, 106, 0.14);
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-card-hover);
  border-color: rgba(255, 45, 106, 0.28);
}

.card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 15%, rgba(255, 45, 106, 0.18), transparent 55%), radial-gradient(circle at 80% 20%, rgba(255, 178, 36, 0.18), transparent 60%);
  opacity: 0;
  transition: opacity 0.25s ease;
  pointer-events: none;
}

.card:hover::before {
  opacity: 1;
}

.card-media {
  position: relative;
  display: block;
  overflow: hidden;
  border-bottom: 1px solid rgba(255, 45, 106, 0.12);
}

.card-media img {
  width: 100%;
  height: 230px;
  object-fit: cover;
  transition: transform 0.2s ease;
  border-radius: 0;
}

.card:hover .card-media img {
  transform: scale(1.05);
}

.card-badge {
  position: absolute;
  top: 14px;
  left: 14px;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.85), rgba(255, 178, 36, 0.75));
  color: #fff;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  box-shadow: 0 12px 26px rgba(178, 46, 94, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.3);
}

:root[data-theme='dark'] .card-badge {
  border-color: rgba(255, 255, 255, 0.2);
}

.card-content {
  padding: 1.35rem 1.5rem 1.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  flex: 1;
  position: relative;
  z-index: 1;
}

.card--ad .card-content {
  align-items: center;
  text-align: center;
}

.card-content--ad {
  gap: 1.35rem;
  justify-content: center;
}

.card-ad-label {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  background: var(--pill-bg);
  border: 1px solid rgba(255, 45, 106, 0.18);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
}

:root[data-theme='dark'] .card-ad-label {
  border-color: rgba(255, 178, 36, 0.28);
}

.card-content h3 {
  margin: 0;
  font-size: 1.15rem;
}

.card-content p {
  color: var(--muted);
  margin: 0;
  font-size: 0.98rem;
  line-height: 1.7;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.92rem;
  color: var(--muted);
  align-items: center;
}

.card-retailer {
  background: var(--badge-bg);
  color: var(--badge-color);
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.9rem;
}

.card-highlight {
  margin-top: -0.25rem;
}

.card-deal {
  display: inline-block;
  margin-top: 0.35rem;
  background: rgba(255, 178, 36, 0.18);
  color: var(--accent);
  font-weight: 600;
  padding: 0.35rem 0.7rem;
  border-radius: 12px;
  border: 1px solid rgba(255, 178, 36, 0.35);
}

.card-deal--up {
  background: rgba(249, 115, 22, 0.16);
  color: var(--highlight);
  border-color: rgba(249, 115, 22, 0.3);
}

.card-price {
  font-weight: 700;
  color: var(--brand);
  background: var(--price-bg);
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 45, 106, 0.24);
}

.card-rating {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: linear-gradient(135deg, var(--brand), var(--accent));
  color: #fff;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 8px 18px rgba(178, 46, 94, 0.25);
}

.card-rating svg {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

.card-rating-count {
  color: rgba(255, 255, 255, 0.75);
  margin-left: 0.15rem;
}

.card-actions {
  margin-top: auto;
  display: grid;
  gap: 0.85rem;
}

.card-actions .button-link,
.card-actions .cta-secondary {
  width: 100%;
  justify-content: center;
}

@media (min-width: 640px) {
  .card-actions {
    grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
  }
}

@media (max-width: 600px) {
  .card-media img {
    height: 210px;
  }
}

.category-hero {
  display: grid;
  gap: 2.5rem;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  align-items: center;
  margin-bottom: 2.8rem;
  padding: 2.5rem;
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.12), rgba(255, 178, 36, 0.1)), var(--card);
  border-radius: 30px;
  border: 1px solid rgba(255, 45, 106, 0.16);
  box-shadow: var(--shadow-card);
}

.category-hero p {
  color: var(--muted);
  font-size: 1.05rem;
}

.newsletter-banner {
  margin: 3.5rem auto 0;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.12), rgba(255, 178, 36, 0.1)), var(--card);
  border: 1px solid rgba(255, 45, 106, 0.2);
  border-radius: 28px;
  padding: 2.5rem;
  text-align: center;
  max-width: 760px;
  box-shadow: var(--shadow-card);
}

.newsletter-banner::before,
.newsletter-banner::after {
  content: '';
  position: absolute;
  inset: auto;
  pointer-events: none;
  opacity: 0.75;
}

.newsletter-banner::before {
  top: -35%;
  left: -25%;
  width: 60%;
  height: 120%;
  background: radial-gradient(circle, rgba(255, 45, 106, 0.28), transparent 65%);
}

.newsletter-banner::after {
  bottom: -40%;
  right: -10%;
  width: 70%;
  height: 130%;
  background: radial-gradient(circle, rgba(255, 178, 36, 0.2), transparent 60%);
}

.newsletter-banner > * {
  position: relative;
  z-index: 1;
}

.newsletter-banner h3 {
  margin-top: 0;
}

.newsletter-banner p {
  color: var(--muted);
  margin-bottom: 1.1rem;
}

.newsletter-form {
  margin-top: 1.5rem;
}

.newsletter-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 0.9rem;
  justify-content: center;
}

.newsletter-fields input[type="email"] {
  flex: 1 1 240px;
  min-width: 0;
  padding: 0.85rem 1.1rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 45, 106, 0.22);
  background: var(--card-sheen);
  font-size: 1rem;
  color: var(--text);
  box-shadow: 0 16px 34px rgba(178, 46, 94, 0.18);
}

.newsletter-fields input[type="email"]::placeholder {
  color: var(--muted);
}

.newsletter-fields button {
  flex: 0 0 auto;
  padding: 0.9rem 1.45rem;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 60%, rgba(249, 115, 22, 0.95) 100%);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 24px 48px rgba(255, 45, 106, 0.32);
  transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.newsletter-fields button:hover,
.newsletter-fields button:focus {
  transform: translateY(-2px);
  box-shadow: 0 30px 60px rgba(255, 45, 106, 0.38);
}

.value-prop {
  margin-top: 3.5rem;
}

.value-grid {
  display: grid;
  gap: 1.75rem;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.value-card {
  position: relative;
  background: linear-gradient(180deg, var(--card-sheen), var(--card));
  border-radius: 26px;
  padding: 1.85rem;
  border: 1px solid rgba(255, 45, 106, 0.16);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.value-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top right, rgba(255, 45, 106, 0.22), transparent 60%), radial-gradient(circle at bottom left, rgba(255, 178, 36, 0.18), transparent 60%);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.value-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-card-hover);
  border-color: rgba(255, 45, 106, 0.28);
}

.value-card:hover::after {
  opacity: 1;
}

.value-card h3 {
  margin-top: 0.75rem;
}

.value-card p {
  margin: 0;
  color: var(--muted);
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.16), rgba(255, 178, 36, 0.16));
  color: var(--brand);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  font-weight: 700;
  text-transform: uppercase;
}

.latest-intro {
  text-align: center;
  margin-top: 3.5rem;
}

.latest-intro p {
  max-width: 640px;
  margin: 0.5rem auto 0;
  color: var(--muted);
}

.product-page {
  display: grid;
  gap: 2.25rem;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  align-items: flex-start;
}

.product-page img {
  width: 100%;
  border-radius: 24px;
  box-shadow: var(--shadow-card);
}

.product-meta {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.product-meta h1 {
  font-size: clamp(2.1rem, 3.5vw, 2.7rem);
  margin: 0;
}

.price-callout {
  font-weight: 600;
  color: var(--brand);
}

.review-callout {
  color: var(--accent);
  font-weight: 500;
}

.retailer-callout {
  margin: 0;
  color: var(--muted);
  font-size: 0.95rem;
}

.retailer-callout a {
  color: var(--accent);
}

.deal-callout {
  margin: 0;
  background: var(--price-bg);
  color: var(--brand);
  padding: 0.6rem 0.8rem;
  border-radius: 14px;
  font-weight: 600;
  border: 1px solid rgba(255, 45, 106, 0.24);
}

.deal-callout--up {
  background: rgba(249, 115, 22, 0.16);
  color: var(--highlight);
  border-color: rgba(249, 115, 22, 0.26);
}

.feature-list {
  padding-left: 1.2rem;
}

.cta-row {
  margin-top: 1.35rem;
}

.engagement-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 0.9rem;
  align-items: center;
}

.wishlist-toggle {
  background: rgba(255, 45, 106, 0.08);
  border: 1px solid rgba(255, 45, 106, 0.24);
  border-radius: 999px;
  padding: 0.45rem 1.2rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--brand);
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.wishlist-toggle:hover,
.wishlist-toggle:focus {
  background: rgba(255, 45, 106, 0.16);
  border-color: rgba(255, 45, 106, 0.32);
  box-shadow: 0 12px 26px rgba(255, 45, 106, 0.24);
}

.wishlist-toggle.is-active {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
  box-shadow: 0 14px 32px rgba(255, 45, 106, 0.3);
}

.share-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: center;
}

.share-primary {
  background: linear-gradient(135deg, var(--brand), var(--accent));
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 0.45rem 1.1rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 16px 34px rgba(255, 45, 106, 0.28);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.share-primary:hover,
.share-primary:focus {
  transform: translateY(-2px);
  box-shadow: 0 20px 42px rgba(255, 45, 106, 0.32);
}

.share-links {
  display: flex;
  gap: 0.45rem;
  align-items: center;
}

.share-links a,
.share-copy {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border-radius: 999px;
  padding: 0.4rem 0.9rem;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(255, 45, 106, 0.18);
  color: var(--accent);
  font-weight: 500;
  cursor: pointer;
}

.share-copy {
  background: rgba(255, 45, 106, 0.08);
}

:root[data-theme='dark'] .share-links a,
:root[data-theme='dark'] .share-copy {
  background: rgba(42, 12, 50, 0.72);
  border-color: rgba(255, 178, 36, 0.32);
}

:root[data-theme='dark'] .share-copy {
  background: rgba(255, 45, 106, 0.25);
}

.related-grid {
  margin-top: 3rem;
}

.related-grid h2 {
  text-align: center;
  margin-bottom: 1.6rem;
}

.price-insights {
  margin-top: 3rem;
  background: linear-gradient(135deg, rgba(255, 45, 106, 0.12), rgba(255, 178, 36, 0.12)), var(--card);
  padding: 1.8rem 2rem;
  border-radius: 24px;
  box-shadow: var(--shadow-card);
  border: 1px solid rgba(255, 45, 106, 0.16);
}

.price-insights h2 {
  margin-top: 0;
  margin-bottom: 0.65rem;
}

.price-insights p {
  margin: 0;
  color: var(--muted-strong);
}

.price-history {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.price-history li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.55rem;
  padding: 0.65rem 0.85rem;
  border-radius: 14px;
  background: linear-gradient(180deg, var(--card-sheen), var(--card));
  box-shadow: 0 14px 28px rgba(178, 46, 94, 0.12);
  border: 1px solid rgba(255, 45, 106, 0.14);
}

.price-history span {
  color: var(--muted);
}

.price-history strong {
  color: var(--brand);
}

.adsense-slot {
  margin: 2rem auto;
  text-align: center;
}

.adsense-slot--inline {
  margin: 0;
  width: 100%;
  min-height: 250px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.adsense-slot--footer {
  max-width: 728px;
}

.adsense-slot--rail {
  margin: 0;
  width: 100%;
}

.breadcrumbs {
  font-size: 0.9rem;
  margin-bottom: 1.6rem;
  color: var(--muted);
}

.breadcrumbs a {
  color: var(--muted);
}

.breadcrumbs a:hover,
.breadcrumbs a:focus {
  color: var(--brand);
}

.search-page {
  max-width: 820px;
  margin: 0 auto;
}

.search-results {
  list-style: none;
  margin: 2rem 0 0;
  padding: 0;
  display: grid;
  gap: 1.4rem;
}

.search-result {
  background: linear-gradient(180deg, var(--card-sheen), var(--card));
  border: 1px solid rgba(255, 45, 106, 0.14);
  border-radius: 24px;
  padding: 1.5rem 1.75rem;
  box-shadow: var(--shadow-card);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.search-result:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-card-hover);
  border-color: rgba(255, 45, 106, 0.28);
}

.search-result h3 {
  margin-top: 0;
  margin-bottom: 0.45rem;
}

.search-result p {
  margin: 0;
  color: var(--muted);
}

.search-result .badge {
  margin-top: 0.8rem;
}

.search-empty {
  text-align: center;
  color: var(--muted);
  margin-top: 2rem;
}

footer {
  border-top: 1px solid rgba(255, 45, 106, 0.16);
  margin-top: 3.5rem;
  padding: 2.75rem 1.5rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.92rem;
  background: linear-gradient(180deg, rgba(255, 45, 106, 0.08), transparent 45%, rgba(255, 178, 36, 0.08));
  transition: background 0.35s ease, color 0.35s ease, border-color 0.35s ease;
}

:root[data-theme='dark'] footer {
  background: linear-gradient(180deg, rgba(12, 15, 34, 0.65), rgba(255, 45, 106, 0.22));
}

.footer-links {
  display: flex;
  justify-content: center;
  gap: 1.1rem;
  flex-wrap: wrap;
  margin-top: 0.85rem;
}

.footer-links a {
  color: var(--muted);
}

.footer-links a:hover,
.footer-links a:focus {
  color: var(--brand);
  text-decoration: underline;
}

@media (max-width: 1024px) {
  nav {
    padding: 1rem 1.5rem;
  }
}

@media (min-width: 1100px) {
  .page-shell {
    flex-direction: row;
    align-items: flex-start;
  }

  .ad-rail {
    flex: 0 0 300px;
    position: sticky;
    top: 6.5rem;
    max-height: calc(100vh - 7rem);
  }
}

@media (max-width: 900px) {
  nav {
    flex-direction: column;
    align-items: flex-start;
  }

  .nav-groups {
    width: 100%;
    justify-content: space-between;
  }

  .nav-actions {
    width: 100%;
    justify-content: space-between;
  }

  .search-form {
    margin-left: auto;
  }
}

@media (max-width: 720px) {
  .nav-groups {
    flex-direction: column;
    align-items: stretch;
    gap: 1rem;
  }

  .nav-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 0.9rem;
  }

  .search-form {
    width: 100%;
  }

  .search-form input {
    min-width: 0;
    flex: 1;
  }

  .theme-toggle-label {
    justify-content: space-between;
    width: 100%;
  }

  .feed-header {
    align-items: stretch;
  }

  .feed-controls {
    width: 100%;
    justify-content: center;
  }

  .feed-sort {
    flex: 1 1 auto;
    text-align: center;
  }

  .hero {
    padding: 3rem 1.25rem;
  }
}

@media (max-width: 540px) {
  nav {
    padding: 0.9rem 1.2rem;
  }

  .logo {
    font-size: 1.15rem;
  }

  .page-shell {
    padding: 2rem 1.25rem 3rem;
  }

  .grid {
    grid-template-columns: 1fr;
  }

  .feed-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }

  .card:hover,
  .button-link:hover,
  .cta-button:hover,
  .cta-secondary:hover,
  .pill-link:hover,
  .value-card:hover,
  .search-result:hover {
    transform: none !important;
    box-shadow: none !important;
  }
}
"""

DEFAULT_SOCIAL_IMAGE = "https://source.unsplash.com/1200x630/?gifts"


@dataclass
class PageContext:
    title: str
    description: str
    canonical_url: str
    body: str
    og_image: str | None = None
    structured_data: List[dict] | None = None
    og_type: str = "website"
    og_image_alt: str | None = None
    updated_time: str | None = None
    published_time: str | None = None
    extra_head: str = ""
    noindex: bool = False


class SiteGenerator:
    """Generate static HTML pages for the Grab Gifts experience."""

    def __init__(
        self,
        settings: SiteSettings,
        *,
        output_dir: Path | None = None,
    ) -> None:
        ensure_directories()
        self.settings = settings
        self.output_dir = output_dir or OUTPUT_DIR
        self.assets_dir = self.output_dir / "assets"
        self.categories_dir = self.output_dir / "categories"
        self.products_dir = self.output_dir / "products"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.categories_dir.mkdir(parents=True, exist_ok=True)
        self.products_dir.mkdir(parents=True, exist_ok=True)
        self._nav_cache: List[Category] = []
        self._category_lookup: dict[str, Category] = {}
        self._has_deals_page = False
        self._deals_products: List[Product] = []

    def build(self, categories: List[Category], products: List[Product]) -> None:
        logger.info("Generating site with %s products", len(products))
        self._write_assets()
        self.preload_navigation(categories)
        self._category_lookup = {category.slug: category for category in categories}
        self._has_deals_page = False
        self._deals_products = []
        products_sorted = sorted(products, key=lambda p: p.updated_at, reverse=True)
        self._deals_products = self._select_deals_products(products_sorted)
        self._has_deals_page = bool(self._deals_products)
        if self._has_deals_page:
            self._write_deals_page(self._deals_products)
        self._write_index(categories, products_sorted[:12], products_sorted)
        self._write_latest_page(products_sorted)
        self._write_search_page(categories, products_sorted)
        for category in categories:
            category_products = [
                product
                for product in products_sorted
                if product.category_slug == category.slug
            ]
            self._write_category_page(category, category_products)
            for product in category_products:
                related = [
                    candidate
                    for candidate in category_products
                    if candidate.asin != product.asin
                ][:3]
                self._write_product_page(product, category, related)
        self._write_feed(products_sorted)
        self._write_sitemap(categories, products_sorted)

    # ------------------------------------------------------------------
    # Rendering helpers
    def _layout(self, context: PageContext) -> str:
        adsense = ""
        if self.settings.adsense_client_id:
            adsense = (
                "<script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client="
                f"{self.settings.adsense_client_id}\" crossorigin=\"anonymous\"></script>"
            )
        analytics_snippet = ""
        if getattr(self.settings, "analytics_snippet", None):
            analytics_snippet = self.settings.analytics_snippet or ""
        elif getattr(self.settings, "analytics_measurement_id", None):
            raw_measurement = self.settings.analytics_measurement_id or ""
            safe_attr_id = html.escape(raw_measurement)
            js_measurement = raw_measurement.replace("\\", "\\\\").replace("'", "\\'")
            analytics_snippet = (
                f'<script async src="https://www.googletagmanager.com/gtag/js?id={safe_attr_id}"></script>'
                "\n"
                "<script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}"
                "gtag('js', new Date());"
                f"gtag('config', '{js_measurement}');</script>"
            )
        analytics_block = (
            "\n    " + analytics_snippet.replace("\n", "\n    ")
            if analytics_snippet
            else ""
        )
        meta_description = html.escape(context.description)
        meta_title = html.escape(context.title)
        canonical = html.escape(context.canonical_url)
        language_value = (self.settings.language or "en").strip()
        language = html.escape(language_value or "en")
        locale_value = (self.settings.locale or "en_US").strip()
        locale = html.escape(locale_value or "en_US")
        og_type_value = (context.og_type or "website").strip()
        if not og_type_value:
            og_type_value = "website"
        og_type = html.escape(og_type_value)
        nav_links = "".join(
            f"<a href=\"/{self._category_path(slug)}\">{html.escape(name)}</a>"
            for slug, name in self._navigation_links()
        )
        nav_action_links = ['<a href="/latest.html">Latest drops</a>']
        if self._has_deals_page:
            nav_action_links.append('<a href="/deals.html">Deals</a>')
        nav_action_links.append(
            '<button type="button" class="pill-link nav-surprise" data-surprise>Deal me in</button>'
        )
        newsletter_link = None
        newsletter_attrs = ""
        if getattr(self.settings, "newsletter_url", None):
            newsletter_link = html.escape(self.settings.newsletter_url)
            newsletter_attrs = ' target="_blank" rel="noopener"'
        elif getattr(self.settings, "newsletter_form_action", None):
            newsletter_link = "#newsletter"
        if newsletter_link:
            nav_action_links.append(
                f'<a class="pill-link" href="{newsletter_link}"{newsletter_attrs}>Newsletter</a>'
            )
        search_form = (
            "<form class=\"search-form\" action=\"/search.html\" method=\"get\" role=\"search\">"
            "<label class=\"sr-only\" for=\"nav-search\">Search Grab Gifts</label>"
            "<input id=\"nav-search\" type=\"search\" name=\"q\" placeholder=\"Search gift drops...\" aria-label=\"Search Grab Gifts\" />"
            "<button type=\"submit\" aria-label=\"Submit search\">"
            "<svg aria-hidden=\"true\" width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"11\" cy=\"11\" r=\"7\"></circle><line x1=\"20\" y1=\"20\" x2=\"16.65\" y2=\"16.65\"></line></svg>"
            "</button>"
            "</form>"
        )
        theme_toggle = (
            "<div class=\"theme-toggle\">"
            "<input class=\"theme-toggle-input\" type=\"checkbox\" id=\"theme-switch\" role=\"switch\" aria-label=\"Toggle dark mode\" aria-checked=\"false\" />"
            "<label class=\"theme-toggle-label\" for=\"theme-switch\">"
            "<span class=\"theme-toggle-text\">Theme</span>"
            "<span class=\"theme-toggle-icon theme-toggle-icon--sun\" aria-hidden=\"true\">"
            "<svg aria-hidden=\"true\" width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"5\"></circle><line x1=\"12\" y1=\"1\" x2=\"12\" y2=\"3\"></line><line x1=\"12\" y1=\"21\" x2=\"12\" y2=\"23\"></line><line x1=\"4.22\" y1=\"4.22\" x2=\"5.64\" y2=\"5.64\"></line><line x1=\"18.36\" y1=\"18.36\" x2=\"19.78\" y2=\"19.78\"></line><line x1=\"1\" y1=\"12\" x2=\"3\" y2=\"12\"></line><line x1=\"21\" y1=\"12\" x2=\"23\" y2=\"12\"></line><line x1=\"4.22\" y1=\"19.78\" x2=\"5.64\" y2=\"18.36\"></line><line x1=\"18.36\" y1=\"5.64\" x2=\"19.78\" y2=\"4.22\"></line></svg>"
            "</span>"
            "<span class=\"theme-toggle-track\" aria-hidden=\"true\"><span class=\"theme-toggle-thumb\"></span></span>"
            "<span class=\"theme-toggle-icon theme-toggle-icon--moon\" aria-hidden=\"true\">"
            "<svg aria-hidden=\"true\" width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M21 12.79A9 9 0 0 1 11.21 3 7 7 0 0 0 12 21a9 9 0 0 0 9-8.21z\"></path></svg>"
            "</span>"
            "</label>"
            "</div>"
        )
        nav_actions_html = " ".join(
            part for part in [theme_toggle, " ".join(nav_action_links), search_form] if part
        )
        keywords_meta = ""
        if getattr(self.settings, "keywords", ()):  # type: ignore[attr-defined]
            keywords = ", ".join(html.escape(keyword) for keyword in self.settings.keywords)
            keywords_meta = f'<meta name="keywords" content="{keywords}" />'
        robots_meta = (
            "<meta name=\"robots\" content=\"noindex, nofollow\" />"
            if context.noindex
            else "<meta name=\"robots\" content=\"index, follow\" />"
        )
        feed_link = (
            f'<link rel="alternate" type="application/rss+xml" title="{html.escape(self.settings.site_name)} RSS" href="/feed.xml" />'
        )
        favicon_link = ""
        if self.settings.favicon_url:
            favicon_link = (
                f'<link rel="icon" href="{html.escape(self.settings.favicon_url)}" />'
            )
        theme_bootstrap = (
            "<script>"
            "(function(){"
            "var storageKey='grabgifts-theme';"
            "var root=document.documentElement;"
            "if(!root){return;}"
            "var stored=null;"
            "try{stored=window.localStorage.getItem(storageKey);}catch(error){stored=null;}"
            "var theme=stored;"
            "if(theme!=='light'&&theme!=='dark'){"
            "var media=window.matchMedia('(prefers-color-scheme: dark)');"
            "theme=media&&media.matches?'dark':'light';"
            "}"
            "root.setAttribute('data-theme', theme||'light');"
            "})();"
            "</script>"
        )
        og_image_meta = ""
        if context.og_image:
            image = html.escape(context.og_image)
            og_parts = [
                f'<meta property="og:image" content="{image}" />',
                f'<meta name="twitter:image" content="{image}" />',
            ]
            if context.og_image_alt:
                alt = html.escape(context.og_image_alt)
                og_parts.append(f'<meta property="og:image:alt" content="{alt}" />')
                og_parts.append(f'<meta name="twitter:image:alt" content="{alt}" />')
            og_image_meta = "\n    ".join(og_parts)
        twitter_meta_lines = [
            '<meta name="twitter:card" content="summary_large_image" />',
            f'<meta name="twitter:title" content="{meta_title}" />',
            f'<meta name="twitter:description" content="{meta_description}" />',
        ]
        if self.settings.twitter_handle:
            handle = self.settings.twitter_handle
            if not handle.startswith("@"):
                handle = f"@{handle}"
            safe_handle = html.escape(handle)
            twitter_meta_lines.append(
                f'<meta name="twitter:site" content="{safe_handle}" />'
            )
            twitter_meta_lines.append(
                f'<meta name="twitter:creator" content="{safe_handle}" />'
            )
        twitter_meta = "\n    ".join(twitter_meta_lines)
        facebook_meta = ""
        if self.settings.facebook_page:
            facebook_meta = (
                f'<meta property="article:publisher" content="{html.escape(self.settings.facebook_page)}" />'
            )
        updated_meta = ""
        if context.updated_time:
            updated = html.escape(context.updated_time)
            updated_parts = [
                f'<meta property="og:updated_time" content="{updated}" />'
            ]
            if og_type_value != "website":
                updated_parts.append(
                    f'<meta property="article:modified_time" content="{updated}" />'
                )
            updated_meta = "\n    ".join(updated_parts)
        published_meta = ""
        if context.published_time and og_type_value != "website":
            published_meta = (
                f'<meta property="article:published_time" content="{html.escape(context.published_time)}" />'
            )
        adsense_slot = ""
        if self._adsense_inline_enabled():
            adsense_slot = self._adsense_unit(
                self.settings.adsense_slot or "",
                extra_class="adsense-slot--footer",
            )
        rail_html = ""
        rail_slot_id = getattr(self.settings, "adsense_rail_slot", None)
        if self.settings.adsense_client_id and rail_slot_id:
            rail_unit = self._adsense_unit(
                rail_slot_id,
                extra_class="adsense-slot--rail",
            )
            if rail_unit:
                rail_html = (
                    "\n      <aside class=\"ad-rail\" role=\"complementary\" aria-label=\"Sponsored placements\">"
                    "\n        <div class=\"ad-rail-inner\">"
                    "\n          <span class=\"ad-rail-label\">Advertisement</span>"
                    f"\n          {rail_unit}"
                    "\n        </div>"
                    "\n      </aside>"
                )
        structured_json = ""
        if context.structured_data:
            scripts = []
            for data in context.structured_data:
                json_blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
                scripts.append(f'<script type="application/ld+json">{json_blob}</script>')
            structured_json = "\n    ".join(scripts)
        extra_head = context.extra_head or ""
        structured_block = f"\n    {structured_json}" if structured_json else ""
        extra_head_block = f"\n    {extra_head}" if extra_head else ""
        now = datetime.utcnow()
        footer_links_parts = ['<a href="/index.html">Home</a>', '<a href="/latest.html">Latest finds</a>']
        if self._has_deals_page:
            footer_links_parts.append('<a href="/deals.html">Deals</a>')
        if getattr(self.settings, "newsletter_url", None):
            newsletter_url = html.escape(self.settings.newsletter_url)
            footer_links_parts.append(
                f'<a href="{newsletter_url}" target="_blank" rel="noopener">Newsletter</a>'
            )
        elif getattr(self.settings, "newsletter_form_action", None):
            footer_links_parts.append('<a href="#newsletter">Newsletter</a>')
        if getattr(self.settings, "contact_email", None):
            footer_links_parts.append(
                f'<a href="mailto:{html.escape(self.settings.contact_email)}">Contact</a>'
            )
        footer_links = ""
        if footer_links_parts:
            footer_links = f"<div class=\"footer-links\">{' '.join(footer_links_parts)}</div>"
        return f"""<!DOCTYPE html>
<html lang=\"{language}\" data-theme=\"light\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{meta_title}</title>
    <meta name=\"description\" content=\"{meta_description}\" />
    {robots_meta}
    <link rel=\"canonical\" href=\"{canonical}\" />
    {feed_link}
    {theme_bootstrap}
    <link rel=\"stylesheet\" href=\"/assets/styles.css\" />
    {favicon_link}
    {adsense}{analytics_block}
    {keywords_meta}
    <meta property=\"og:type\" content=\"{og_type}\" />
    <meta property=\"og:title\" content=\"{meta_title}\" />
    <meta property=\"og:description\" content=\"{meta_description}\" />
    <meta property=\"og:url\" content=\"{canonical}\" />
    <meta property=\"og:site_name\" content=\"{html.escape(self.settings.site_name)}\" />
    <meta property=\"og:locale\" content=\"{locale}\" />
    {og_image_meta}
    {updated_meta}
    {published_meta}
    {twitter_meta}
    {facebook_meta}{structured_block}{extra_head_block}
  </head>
  <body>
    <a class=\"skip-link\" href=\"#main-content\">Skip to content</a>
    <header>
      <nav aria-label=\"Primary\">
        <a href=\"/index.html\" class=\"logo\">{html.escape(self.settings.site_name)}</a>
        <div class=\"nav-groups\">
          <div class=\"nav-links\">{nav_links}</div>
          <div class=\"nav-actions\">{nav_actions_html}</div>
        </div>
      </nav>
    </header>
    <div class=\"page-shell\">
      <main id=\"main-content\" class=\"page-main\">
        {context.body}
        {adsense_slot}
      </main>{rail_html}
    </div>
    <footer>
      <p>&copy; {now.year} {html.escape(self.settings.site_name)}. Updated {html.escape(now.strftime('%b %d, %Y'))}.</p>
      <p>As an Amazon Associate we earn from qualifying purchases. Links may generate affiliate revenue.</p>
      {footer_links}
    </footer>
    <script>
      (function() {{
        var storageKey = 'grabgifts-theme';
        var root = document.documentElement;
        var toggle = document.getElementById('theme-switch');
        var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

        function setToggleState(theme) {{
          if (!toggle) {{
            return;
          }}
          var isDark = theme === 'dark';
          toggle.checked = isDark;
          toggle.setAttribute('aria-checked', String(isDark));
        }}

        function applyTheme(next) {{
          var theme = next === 'dark' ? 'dark' : 'light';
          root.setAttribute('data-theme', theme);
          setToggleState(theme);
        }}

        function readPreference() {{
          try {{
            return window.localStorage.getItem(storageKey);
          }} catch (error) {{
            return null;
          }}
        }}

        function storePreference(value) {{
          try {{
            window.localStorage.setItem(storageKey, value);
          }} catch (error) {{
            return;
          }}
        }}

        var saved = readPreference();
        if (saved === 'dark' || saved === 'light') {{
          applyTheme(saved);
        }} else {{
          applyTheme(mediaQuery.matches ? 'dark' : 'light');
        }}

        mediaQuery.addEventListener('change', function (event) {{
          if (!readPreference()) {{
            applyTheme(event.matches ? 'dark' : 'light');
          }}
        }});

        if (toggle) {{
          toggle.addEventListener('change', function (event) {{
            var mode = event.target.checked ? 'dark' : 'light';
            applyTheme(mode);
            storePreference(mode);
          }});
        }}

        window.addEventListener('storage', function (event) {{
          if (event.key === storageKey) {{
            applyTheme(event.newValue === 'dark' ? 'dark' : 'light');
          }}
        }});
      }})();
    </script>
  </body>
</html>
"""

    def _write_assets(self) -> None:
        stylesheet_path = self.assets_dir / "styles.css"
        stylesheet_path.write_text(ASSETS_STYLES, encoding="utf-8")

    def _write_index(
        self,
        categories: List[Category],
        featured_products: List[Product],
        all_products: List[Product],
    ) -> None:
        cta_href = f"/{self._category_path(categories[0].slug)}" if categories else "#"
        hero_description = (
            f"{self.settings.description.strip()} "
            "Power through a shoppable feed of affiliate-ready gift drops fueled by live trend data."
        )
        hero = f"""
<section class=\"hero\">
  <span class=\"eyebrow\">Your viral gift playbook</span>
  <h1>{html.escape(self.settings.site_name)}</h1>
  <p>{html.escape(hero_description)}</p>
  <div class=\"hero-actions\">
    <a class=\"button-link\" href=\"{cta_href}\">Browse latest drops</a>
    <button type=\"button\" class=\"cta-secondary surprise-button\" data-surprise>Deal me in</button>
    <a class=\"cta-secondary\" href=\"/latest.html\">Watch today's reload</a>
  </div>
</section>
"""
        category_cards = "".join(
            self._category_card(category) for category in categories
        )
        feed_section = self._news_feed_section(all_products)
        category_section = f"""
<section>
  <div class=\"section-heading\">
    <h2>Shop by vibe</h2>
    <p>Dive into themed lineups built with click-magnetic copy, affiliate compliance, and ad inventory baked in.</p>
  </div>
  <div class=\"grid\">{category_cards}</div>
</section>
"""
        value_props = """
<section class=\"value-prop\">
  <div class=\"section-heading\">
    <h2>Why marketers love Grab Gifts</h2>
    <p>Plug in the automation, own the audience, and keep your gift commerce funnels roaring.</p>
  </div>
  <div class=\"value-grid\">
    <article class=\"value-card\">
      <span class=\"badge\">Storyselling</span>
      <h3>Copy that sparks clicks</h3>
      <p>Every card blends social proof angles, urgency cues, and SEO-primed structure to lift conversions.</p>
    </article>
    <article class=\"value-card\">
      <span class=\"badge\">Affiliate Fuel</span>
      <h3>Your tags, everywhere</h3>
      <p>Amazon and partner CTAs ship pre-wired with your tracking so every discovery turns into attributable revenue.</p>
    </article>
    <article class=\"value-card\">
      <span class=\"badge\">Always Fresh</span>
      <h3>Automation handles the grind</h3>
      <p>Nightly refreshes, trend scoring, and deal callouts keep the catalogue feeling like a live drop campaign.</p>
    </article>
  </div>
</section>
"""
        newsletter_banner = self._newsletter_banner()
        body = f"{hero}{feed_section}{category_section}{newsletter_banner}{value_props}"
        organization_data = self._organization_structured_data()
        website_schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": self.settings.site_name,
            "url": self.settings.base_url,
            "description": self.settings.description,
            "inLanguage": self.settings.language,
            "potentialAction": {
                "@type": "SearchAction",
                "target": f"{self.settings.base_url.rstrip('/')}/search.html?q={{search_term_string}}",
                "query-input": "required name=search_term_string",
            },
        }
        if organization_data:
            website_schema["publisher"] = organization_data
        structured_data = [
            website_schema,
            self._item_list_structured_data(
                "Featured gift ideas",
                [
                    (product.title, self._absolute_url(self._product_path(product)))
                    for product in featured_products
                ],
            ),
        ]
        if organization_data:
            structured_data.append(organization_data)
        og_image = None
        for product in featured_products:
            if product.image:
                og_image = product.image
                break
        if og_image is None:
            if self.settings.logo_url:
                og_image = self.settings.logo_url
            else:
                og_image = DEFAULT_SOCIAL_IMAGE
        latest_site_update = self._latest_updated_datetime(all_products)
        context = PageContext(
            title=f"{self.settings.site_name} — Daily gift drops that convert",
            description=self.settings.description,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/index.html",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
            og_image_alt=self.settings.site_name,
            updated_time=self._format_iso8601(latest_site_update),
        )
        self._write_page(self.output_dir / "index.html", context)

    def _news_feed_section(self, products: List[Product]) -> str:
        now = datetime.now(timezone.utc)
        feed_limit = len(products)
        feed_products = products[:feed_limit]
        feed_cards: List[str] = []
        pool_limit = min(len(products), 60)
        seen_urls: set[str] = set()
        surprise_pool: List[str] = []
        for product in products[:pool_limit]:
            url = f"/{self._product_path(product)}"
            if url not in seen_urls:
                seen_urls.add(url)
                surprise_pool.append(url)
        ads_enabled = self._adsense_inline_enabled()
        for index, product in enumerate(feed_products, start=1):
            updated_score, popularity_score, trending_score = self._news_feed_metrics(
                product, now
            )
            url = f"/{self._product_path(product)}"
            extra_attrs = (
                f'data-updated="{updated_score}" '
                f'data-popularity="{popularity_score:.2f}" '
                f'data-trending="{trending_score:.2f}" '
                f'data-url="{html.escape(url, quote=True)}"'
            )
            feed_cards.append(
                self._product_card(
                    product,
                    extra_attrs=extra_attrs,
                    extra_classes="feed-card",
                )
            )
            if ads_enabled and index % 5 == 0:
                ad_card = self._adsense_card()
                if ad_card:
                    if "<article" in ad_card:
                        ad_card = ad_card.replace(
                            "<article",
                            f'<article data-feed-ad-after="{index}" aria-hidden="true"',
                            1,
                        )
                    if 'class="card card--ad"' in ad_card:
                        ad_card = ad_card.replace(
                            'class="card card--ad"',
                            'class="card card--ad feed-card is-hidden"',
                            1,
                        )
                    feed_cards.append(ad_card)
        feed_grid = "".join(feed_cards)
        if not feed_cards:
            feed_grid = (
                "<p class=\"feed-empty\">More gift ideas are on the way. Check back after the next refresh.</p>"
            )
        feed_dom_id = "news-feed-grid"
        sentinel_html = ""
        if feed_cards:
            sentinel_html = (
                "<div class=\"feed-sentinel\" data-feed-sentinel aria-live=\"polite\">"
                "<button type=\"button\" class=\"feed-more\" data-feed-more aria-expanded=\"false\" "
                f"aria-controls=\"{feed_dom_id}\">Show more gift ideas</button>"
                "</div>"
            )
        surprise_json = json.dumps(surprise_pool, ensure_ascii=False).replace("</", "<\\/")
        section = f"""
<section class=\"news-feed\">
  <div class=\"feed-header\">
    <div>
      <span class=\"badge\">Daily drops</span>
      <h2>Grab Gifts live feed</h2>
      <p>Shuffle trending finds by freshest drops, breakout hits, or velocity to spotlight your next feature.</p>
    </div>
  <div class=\"feed-controls\" role=\"group\" aria-label=\"Sort Grab Gifts feed\">
      <button type=\"button\" class=\"feed-sort is-active\" data-feed-sort=\"updated\" aria-pressed=\"true\">Most recent</button>
      <button type=\"button\" class=\"feed-sort\" data-feed-sort=\"popularity\" aria-pressed=\"false\">Most popular</button>
      <button type=\"button\" class=\"feed-sort\" data-feed-sort=\"trending\" aria-pressed=\"false\">Trending</button>
    </div>
  </div>
  <div class=\"feed-grid\" id=\"{feed_dom_id}\" data-feed>{feed_grid}</div>
  {sentinel_html}
</section>
"""
        script = f"""
<script>
(function() {{
  const feed = document.querySelector('[data-feed]');
  if (!feed) {{
    return;
  }}
  const sortButtons = Array.from(document.querySelectorAll('[data-feed-sort]'));
  const sentinel = document.querySelector('[data-feed-sentinel]');
  const moreButton = sentinel ? sentinel.querySelector('[data-feed-more]') : null;
  const INITIAL_BATCH = 10;
  const BATCH_SIZE = 10;
  let cards = Array.from(feed.querySelectorAll('[data-updated]'));
  let visibleCount = Math.min(INITIAL_BATCH, cards.length);

  function refreshCards() {{
    cards = Array.from(feed.querySelectorAll('[data-updated]'));
  }}

  function updateAds() {{
    const adCards = Array.from(feed.querySelectorAll('[data-feed-ad-after]'));
    adCards.forEach(function (ad) {{
      const threshold = Number(ad.dataset.feedAdAfter || '0');
      const isVisible = visibleCount >= threshold;
      ad.classList.toggle('is-hidden', !isVisible);
      if (isVisible) {{
        ad.removeAttribute('aria-hidden');
      }} else {{
        ad.setAttribute('aria-hidden', 'true');
      }}
    }});
  }}

  function updateButtonState(hasMore) {{
    if (!moreButton) {{
      return;
    }}
    moreButton.disabled = cards.length === 0;
    moreButton.setAttribute('aria-expanded', hasMore ? 'false' : 'true');
  }}

  function updateSentinel() {{
    if (!sentinel) {{
      return;
    }}
    const hasMore = cards.length > visibleCount;
    if (hasMore) {{
      sentinel.removeAttribute('hidden');
      sentinel.setAttribute('aria-hidden', 'false');
    }} else {{
      sentinel.setAttribute('hidden', 'hidden');
      sentinel.setAttribute('aria-hidden', 'true');
    }}
    updateButtonState(hasMore);
  }}

  function applyVisibility() {{
    cards.forEach(function (card, index) {{
      const isVisible = index < visibleCount;
      card.classList.toggle('is-hidden', !isVisible);
      if (isVisible) {{
        card.removeAttribute('aria-hidden');
      }} else {{
        card.setAttribute('aria-hidden', 'true');
      }}
    }});
    updateAds();
    updateSentinel();
  }}

  function applySort(key, resetCount) {{
    const sortable = cards.slice().sort(function (a, b) {{
      return Number(b.dataset[key] || 0) - Number(a.dataset[key] || 0);
    }});
    const fragment = document.createDocumentFragment();
    const adCards = Array.from(feed.querySelectorAll('[data-feed-ad-after]'));
    const inserted = new Set();
    sortable.forEach(function (card, index) {{
      fragment.appendChild(card);
      const position = index + 1;
      adCards.forEach(function (ad) {{
        const after = Number(ad.dataset.feedAdAfter || '0');
        if (!inserted.has(ad) && after === position) {{
          inserted.add(ad);
          fragment.appendChild(ad);
        }}
      }});
    }});
    adCards.forEach(function (ad) {{
      if (!inserted.has(ad)) {{
        fragment.appendChild(ad);
      }}
    }});
    feed.textContent = '';
    feed.appendChild(fragment);
    refreshCards();
    if (resetCount) {{
      visibleCount = Math.min(INITIAL_BATCH, cards.length);
    }} else {{
      visibleCount = Math.min(visibleCount, cards.length);
    }}
    applyVisibility();
  }}

  function revealMore() {{
    if (visibleCount < cards.length) {{
      visibleCount = Math.min(cards.length, visibleCount + BATCH_SIZE);
      applyVisibility();
    }}
  }}

  sortButtons.forEach(function (button) {{
    button.addEventListener('click', function () {{
      const key = button.getAttribute('data-feed-sort');
      if (!key) {{
        return;
      }}
      sortButtons.forEach(function (item) {{
        const isActive = item === button;
        item.classList.toggle('is-active', isActive);
        item.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      }});
      applySort(key, true);
    }});
  }});

  applySort('updated', true);

  if (moreButton) {{
    moreButton.addEventListener('click', function () {{
      revealMore();
    }});
  }}

  if ('IntersectionObserver' in window && sentinel) {{
    const observer = new IntersectionObserver(function (entries) {{
      entries.forEach(function (entry) {{
        if (entry.isIntersecting) {{
          revealMore();
        }}
      }});
    }}, {{ rootMargin: '0px 0px 320px 0px' }});
    observer.observe(sentinel);
  }}

  const surpriseButtons = Array.from(document.querySelectorAll('[data-surprise]'));
  const surpriseTargets = {surprise_json};
  if (surpriseButtons.length && surpriseTargets.length) {{
    surpriseButtons.forEach(function (button) {{
      button.addEventListener('click', function (event) {{
        event.preventDefault();
        const index = Math.floor(Math.random() * surpriseTargets.length);
        const target = surpriseTargets[index];
        if (target) {{
          window.location.href = target;
        }}
      }});
    }});
  }}
}})();
</script>
"""
        return section + script

    def _write_category_page(self, category: Category, products: List[Product]) -> None:
        cards = self._product_cards_with_ads(products)
        keyword_query = quote_plus(" ".join(category.keywords))
        amazon_url = f"https://www.amazon.com/s?k={keyword_query}"
        if self.settings.amazon_partner_tag:
            partner_tag = quote_plus(self.settings.amazon_partner_tag)
            amazon_url = f"{amazon_url}&tag={partner_tag}"
        amazon_url = html.escape(amazon_url, quote=True)
        newsletter_banner = self._newsletter_banner()
        body = f"""
<div class=\"breadcrumbs\"><a href=\"/index.html\">Home</a> &rsaquo; {html.escape(category.name)}</div>
<section class=\"category-hero\">
  <div>
    <span class=\"badge\">Category spotlight</span>
    <h1>{html.escape(category.name)}</h1>
    <p>{html.escape(category.blurb)}</p>
    <div class=\"hero-actions align-left\">
      <a class=\"cta-secondary\" href=\"/latest.html\">See the newest arrivals</a>
    </div>
  </div>
  <div>
    <a class=\"button-link\" href=\"{amazon_url}\" target=\"_blank\" rel=\"noopener sponsored\">Shop full Amazon results</a>
  </div>
</section>
<section>
  <div class=\"grid\">{cards}</div>
</section>
{newsletter_banner}
"""
        og_image = None
        for product in products:
            if product.image:
                og_image = product.image
                break
        if og_image is None:
            og_image = f"https://source.unsplash.com/1200x630/?{category.slug}"
        structured_data = [
            self._breadcrumb_structured_data(
                [
                    ("Home", self._absolute_url("index.html")),
                    (category.name, self._absolute_url(self._category_path(category.slug))),
                ]
            ),
            self._item_list_structured_data(
                f"{category.name} gift ideas",
                [
                    (product.title, self._absolute_url(self._product_path(product)))
                    for product in products
                ],
            ),
        ]
        category_last_updated = self._latest_updated_datetime(products)
        context = PageContext(
            title=f"{category.name} — {self.settings.site_name}",
            description=category.blurb,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/{self._category_path(category.slug)}",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
            og_image_alt=category.name,
            updated_time=self._format_iso8601(category_last_updated),
        )
        path = self.categories_dir / category.slug / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(path, context)

    def _write_product_page(self, product: Product, category: Category, related: List[Product]) -> None:
        price_line = (
            f'<p class="price-callout">{html.escape(product.price)}</p>'
            if product.price
            else ""
        )
        rating_line = (
            f'<p class="review-callout">{product.rating:.1f} / 5.0 ({product.total_reviews:,} reviews)</p>'
            if product.rating and product.total_reviews
            else ""
        )
        retailer_line = ""
        if product.retailer_name:
            retailer_target = product.retailer_homepage or product.link
            retailer_name_html = html.escape(product.retailer_name)
            if retailer_target:
                retailer_line = (
                    f'<p class="retailer-callout">Sourced from <a href="{html.escape(retailer_target)}" target="_blank" rel="noopener">{retailer_name_html}</a>.</p>'
                )
            else:
                retailer_line = f'<p class="retailer-callout">Sourced from {retailer_name_html}.</p>'
        latest_point = product.latest_price_point
        previous_point = product.previous_price_point
        price_drop = product.price_drop_amount()
        price_change = product.price_change_amount()
        percent_drop = product.price_drop_percent()
        deal_line = ""
        if price_line:
            if price_drop is not None and latest_point and previous_point:
                drop_text = self._format_currency(price_drop, latest_point.currency)
                prev_label = self._format_price_point_label(previous_point)
                detail = drop_text
                if percent_drop is not None:
                    detail = f"{detail} ({percent_drop:.0f}% drop)"
                deal_line = (
                    f'<p class="deal-callout">Price dropped {html.escape(detail)} since {html.escape(prev_label)}.</p>'
                )
            elif price_change is not None and price_change > 0 and latest_point and previous_point:
                increase_text = self._format_currency(price_change, latest_point.currency)
                prev_label = self._format_price_point_label(previous_point)
                deal_line = (
                    f'<p class="deal-callout deal-callout--up">Price climbed {html.escape(increase_text)} since {html.escape(prev_label)}.</p>'
                )
            elif product.price_history:
                first_label = self._format_price_point_label(product.price_history[0])
                deal_line = (
                    f'<p class="deal-callout">Tracking this listing since {html.escape(first_label)} for quick deal alerts.</p>'
                )
        related_section = ""
        if related:
            related_cards = "".join(self._product_card(item) for item in related)
            related_section = f"""
<section class="related-grid">
  <h2>More {html.escape(category.name)} hits</h2>
  <div class="grid">{related_cards}</div>
</section>
""".strip()
        breadcrumbs_html = (
            f'<div class="breadcrumbs"><a href="/index.html">Home</a> &rsaquo; <a href="/{self._category_path(category.slug)}">{html.escape(category.name)}</a></div>'
        )
        image_url = product.image or f"https://source.unsplash.com/1200x630/?{category.slug}"
        updated_dt = self._parse_iso_datetime(product.updated_at)
        published_dt = self._parse_iso_datetime(product.created_at)
        price_value, price_currency = self._extract_price_components(product.price)
        currency_code = price_currency or "USD"
        extra_head_parts = [
            f'<meta property="product:retailer_item_id" content="{html.escape(product.asin)}" />',
        ]
        if price_value:
            extra_head_parts.append(
                f'<meta property="product:price:amount" content="{html.escape(price_value)}" />'
            )
            extra_head_parts.append(
                f'<meta property="product:price:currency" content="{html.escape(currency_code)}" />'
            )
        extra_head_parts.append('<meta property="product:availability" content="in stock" />')
        extra_head = "\n    ".join(extra_head_parts)
        canonical_url = self._absolute_url(self._product_path(product))
        encoded_url = quote_plus(canonical_url)
        encoded_title = quote_plus(product.title)
        tweet_url = f"https://twitter.com/intent/tweet?text={encoded_title}&url={encoded_url}"
        facebook_url = f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}"
        engagement_html = f"""
<div class="engagement-tools">
  <button class="wishlist-toggle" type="button" data-wishlist="toggle" data-product="{html.escape(product.slug)}" aria-pressed="false">Save to shortlist</button>
  <div class="share-controls">
    <button class="share-primary" type="button" data-share>Share with a friend</button>
    <div class="share-links">
      <button class="share-copy" type="button" data-copy="{html.escape(canonical_url)}">Copy link</button>
      <a href="{tweet_url}" target="_blank" rel="noopener">Tweet</a>
      <a href="{facebook_url}" target="_blank" rel="noopener">Share</a>
    </div>
  </div>
</div>
""".strip()
        price_history_section = ""
        history_points = product.price_history_summary(6)
        if history_points:
            if price_drop is not None and latest_point and previous_point:
                drop_text = self._format_currency(price_drop, latest_point.currency)
                prev_label = self._format_price_point_label(previous_point)
                if percent_drop is not None:
                    price_message = f"Currently {drop_text} off ({percent_drop:.0f}% drop) since {prev_label}."
                else:
                    price_message = f"Currently {drop_text} under the last update from {prev_label}."
            elif price_change is not None and price_change > 0 and latest_point and previous_point:
                increase_text = self._format_currency(price_change, latest_point.currency)
                prev_label = self._format_price_point_label(previous_point)
                price_message = f"Trending up {increase_text} since {prev_label} — keep it bookmarked."
            else:
                first_label = self._format_price_point_label(history_points[0])
                price_message = f"Tracked pricing since {first_label} so you can time campaigns perfectly."
            history_rows = []
            for point in reversed(history_points):
                label = self._format_price_point_label(point)
                display = html.escape(point.display or product.price or "")
                history_rows.append(
                    f"    <li><span>{html.escape(label)}</span><strong>{display}</strong></li>"
                )
            rows_html = "\n".join(history_rows)
            price_history_section = f"""
<section class="price-insights">
  <h2>Price pulse</h2>
  <p>{html.escape(price_message)}</p>
  <ul class="price-history">
{rows_html}
  </ul>
</section>
""".strip()
        cta_block = ""
        if product.link:
            cta_label = product.call_to_action or f"Shop on {product.retailer_name}"
            cta_block = (
                f'<p class="cta-row"><a class="cta-button" href="{html.escape(product.link)}" target="_blank" rel="noopener sponsored">{html.escape(cta_label)}</a></p>'
            )
        body = f"""
{breadcrumbs_html}
<div class="product-page">
  <div>
    <img src="{html.escape(image_url)}" alt="{html.escape(product.title)}" loading="lazy" decoding="async" />
  </div>
  <div class="product-meta">
    <h1>{html.escape(product.title)}</h1>
    {price_line}
    {rating_line}
    {deal_line}
    {retailer_line}
    {product.blog_content or ''}
    {engagement_html}
    {cta_block}
  </div>
</div>
{price_history_section}
{related_section}
""".strip()
        js_slug = json.dumps(product.slug)
        js_link = json.dumps(canonical_url)
        js_title = json.dumps(product.title)
        wishlist_script = f"""
<script>
(function() {{
  const STORAGE_KEY = 'grabgifts-wishlist';
  const productId = {js_slug};
  const link = {js_link};
  const title = {js_title};
  const toggle = document.querySelector('[data-wishlist]');
  const shareButton = document.querySelector('[data-share]');
  const copyButton = document.querySelector('[data-copy]');
  function readList() {{
    try {{
      const raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    }} catch (error) {{
      return [];
    }}
  }}
  function writeList(list) {{
    try {{
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    }} catch (error) {{}}
  }}
  function updateState() {{
    if (!toggle) {{
      return;
    }}
    const list = readList();
    const active = list.includes(productId);
    toggle.setAttribute('aria-pressed', String(active));
    toggle.classList.toggle('is-active', active);
    toggle.textContent = active ? 'Saved to shortlist' : 'Save to shortlist';
  }}
  if (toggle) {{
    toggle.addEventListener('click', () => {{
      const list = readList();
      const index = list.indexOf(productId);
      if (index === -1) {{
        list.push(productId);
      }} else {{
        list.splice(index, 1);
      }}
      writeList(list);
      updateState();
    }});
    updateState();
  }}
  function copyLink() {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(link).catch(() => {{}});
    }} else {{
      const temp = document.createElement('input');
      temp.value = link;
      document.body.appendChild(temp);
      temp.select();
      try {{ document.execCommand('copy'); }} catch (error) {{}}
      document.body.removeChild(temp);
    }}
  }}
  if (copyButton) {{
    copyButton.addEventListener('click', () => {{
      copyLink();
      copyButton.textContent = 'Link copied!';
      window.setTimeout(() => {{ copyButton.textContent = 'Copy link'; }}, 2000);
    }});
  }}
  if (shareButton) {{
    shareButton.addEventListener('click', async () => {{
      if (navigator.share) {{
        try {{
          await navigator.share({{ title: title, url: link }});
          return;
        }} catch (error) {{}}
      }}
      copyLink();
      shareButton.textContent = 'Link copied!';
      window.setTimeout(() => {{ shareButton.textContent = 'Share with a friend'; }}, 2000);
    }});
  }}
}})();
</script>
""".strip()
        body += wishlist_script
        structured_data = [
            self._breadcrumb_structured_data(
                [
                    ("Home", self._absolute_url("index.html")),
                    (category.name, self._absolute_url(self._category_path(category.slug))),
                    (product.title, self._absolute_url(self._product_path(product))),
                ]
            ),
            self._product_structured_data(product, category),
        ]
        context = PageContext(
            title=f"{product.title} — {category.name} gift idea",
            description=product.summary or self.settings.description,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/{self._product_path(product)}",
            body=body,
            og_image=image_url,
            structured_data=structured_data,
            og_type="product",
            og_image_alt=product.title,
            updated_time=self._format_iso8601(updated_dt),
            published_time=self._format_iso8601(published_dt),
            extra_head=extra_head,
        )
        path = self.products_dir / product.slug / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(path, context)

    def _write_latest_page(self, products: List[Product]) -> None:
        cards = self._product_cards_with_ads(products[:60])
        body = f"""
<section class=\"latest-intro\">
  <div class=\"section-heading\">
    <h1>Latest gift drops</h1>
    <p>Keep tabs on the freshest Amazon discoveries and schedule them into campaigns before competitors notice.</p>
  </div>
  <div class=\"grid\">{cards}</div>
</section>
{self._newsletter_banner()}
"""
        structured_data = [
            self._item_list_structured_data(
                "Latest gift ideas",
                [
                    (product.title, self._absolute_url(self._product_path(product)))
                    for product in products[:30]
                ],
            )
        ]
        og_image = None
        for product in products:
            if product.image:
                og_image = product.image
                break
        if og_image is None:
            if self.settings.logo_url:
                og_image = self.settings.logo_url
            else:
                og_image = DEFAULT_SOCIAL_IMAGE
        latest_update = self._latest_updated_datetime(products)
        context = PageContext(
            title=f"Latest gift drops — {self.settings.site_name}",
            description="The newest Grab Gifts drops from Amazon and partners, refreshed automatically for maximum conversion potential.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/latest.html",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
            og_image_alt="Latest gift drops",
            updated_time=self._format_iso8601(latest_update),
        )
        self._write_page(self.output_dir / "latest.html", context)

    def _write_deals_page(self, products: List[Product]) -> None:
        if not products:
            return
        top_products = products[:60]
        cards = self._product_cards_with_ads(top_products)
        body = f"""
<section class=\"latest-intro deals-hero\">
  <div class=\"section-heading\">
    <h1>Today's best gift deals</h1>
    <p>Track the steepest price drops in our catalog and surface high-converting offers while they're hot.</p>
  </div>
  <div class=\"grid\">{cards}</div>
</section>
{self._newsletter_banner()}
"""
        structured_data = [
            self._breadcrumb_structured_data(
                [
                    ("Home", self._absolute_url("index.html")),
                    ("Deals", self._absolute_url("deals.html")),
                ]
            ),
            self._item_list_structured_data(
                "Top gift deals",
                [
                    (product.title, self._absolute_url(self._product_path(product)))
                    for product in top_products[:30]
                ],
            ),
        ]
        organization_data = self._organization_structured_data()
        if organization_data:
            structured_data.append(organization_data)
        og_image = None
        for product in top_products:
            if product.image:
                og_image = product.image
                break
        if og_image is None:
            if self.settings.logo_url:
                og_image = self.settings.logo_url
            else:
                og_image = DEFAULT_SOCIAL_IMAGE
        latest_update = self._latest_updated_datetime(top_products)
        context = PageContext(
            title=f"Gift deals — {self.settings.site_name}",
            description="See the biggest price drops across Grab Gifts' Amazon finds, refreshed daily.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/deals.html",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
            og_image_alt="Featured gift deals",
            updated_time=self._format_iso8601(latest_update),
        )
        self._write_page(self.output_dir / "deals.html", context)

    def _write_search_page(self, categories: List[Category], products: List[Product]) -> None:
        category_lookup = {category.slug: category.name for category in categories}
        index_entries = []
        for product in products:
            raw_keywords = product.keywords or []
            keywords = [keyword.strip() for keyword in raw_keywords if keyword and keyword.strip()]
            keyword_blob = " ".join(keyword.lower() for keyword in keywords)
            latest_point = product.latest_price_point
            price_value = latest_point.amount if latest_point else None
            price_display = product.price or (latest_point.display if latest_point else None)
            index_entries.append(
                {
                    "title": product.title,
                    "summary": product.summary or "",
                    "url": f"/{self._product_path(product)}",
                    "category": category_lookup.get(product.category_slug, ""),
                    "categorySlug": product.category_slug,
                    "keywords": keywords,
                    "keywordBlob": keyword_blob,
                    "priceValue": price_value,
                    "priceDisplay": price_display,
                    "rating": product.rating,
                    "retailerName": product.retailer_name,
                    "retailerSlug": product.retailer_slug,
                }
            )
        dataset = json.dumps(index_entries, ensure_ascii=False).replace("</", "<\/")
        body = f"""
<section class="search-page">
  <h1>Search Grab Gifts</h1>
  <p>Zero in on conversion-ready gift drops by keyword, price point, rating, or marketplace partner.</p>
  <form id="search-page-form" class="search-form" action="/search.html" method="get" role="search">
    <label class="sr-only" for="search-query">Search Grab Gifts</label>
    <input id="search-query" type="search" name="q" placeholder="Type a product, keyword, or vibe" aria-label="Search Grab Gifts" />
    <button type="submit" aria-label="Submit search">
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><line x1="20" y1="20" x2="16.65" y2="16.65"></line></svg>
    </button>
  </form>
  <div class="search-filters" role="group" aria-label="Filter search results">
    <label for="filter-price">Price</label>
    <select id="filter-price" name="price">
      <option value="all">Any price</option>
      <option value="under-25">Under $25</option>
      <option value="25-50">$25 – $50</option>
      <option value="50-100">$50 – $100</option>
      <option value="100-plus">$100+</option>
    </select>
    <label for="filter-rating">Rating</label>
    <select id="filter-rating" name="rating">
      <option value="all">Any rating</option>
      <option value="4">4★ &amp; up</option>
      <option value="4.5">4.5★ &amp; up</option>
    </select>
    <label for="filter-retailer">Retailer</label>
    <select id="filter-retailer" name="retailer">
      <option value="all">All partners</option>
    </select>
  </div>
  <div id="search-feedback" class="search-empty" role="status" aria-live="polite" aria-atomic="true">Start typing to reveal the latest gift ideas.</div>
  <ol id="search-results" class="search-results" aria-live="polite"></ol>
</section>
<script>
const PRODUCT_INDEX = {dataset};
const form = document.getElementById('search-page-form');
const input = document.getElementById('search-query');
const feedback = document.getElementById('search-feedback');
const resultsList = document.getElementById('search-results');
const priceSelect = document.getElementById('filter-price');
const ratingSelect = document.getElementById('filter-rating');
const retailerSelect = document.getElementById('filter-retailer');
const retailerMap = new Map();
for (const item of PRODUCT_INDEX) {{
  if (item.retailerSlug && !retailerMap.has(item.retailerSlug)) {{
    retailerMap.set(item.retailerSlug, item.retailerName || item.retailerSlug);
  }}
}}
for (const [slug, name] of retailerMap.entries()) {{
  const option = document.createElement('option');
  option.value = slug;
  option.textContent = name;
  retailerSelect.appendChild(option);
}}
function getFilters() {{
  return {{
    price: priceSelect.value || 'all',
    rating: ratingSelect.value || 'all',
    retailer: retailerSelect.value || 'all',
  }};
}}
function matchesFilters(item, filters) {{
  if (filters.price !== 'all') {{
    const value = typeof item.priceValue === 'number' ? item.priceValue : null;
    if (value === null) {{
      return false;
    }}
    if (filters.price === 'under-25' && value >= 25) {{
      return false;
    }}
    if (filters.price === '25-50' && (value < 25 || value > 50)) {{
      return false;
    }}
    if (filters.price === '50-100' && (value < 50 || value > 100)) {{
      return false;
    }}
    if (filters.price === '100-plus' && value < 100) {{
      return false;
    }}
  }}
  if (filters.rating !== 'all') {{
    const minRating = parseFloat(filters.rating);
    if (!item.rating || item.rating < minRating) {{
      return false;
    }}
  }}
  if (filters.retailer !== 'all' && item.retailerSlug !== filters.retailer) {{
    return false;
  }}
  return true;
}}
function matchesQuery(item, normalized, hasQuery) {{
  if (!hasQuery) {{
    return true;
  }}
  if (item.title.toLowerCase().includes(normalized)) {{
    return true;
  }}
  if ((item.summary || '').toLowerCase().includes(normalized)) {{
    return true;
  }}
  if (item.category && item.category.toLowerCase().includes(normalized)) {{
    return true;
  }}
  if (item.keywordBlob && item.keywordBlob.includes(normalized)) {{
    return true;
  }}
  if (Array.isArray(item.keywords)) {{
    return item.keywords.some((keyword) => (keyword || '').toLowerCase().includes(normalized));
  }}
  return false;
}}
function renderResults(query, filters) {{
  resultsList.innerHTML = '';
  const hasQuery = Boolean(query);
  const hasFilters = filters.price !== 'all' || filters.rating !== 'all' || filters.retailer !== 'all';
  if (!hasQuery && !hasFilters) {{
    feedback.textContent = 'Start typing to reveal the latest gift ideas.';
    return;
  }}
  const normalized = query.toLowerCase();
  const matches = PRODUCT_INDEX.filter((item) => {{
    return matchesQuery(item, normalized, hasQuery) && matchesFilters(item, filters);
  }}).slice(0, 60);
  if (!matches.length) {{
    feedback.textContent = 'No matching gifts yet — try a different keyword or adjust the filters.';
    return;
  }}
  feedback.textContent = `Showing ${{matches.length}} conversion-ready picks.`;
  const frag = document.createDocumentFragment();
  for (const match of matches) {{
    const li = document.createElement('li');
    li.className = 'search-result';
    const heading = document.createElement('h3');
    const link = document.createElement('a');
    link.href = match.url;
    link.textContent = match.title;
    heading.appendChild(link);
    li.appendChild(heading);
    const summary = document.createElement('p');
    summary.textContent = match.summary || 'Tap through to read the full hype breakdown.';
    li.appendChild(summary);
    const metaParts = [];
    if (match.priceDisplay) {{
      metaParts.push(match.priceDisplay);
    }}
    if (typeof match.rating === 'number') {{
      metaParts.push(`${{match.rating.toFixed(1)}}★`);
    }}
    if (match.retailerName) {{
      metaParts.push(match.retailerName);
    }}
    if (metaParts.length) {{
      const meta = document.createElement('p');
      meta.className = 'search-meta';
      meta.textContent = metaParts.join(' • ');
      li.appendChild(meta);
    }}
    if (match.category) {{
      const badge = document.createElement('p');
      badge.className = 'badge';
      badge.textContent = match.category;
      li.appendChild(badge);
    }}
    frag.appendChild(li);
  }}
  resultsList.appendChild(frag);
}}
function updateUrl(query, filters) {{
  const url = new URL(window.location.href);
  if (query) {{
    url.searchParams.set('q', query);
  }} else {{
    url.searchParams.delete('q');
  }}
  for (const [key, value] of Object.entries(filters)) {{
    if (value && value !== 'all') {{
      url.searchParams.set(key, value);
    }} else {{
      url.searchParams.delete(key);
    }}
  }}
  window.history.replaceState(null, '', url.toString());
}}
function applyState() {{
  const filters = getFilters();
  const query = input.value.trim();
  updateUrl(query, filters);
  renderResults(query, filters);
}}
const params = new URLSearchParams(window.location.search);
const initial = (params.get('q') || '').trim();
const initialFilters = {{
  price: params.get('price') || 'all',
  rating: params.get('rating') || 'all',
  retailer: params.get('retailer') || 'all',
}};
const priceOptions = new Set(['all', 'under-25', '25-50', '50-100', '100-plus']);
const ratingOptions = new Set(['all', '4', '4.5']);
if (!priceOptions.has(initialFilters.price)) {{
  initialFilters.price = 'all';
}}
if (!ratingOptions.has(initialFilters.rating)) {{
  initialFilters.rating = 'all';
}}
if (initialFilters.retailer && !retailerMap.has(initialFilters.retailer)) {{
  initialFilters.retailer = 'all';
}}
input.value = initial;
priceSelect.value = initialFilters.price;
ratingSelect.value = initialFilters.rating;
retailerSelect.value = initialFilters.retailer;
applyState();
form.addEventListener('submit', (event) => {{
  event.preventDefault();
  applyState();
}});
input.addEventListener('input', () => {{
  applyState();
}});
priceSelect.addEventListener('change', () => {{
  applyState();
}});
ratingSelect.addEventListener('change', () => {{
  applyState();
}});
retailerSelect.addEventListener('change', () => {{
  applyState();
}});
</script>
"""
        structured_data = [
            {
                "@context": "https://schema.org",
                "@type": "SearchResultsPage",
                "name": f"Search {self.settings.site_name}",
                "description": "Search Grab Gifts for conversion-ready Amazon finds across every category.",
                "url": f"{self.settings.base_url.rstrip('/')}/search.html",
            }
        ]
        context = PageContext(
            title=f"Search gifts — {self.settings.site_name}",
            description="Search Grab Gifts for conversion-ready Amazon ideas instantly.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/search.html",
            body=body,
            structured_data=structured_data,
            noindex=True,
        )
        self._write_page(self.output_dir / "search.html", context)

    def _write_feed(self, products: List[Product]) -> None:
        item_blocks: List[str] = []
        if self._has_deals_page and self._deals_products:
            first_deal = self._deals_products[0]
            description = "Spot today's top price drops on Grab Gifts finds."
            if first_deal.title:
                description = f"Spot today's top price drops including {first_deal.title}."
            deals_pub = getattr(first_deal, "updated_at", "") or ""
            item_blocks.append(
                f"""
    <item>
      <title>Today's gift deals</title>
      <link>{html.escape(self._absolute_url('deals.html'))}</link>
      <guid>{html.escape('deals')}</guid>
      <description>{html.escape(description)}</description>
      <pubDate>{html.escape(deals_pub)}</pubDate>
    </item>
"""
            )
        item_blocks.extend(
            f"""
    <item>
      <title>{html.escape(product.title)}</title>
      <link>{html.escape(self._absolute_url(self._product_path(product)))}</link>
      <guid>{html.escape(product.asin)}</guid>
      <description>{html.escape(product.summary or '')}</description>
      <pubDate>{html.escape(product.updated_at)}</pubDate>
    </item>
"""
            for product in products[:30]
        )
        items = "".join(item_blocks)
        rss = f"""
<?xml version=\"1.0\" encoding=\"UTF-8\" ?>
<rss version=\"2.0\">
  <channel>
    <title>{html.escape(self.settings.site_name)}</title>
    <link>{html.escape(self.settings.base_url)}</link>
    <description>{html.escape(self.settings.description)}</description>
    {items}
  </channel>
</rss>
"""
        (self.output_dir / "feed.xml").write_text(rss.strip(), encoding="utf-8")

    def _write_sitemap(self, categories: List[Category], products: List[Product]) -> None:
        latest_site_update = self._latest_updated_datetime(products)
        if latest_site_update is None:
            latest_site_update = datetime.now(timezone.utc)
        product_lastmods: dict[str, datetime | None] = {}
        category_lastmods: dict[str, datetime | None] = {}
        for product in products:
            product_dt = self._parse_iso_datetime(product.updated_at)
            product_lastmods[product.slug] = product_dt
            if product_dt is None:
                continue
            existing = category_lastmods.get(product.category_slug)
            if existing is None or product_dt > existing:
                category_lastmods[product.category_slug] = product_dt
        entries: List[dict[str, str | None]] = [
            {
                "loc": self._absolute_url("index.html"),
                "lastmod": self._format_iso8601(latest_site_update),
                "changefreq": "daily",
                "priority": "1.0",
            },
            {
                "loc": self._absolute_url("latest.html"),
                "lastmod": self._format_iso8601(latest_site_update),
                "changefreq": "daily",
                "priority": "0.8",
            },
        ]
        if self._has_deals_page and self._deals_products:
            deals_update = self._latest_updated_datetime(self._deals_products) or latest_site_update
            entries.append(
                {
                    "loc": self._absolute_url("deals.html"),
                    "lastmod": self._format_iso8601(deals_update),
                    "changefreq": "daily",
                    "priority": "0.75",
                }
            )
        for category in categories:
            category_dt = category_lastmods.get(category.slug, latest_site_update)
            entries.append(
                {
                    "loc": self._absolute_url(self._category_path(category.slug)),
                    "lastmod": self._format_iso8601(category_dt),
                    "changefreq": "weekly",
                    "priority": "0.7",
                }
            )
        for product in products:
            entries.append(
                {
                    "loc": self._absolute_url(self._product_path(product)),
                    "lastmod": self._format_iso8601(product_lastmods.get(product.slug)),
                    "changefreq": "weekly",
                    "priority": "0.6",
                }
            )
        url_tags = "".join(
            "<url>"
            f"<loc>{html.escape(entry['loc'])}</loc>"
            + (
                f"<lastmod>{html.escape(entry['lastmod'])}</lastmod>"
                if entry.get("lastmod")
                else ""
            )
            + (
                f"<changefreq>{entry['changefreq']}</changefreq>"
                if entry.get("changefreq")
                else ""
            )
            + (
                f"<priority>{entry['priority']}</priority>"
                if entry.get("priority")
                else ""
            )
            + "</url>"
            for entry in entries
        )
        xml = f"""
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
{url_tags}
</urlset>
"""
        (self.output_dir / "sitemap.xml").write_text(xml.strip(), encoding="utf-8")

    def _select_deals_products(self, products: Iterable[Product], limit: int = 60) -> List[Product]:
        deals: List[tuple[Product, float, float, datetime]] = []
        for product in products:
            drop_amount = product.price_drop_amount()
            latest_point = product.latest_price_point
            previous_point = product.previous_price_point
            if drop_amount is None or not latest_point or not previous_point:
                continue
            percent_drop = product.price_drop_percent() or 0.0
            updated = self._parse_iso_datetime(getattr(product, "updated_at", None))
            if updated is None:
                updated = datetime(1970, 1, 1, tzinfo=timezone.utc)
            deals.append((product, percent_drop, drop_amount, updated))
        deals.sort(key=lambda item: (item[1], item[2], item[3]), reverse=True)
        return [item[0] for item in deals[:limit]]

    def _organization_structured_data(self) -> dict | None:
        same_as: List[str] = []
        if self.settings.twitter_handle:
            handle = self.settings.twitter_handle.lstrip("@")
            if handle:
                same_as.append(f"https://twitter.com/{handle}")
        if self.settings.facebook_page:
            same_as.append(self.settings.facebook_page)
        data: dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": self.settings.site_name,
            "url": self.settings.base_url,
        }
        if self.settings.logo_url:
            data["logo"] = {
                "@type": "ImageObject",
                "url": self.settings.logo_url,
            }
        if same_as:
            data["sameAs"] = same_as
        return data

    def _newsletter_banner(self) -> str:
        cta_copy = getattr(self.settings, "newsletter_cta_copy", None) or "Join the newsletter"
        form_action = getattr(self.settings, "newsletter_form_action", None)
        if form_action:
            action = html.escape(form_action)
            method = getattr(self.settings, "newsletter_form_method", "post") or "post"
            method = method.lower()
            if method not in {"get", "post"}:
                method = "post"
            method_attr = html.escape(method)
            email_field = (
                getattr(self.settings, "newsletter_form_email_field", "email") or "email"
            )
            email_field = html.escape(email_field)
            hidden_inputs = getattr(self.settings, "newsletter_form_hidden_inputs", ())
            hidden_inputs_html = "".join(
                f"\n    <input type=\"hidden\" name=\"{html.escape(name)}\" value=\"{html.escape(value)}\" />"
                for name, value in hidden_inputs
            )
            button_label = html.escape(cta_copy)
            return f"""
<section class=\"newsletter-banner\" id=\"newsletter\">
  <h3>Get the Grab Gifts insider drop</h3>
  <p>Subscribe for breakout performers, promo angles, and launch reminders straight from the gift commerce lab.</p>
  <form class=\"newsletter-form\" action=\"{action}\" method=\"{method_attr}\" target=\"_blank\">
    <label class=\"sr-only\" for=\"newsletter-email\">Email address</label>
    <div class=\"newsletter-fields\">
      <input id=\"newsletter-email\" type=\"email\" name=\"{email_field}\" placeholder=\"you@example.com\" autocomplete=\"email\" required />
      <button type=\"submit\">{button_label}</button>
    </div>{hidden_inputs_html}
  </form>
</section>
"""
        if getattr(self.settings, "newsletter_url", None):
            url = html.escape(self.settings.newsletter_url)
            button_label = html.escape(cta_copy)
            return f"""
<section class=\"newsletter-banner\" id=\"newsletter\">
  <h3>Get the Grab Gifts insider drop</h3>
  <p>Subscribe for breakout performers, promo angles, and launch reminders straight from the gift commerce lab.</p>
  <a class=\"button-link\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">{button_label}</a>
</section>
"""
        return ""

    def _item_list_structured_data(self, name: str, items: List[tuple[str, str]]) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": name,
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": title,
                    "url": url,
                }
                for index, (title, url) in enumerate(items)
            ],
        }

    def _latest_updated_datetime(self, products: Iterable[Product]) -> datetime | None:
        latest: datetime | None = None
        for product in products:
            dt = self._parse_iso_datetime(getattr(product, "updated_at", None))
            if dt and (latest is None or dt > latest):
                latest = dt
        return latest

    def _breadcrumb_structured_data(self, crumbs: List[tuple[str, str]]) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": name,
                    "item": url,
                }
                for index, (name, url) in enumerate(crumbs)
            ],
        }

    def _product_structured_data(self, product: Product, category: Category) -> dict:
        data: dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "sku": product.asin,
            "url": self._absolute_url(self._product_path(product)),
            "description": product.summary or self.settings.description,
            "category": category.name,
        }
        if product.image:
            image_url = product.image
        else:
            image_url = f"https://source.unsplash.com/1200x630/?{category.slug}"
        data["image"] = [image_url]
        price_value, currency = self._extract_price_components(product.price)
        if price_value:
            data["offers"] = {
                "@type": "Offer",
                "price": price_value,
                "priceCurrency": currency or "USD",
                "availability": "https://schema.org/InStock",
                "url": product.link,
            }
        if product.rating and product.total_reviews:
            data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": f"{product.rating:.1f}",
                "reviewCount": str(product.total_reviews),
            }
        return data

    @staticmethod
    def _extract_price_components(price: str | None) -> tuple[str | None, str | None]:
        parsed = parse_price_string(price)
        if not parsed:
            return None, None
        value, currency = parsed
        if currency is None and price:
            for symbol, code in PRICE_CURRENCY_SYMBOLS.items():
                if symbol in price:
                    currency = code
                    break
        numeric = f"{value:.2f}".rstrip("0").rstrip(".")
        return numeric, currency

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _format_iso8601(value: datetime | None) -> str | None:
        if value is None:
            return None
        return (
            value.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _format_currency(amount: float | None, currency: str | None) -> str:
        if amount is None:
            return ""
        symbol = CURRENCY_SYMBOL_BY_CODE.get(currency or "USD", "$")
        return f"{symbol}{abs(amount):,.2f}"

    def _format_price_point_label(self, point: PricePoint) -> str:
        dt = self._parse_iso_datetime(point.captured_at)
        if not dt:
            return point.captured_at.split("T")[0]
        return dt.strftime("%b %d, %Y")

    def _adsense_inline_enabled(self) -> bool:
        return bool(self.settings.adsense_client_id and self.settings.adsense_slot)

    def _adsense_unit(self, slot: str, *, extra_class: str = "") -> str:
        if not self.settings.adsense_client_id or not slot:
            return ""
        client = html.escape(self.settings.adsense_client_id, quote=True)
        slot_attr = html.escape(slot, quote=True)
        classes = "adsense-slot"
        if extra_class:
            classes = f"{classes} {extra_class}"
        return (
            f'<div class="{classes}">'
            f"\n  <ins class=\"adsbygoogle\" style=\"display:block\" data-ad-client=\"{client}\" "
            f"data-ad-slot=\"{slot_attr}\" data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>"
            "\n  <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"
            "\n</div>"
        )

    def _adsense_card(self) -> str:
        if not self._adsense_inline_enabled():
            return ""
        unit = self._adsense_unit(
            self.settings.adsense_slot or "",
            extra_class="adsense-slot--inline",
        )
        if not unit:
            return ""
        return (
            "<article class=\"card card--ad\" aria-label=\"Advertisement\">"
            "\n  <div class=\"card-content card-content--ad\">"
            "\n    <span class=\"card-ad-label\">Advertisement</span>"
            f"\n    {unit}"
            "\n  </div>"
            "\n</article>"
        )

    def _news_feed_metrics(self, product: Product, now: datetime) -> tuple[int, float, float]:
        updated_dt = self._parse_iso_datetime(getattr(product, "updated_at", None))
        updated_score = int(updated_dt.timestamp()) if updated_dt else 0
        rating_value = product.rating or 0.0
        review_count = float(product.total_reviews or 0)
        popularity_score = review_count + (rating_value * 100)
        trending_score = popularity_score
        if updated_dt:
            hours_old = (now - updated_dt).total_seconds() / 3600.0
            recency_window = max(0.0, 240 - hours_old)
            trending_score += recency_window * 10
        drop_percent = product.price_drop_percent()
        if drop_percent:
            trending_score += drop_percent * 25
        return updated_score, popularity_score, trending_score

    def _product_cards_with_ads(self, products: Iterable[Product]) -> str:
        cards: List[str] = []
        ads_enabled = self._adsense_inline_enabled()
        for index, product in enumerate(products, start=1):
            cards.append(self._product_card(product))
            if ads_enabled and index % 5 == 0:
                ad_card = self._adsense_card()
                if ad_card:
                    cards.append(ad_card)
        return "".join(cards)

    def _product_card(
        self,
        product: Product,
        *,
        extra_attrs: str = "",
        extra_classes: str = "",
    ) -> str:
        description = html.escape(product.summary or "Discover why we love this find.")
        image = html.escape(product.image or "")
        category_badge = ""
        category = self._category_lookup.get(product.category_slug)
        if category:
            category_badge = f'<span class="card-badge">{html.escape(category.name)}</span>'
        classes = "card"
        extra_class_value = extra_classes.strip()
        if extra_class_value:
            classes = f"{classes} {extra_class_value}"
        attr_fragment = ""
        extra_attr_value = extra_attrs.strip()
        if extra_attr_value:
            attr_fragment = f" {extra_attr_value}"
        price_html = (
            f'<span class="card-price">{html.escape(product.price)}</span>'
            if product.price
            else ""
        )
        rating_html = ""
        if product.rating and product.total_reviews:
            rating_html = (
                f'<span class="card-rating" aria-label="{product.rating:.1f} out of 5 stars based on {product.total_reviews:,} reviews">'
                '<svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>'
                f'{product.rating:.1f}<span class="card-rating-count">({product.total_reviews:,})</span></span>'
            )
        retailer_html = ""
        if product.retailer_name:
            retailer_html = f'<span class="card-retailer">{html.escape(product.retailer_name)}</span>'
        highlight_badge = ""
        latest_point = product.latest_price_point
        drop_amount = product.price_drop_amount()
        percent_drop = product.price_drop_percent()
        price_change = product.price_change_amount()
        if latest_point:
            currency_symbol = CURRENCY_SYMBOL_BY_CODE.get((latest_point.currency or "USD"), "$")
            if drop_amount is not None:
                drop_text = f"{currency_symbol}{drop_amount:,.2f}"
                if percent_drop is not None:
                    drop_text = f"{drop_text} ({percent_drop:.0f}% off)"
                highlight_badge = f'<span class="card-deal">↓ {html.escape(drop_text + " since last check")}</span>'
            elif price_change is not None and price_change > 0:
                increase_text = f"{currency_symbol}{abs(price_change):,.2f}"
                highlight_badge = f'<span class="card-deal card-deal--up">↑ {html.escape(increase_text + " since last check")}</span>'
        meta_parts = [part for part in (price_html, rating_html, retailer_html) if part]
        meta_html = (
            f'<div class="card-meta">{"".join(meta_parts)}</div>'
            if meta_parts
            else ""
        )
        highlight_html = (
            f'<div class="card-highlight">{highlight_badge}</div>'
            if highlight_badge
            else ""
        )
        outbound_cta = ""
        if product.link:
            cta_copy = product.call_to_action or f"Shop on {product.retailer_name}"
            outbound_cta = (
                f' <a class="cta-secondary" href="{html.escape(product.link)}" target="_blank" rel="noopener sponsored">{html.escape(cta_copy)}</a>'
            )
        return f"""
<article class="{classes}"{attr_fragment}>
  <a class="card-media" href="/{self._product_path(product)}">
    <img src="{image}" alt="{html.escape(product.title)}" loading="lazy" decoding="async" />
    {category_badge}
  </a>
  <div class="card-content">
    <h3><a href="/{self._product_path(product)}">{html.escape(product.title)}</a></h3>
    <p>{description}</p>
    {meta_html}
    {highlight_html}
    <div class="card-actions"><a class="button-link" href="/{self._product_path(product)}">Read the hype</a>{outbound_cta}</div>
  </div>
</article>
"""
    def _category_card(self, category: Category) -> str:
        return f"""
<article class=\"card\">
  <a class=\"card-media\" href=\"/{self._category_path(category.slug)}\">
    <img src=\"https://source.unsplash.com/600x400/?{html.escape(category.slug)}\" alt=\"{html.escape(category.name)}\" loading=\"lazy\" decoding=\"async\" />
  </a>
  <div class=\"card-content\">
    <h3><a href=\"/{self._category_path(category.slug)}\">{html.escape(category.name)}</a></h3>
    <p>{html.escape(category.blurb)}</p>
  </div>
</article>
"""

    def _write_page(self, path: Path, context: PageContext) -> None:
        logger.debug("Writing page %s", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        html_content = self._layout(context)
        path.write_text(html_content, encoding="utf-8")

    def _category_path(self, slug: str) -> str:
        return f"categories/{slug}/index.html"

    def _product_path(self, product: Product) -> str:
        return f"products/{product.slug}/index.html"

    def _absolute_url(self, relative: str) -> str:
        base = self.settings.base_url.rstrip("/")
        relative = relative.lstrip("/")
        return f"{base}/{relative}"

    def _navigation_links(self) -> Iterable[tuple[str, str]]:
        # keep navigation limited to six categories to avoid crowding
        return [
            (category.slug, category.name)
            for category in self._nav_categories[:6]
        ]

    @property
    def _nav_categories(self) -> List[Category]:
        # store categories on generator for navigation reuse
        if not hasattr(self, "_nav_cache"):
            self._nav_cache: List[Category] = []
        return self._nav_cache

    @_nav_categories.setter
    def _nav_categories(self, value: List[Category]) -> None:
        self._nav_cache = value

    def preload_navigation(self, categories: List[Category]) -> None:
        self._nav_categories = categories
        logger.debug("Navigation preload set for %s categories", len(self._nav_categories))
