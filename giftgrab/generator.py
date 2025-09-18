"""Static site generator responsible for producing the HTML pages."""
from __future__ import annotations

import html
import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence
from urllib.parse import quote_plus

from .config import DATA_DIR, OUTPUT_DIR, SiteSettings, ensure_directories
from .articles import Article, ArticleItem
from .models import Category, GeneratedProduct, PricePoint, Product, RoundupArticle
from .quality import SeoPayload, passes_seo
from .text import (
    MetaParams,
    TitleParams,
    desc_breakdown,
    intro_breakdown,
    make_meta,
    make_title,
    title_breakdown,
)
from .utils import PRICE_CURRENCY_SYMBOLS, parse_price_string, slugify

logger = logging.getLogger(__name__)

CURRENCY_SYMBOL_BY_CODE = {code: symbol for symbol, code in PRICE_CURRENCY_SYMBOLS.items()}

ASSETS_STYLES = """
:root {
  color-scheme: light dark;
  --brand: #7f56d9;
  --brand-dark: #53389e;
  --accent: #f97316;
  --highlight: #12b76a;
  --bg: #f5f3ff;
  --bg-muted: #ebe4ff;
  --text: #1f1147;
  --muted: #5b4d87;
  --muted-strong: #362a63;
  --card: #ffffff;
  --card-elevated: #f3ecff;
  --card-sheen: rgba(255, 255, 255, 0.94);
  --border: rgba(127, 86, 217, 0.14);
  --border-strong: rgba(127, 86, 217, 0.26);
  --overlay: rgba(127, 86, 217, 0.12);
  --pill-bg: rgba(127, 86, 217, 0.14);
  --pill-bg-hover: rgba(127, 86, 217, 0.24);
  --badge-bg: rgba(18, 183, 106, 0.16);
  --badge-color: #047857;
  --price-bg: rgba(249, 115, 22, 0.16);
  --rating-bg: rgba(18, 183, 106, 0.16);
  --newsletter-bg: rgba(127, 86, 217, 0.1);
  --newsletter-border: rgba(127, 86, 217, 0.28);
  --input-bg: #ffffff;
  --input-border: rgba(127, 86, 217, 0.24);
  --shadow-soft: 0 18px 38px rgba(82, 39, 177, 0.12);
  --shadow-card: 0 32px 70px rgba(82, 39, 177, 0.16);
  --shadow-card-hover: 0 40px 90px rgba(82, 39, 177, 0.2);
  --header-bg: rgba(255, 255, 255, 0.9);
  --hero-glow: radial-gradient(120% 120% at 50% 0%, rgba(127, 86, 217, 0.16) 0%, rgba(249, 115, 22, 0.12) 45%, transparent 100%);
  --theme-track: rgba(127, 86, 217, 0.28);
  --theme-thumb: #ffffff;
  font-family: 'Manrope', 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

:root[data-theme='dark'] {
  color-scheme: dark light;
  --bg: #0f0a1e;
  --bg-muted: #16112d;
  --text: #f6f4ff;
  --muted: #c5bff0;
  --muted-strong: #f0e9ff;
  --card: #17112d;
  --card-elevated: #211b3b;
  --card-sheen: rgba(47, 33, 93, 0.82);
  --border: rgba(127, 86, 217, 0.34);
  --border-strong: rgba(249, 115, 22, 0.36);
  --overlay: rgba(127, 86, 217, 0.26);
  --pill-bg: rgba(127, 86, 217, 0.38);
  --pill-bg-hover: rgba(127, 86, 217, 0.5);
  --badge-bg: rgba(18, 183, 106, 0.32);
  --badge-color: #a7f3d0;
  --price-bg: rgba(249, 115, 22, 0.34);
  --rating-bg: rgba(18, 183, 106, 0.32);
  --newsletter-bg: rgba(127, 86, 217, 0.32);
  --newsletter-border: rgba(249, 115, 22, 0.48);
  --input-bg: rgba(24, 18, 45, 0.78);
  --input-border: rgba(249, 115, 22, 0.38);
  --shadow-soft: 0 20px 44px rgba(5, 3, 12, 0.55);
  --shadow-card: 0 34px 80px rgba(5, 3, 12, 0.65);
  --shadow-card-hover: 0 44px 94px rgba(5, 3, 12, 0.72);
  --header-bg: rgba(15, 10, 30, 0.92);
  --hero-glow: radial-gradient(120% 120% at 50% 0%, rgba(127, 86, 217, 0.32) 0%, rgba(249, 115, 22, 0.24) 45%, rgba(8, 6, 15, 0.92) 100%);
  --theme-track: rgba(127, 86, 217, 0.42);
  --theme-thumb: #1f1440;
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
    radial-gradient(120% 120% at 0% 0%, rgba(127, 86, 217, 0.18) 0%, transparent 55%),
    radial-gradient(120% 120% at 100% 0%, rgba(249, 115, 22, 0.16) 0%, transparent 60%),
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
  backdrop-filter: blur(16px);
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid rgba(127, 86, 217, 0.18);
  box-shadow: 0 20px 44px rgba(82, 39, 177, 0.14);
  transition: background 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease;
}

:root[data-theme='dark'] header {
  box-shadow: 0 24px 54px rgba(5, 3, 12, 0.55);
  border-color: rgba(127, 86, 217, 0.32);
}

nav {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: center;
  gap: 1.5rem;
  padding: 1.25rem 2.4rem;
}

.nav-brand {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  min-width: 0;
}

.logo {
  font-weight: 800;
  font-size: 1.45rem;
  letter-spacing: -0.02em;
  color: var(--text);
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
}

.logo-mark {
  width: 44px;
  height: 44px;
  border-radius: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow: 0 14px 32px rgba(127, 86, 217, 0.32), 0 0 0 6px rgba(127, 86, 217, 0.16);
  position: relative;
  overflow: hidden;
}

.logo-mark::before {
  content: '';
  position: absolute;
  inset: 6px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0));
  mix-blend-mode: screen;
}

.logo-mark::after {
  content: '';
  position: absolute;
  inset: -8px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.32);
  opacity: 0.65;
}

.logo-spark {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(135deg, #fde68a 0%, #f97316 100%);
  box-shadow: 0 0 0 6px rgba(255, 255, 255, 0.2), 0 6px 14px rgba(249, 115, 22, 0.45);
  position: relative;
  transform: rotate(18deg);
}

.logo-text {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
}

.logo-word {
  color: var(--text);
}

.logo-highlight {
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.nav-tagline {
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
  opacity: 0.85;
}

.nav-toggle {
  display: none;
  align-items: center;
  justify-content: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  box-shadow: var(--shadow-soft);
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease, color 0.2s ease;
  justify-self: end;
}

.nav-toggle:hover,
.nav-toggle:focus {
  border-color: rgba(127, 86, 217, 0.38);
  box-shadow: 0 20px 38px rgba(82, 39, 177, 0.2);
}

.nav-toggle-icon,
.nav-toggle-icon::before,
.nav-toggle-icon::after {
  display: block;
  width: 18px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.nav-toggle-icon {
  position: relative;
}

.nav-toggle-icon::before,
.nav-toggle-icon::after {
  content: '';
  position: absolute;
  left: 0;
}

.nav-toggle-icon::before {
  top: -6px;
}

.nav-toggle-icon::after {
  top: 6px;
}

.nav-open .nav-toggle-icon {
  background: transparent;
}

.nav-open .nav-toggle-icon::before {
  transform: translateY(6px) rotate(45deg);
}

.nav-open .nav-toggle-icon::after {
  transform: translateY(-6px) rotate(-45deg);
}

.nav-groups {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
  padding: 1rem 1.4rem;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.72);
  box-shadow: var(--shadow-soft);
  justify-self: end;
}

.nav-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.96rem;
}

.nav-links a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  color: var(--muted);
  font-weight: 600;
  border: 1px solid transparent;
  transition: color 0.2s ease, border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
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

.nav-links a:hover,
.nav-links a:focus {
  color: var(--brand);
  border-color: rgba(127, 86, 217, 0.3);
  background: rgba(127, 86, 217, 0.14);
  transform: translateY(-1px);
}

:root[data-theme='dark'] .nav-groups {
  background: rgba(24, 18, 45, 0.82);
  border-color: rgba(127, 86, 217, 0.28);
}

.pill-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55rem 0.95rem;
  border-radius: 999px;
  border: 1px solid rgba(127, 86, 217, 0.28);
  font-weight: 600;
  color: var(--brand);
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.18), rgba(249, 115, 22, 0.12));
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.pill-link:hover,
.pill-link:focus {
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.3), rgba(249, 115, 22, 0.2));
  color: var(--brand);
  transform: translateY(-2px);
  border-color: rgba(127, 86, 217, 0.42);
  box-shadow: 0 16px 32px rgba(82, 39, 177, 0.2);
}

.search-form {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 999px;
  border: 1px solid rgba(127, 86, 217, 0.2);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(18px);
}

:root[data-theme='dark'] .search-form {
  background: rgba(24, 18, 45, 0.78);
  border-color: rgba(249, 115, 22, 0.35);
  box-shadow: 0 20px 42px rgba(5, 3, 12, 0.45);
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
  border: 1px solid rgba(127, 86, 217, 0.2);
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
  border-color: rgba(127, 86, 217, 0.32);
  box-shadow: 0 18px 40px rgba(5, 3, 12, 0.45);
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
  box-shadow: 0 4px 10px rgba(82, 39, 177, 0.25);
  transform: translateX(0);
  transition: transform 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
}

:root[data-theme='dark'] .theme-toggle-thumb {
  box-shadow: 0 4px 14px rgba(5, 3, 12, 0.5);
}

.theme-toggle-input:checked + .theme-toggle-label {
  border-color: rgba(127, 86, 217, 0.36);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-text {
  color: var(--brand);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-track {
  background: linear-gradient(135deg, var(--brand), var(--accent));
  box-shadow: 0 14px 28px rgba(82, 39, 177, 0.28);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-thumb {
  transform: translateX(26px);
  box-shadow: 0 10px 20px rgba(82, 39, 177, 0.32);
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
  border: 1px solid rgba(127, 86, 217, 0.16);
  border-radius: 24px;
  box-shadow: var(--shadow-card);
  padding: 1.5rem;
  width: 100%;
}

:root[data-theme='dark'] .ad-rail {
  border-color: rgba(249, 115, 22, 0.25);
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
  border: 1px solid rgba(127, 86, 217, 0.18);
  border-radius: 999px;
  padding: 0.3rem 0.75rem;
}

.hero {
  position: relative;
  text-align: center;
  padding: 4rem 2rem;
  margin: 0 auto 3.75rem;
  max-width: 1020px;
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.2), rgba(249, 115, 22, 0.12)), var(--card);
  border-radius: 36px;
  border: 1px solid rgba(127, 86, 217, 0.2);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  backdrop-filter: blur(8px);
}

.hero::before {
  content: '';
  position: absolute;
  inset: -25%;
  background:
    radial-gradient(circle at 18% 20%, rgba(127, 86, 217, 0.32), transparent 55%),
    radial-gradient(circle at 82% 18%, rgba(249, 115, 22, 0.24), transparent 55%),
    conic-gradient(from 150deg at 50% 50%, rgba(18, 183, 106, 0.2), transparent 65%);
  opacity: 0.9;
  filter: blur(0.5px);
  pointer-events: none;
}

.hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.36), transparent 65%);
  opacity: 0.55;
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
  background: rgba(127, 86, 217, 0.2);
  color: var(--brand);
  border: 1px solid rgba(127, 86, 217, 0.28);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 1.15rem;
  box-shadow: 0 18px 32px rgba(127, 86, 217, 0.22);
  backdrop-filter: blur(8px);
}

.hero h1 {
  font-size: clamp(2.6rem, 4.6vw, 3.55rem);
  margin-bottom: 0.85rem;
  font-weight: 800;
  letter-spacing: -0.015em;
}

.hero p {
  color: var(--muted-strong);
  opacity: 0.92;
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
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 60%, rgba(18, 183, 106, 0.9) 100%);
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.04em;
  box-shadow: 0 28px 60px rgba(127, 86, 217, 0.32);
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
  white-space: nowrap;
}

.button-link:hover,
.button-link:focus,
.cta-button:hover,
.cta-button:focus {
  transform: translateY(-2px);
  box-shadow: 0 34px 72px rgba(82, 39, 177, 0.38);
  filter: brightness(1.05);
}

.guide {
  max-width: 940px;
  margin: 0 auto 5rem;
  background: var(--card);
  border-radius: 32px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
  border: 1px solid var(--border);
}

.guide-hero {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 2rem;
  padding: 3rem;
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.18), rgba(249, 115, 22, 0.12));
}

.guide-hero-media img {
  width: 100%;
  height: auto;
  border-radius: 24px;
  box-shadow: var(--shadow-card);
}

.guide-hero-copy {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  justify-content: center;
}

.guide-kind {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.8rem;
  border-radius: 999px;
  background: var(--pill-bg);
  color: var(--brand);
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.guide-toc {
  margin: 2.5rem auto 0;
  max-width: 760px;
  background: var(--card-elevated);
  border-radius: 20px;
  border: 1px solid var(--border);
  padding: 1.5rem 2rem;
  box-shadow: var(--shadow-soft);
}

.guide-toc strong {
  display: block;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.75rem;
  color: var(--muted);
  margin-bottom: 0.5rem;
}

.guide-toc ol {
  margin: 0;
  padding-left: 1.2rem;
  display: grid;
  gap: 0.35rem;
}

.guide-intro,
.guide-items,
.guide-section,
.guide-related {
  padding: 2.5rem 3rem;
}

.guide-intro p {
  font-size: 1.05rem;
}

.guide-hubs {
  margin-top: 1.5rem;
  background: var(--card-elevated);
  border-radius: 18px;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--border);
}

.guide-hubs h2 {
  margin-top: 0;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--muted);
}

.guide-hubs ul {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  padding: 0;
  margin: 0;
  list-style: none;
}

.guide-hubs a {
  display: inline-flex;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card);
  font-weight: 600;
}

.guide-item {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem;
  margin-bottom: 2.5rem;
  background: var(--card);
  border-radius: 24px;
  border: 1px solid var(--border);
  padding: 2rem;
  box-shadow: var(--shadow-soft);
}

.guide-item-media img {
  width: 100%;
  border-radius: 18px;
}

.guide-item-body h2 {
  margin-top: 0;
  margin-bottom: 0.85rem;
  font-size: 1.6rem;
}

.guide-item-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.2rem;
  height: 2.2rem;
  margin-right: 0.6rem;
  background: var(--pill-bg);
  border-radius: 50%;
  font-weight: 700;
  color: var(--brand);
}

.guide-item-specs {
  margin: 1.2rem 0;
  padding-left: 1.2rem;
}

.guide-item-links {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 1.2rem;
}

.guide-item-tags {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.guide-item-tags span {
  background: var(--pill-bg);
  border-radius: 999px;
  padding: 0.2rem 0.65rem;
  font-size: 0.8rem;
  letter-spacing: 0.08em;
}

.guide-section h2,
.guide-related h2 {
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.9rem;
  color: var(--muted);
  margin-top: 0;
}

.guide-related ul {
  list-style: none;
  margin: 1.2rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.75rem;
}

.guide-ad {
  margin: 1.5rem 0;
}

@media (max-width: 720px) {
  .guide,
  .guide-intro,
  .guide-items,
  .guide-section,
  .guide-related {
    padding: 1.75rem;
  }
  .guide-hero {
    padding: 2rem;
  }
}

.cta-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.8rem 1.15rem;
  border-radius: 999px;
  border: 1px solid rgba(249, 115, 22, 0.32);
  font-weight: 600;
  color: var(--accent);
  background: rgba(249, 115, 22, 0.14);
  box-shadow: 0 18px 34px rgba(249, 115, 22, 0.18);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  cursor: pointer;
}

.cta-secondary:hover,
.cta-secondary:focus {
  color: var(--accent);
  transform: translateY(-2px);
  border-color: rgba(249, 115, 22, 0.42);
  box-shadow: 0 22px 48px rgba(249, 115, 22, 0.24);
}

.hero-dashboard {
  margin-top: 2.75rem;
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  text-align: left;
}

.dashboard-card {
  position: relative;
  display: grid;
  gap: 0.4rem;
  padding: 1.15rem 1.25rem;
  border-radius: 20px;
  border: 1px solid rgba(127, 86, 217, 0.18);
  background: var(--card-sheen);
  box-shadow: var(--shadow-soft);
}

.dashboard-card strong {
  font-size: 1.6rem;
  letter-spacing: -0.02em;
  color: var(--brand);
}

.dashboard-card span {
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.45;
}

.dashboard-label {
  font-size: 0.72rem;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}

:root[data-theme='dark'] .dashboard-card {
  background: rgba(24, 18, 45, 0.82);
  border-color: rgba(127, 86, 217, 0.28);
  box-shadow: 0 24px 52px rgba(5, 3, 12, 0.58);
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
  border-color: rgba(249, 115, 22, 0.38);
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
  background: rgba(127, 86, 217, 0.14);
}

.feed-sort.is-active {
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.22), rgba(249, 115, 22, 0.2));
  color: var(--brand);
  box-shadow: 0 18px 32px rgba(127, 86, 217, 0.24);
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
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.14), rgba(249, 115, 22, 0.18));
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
  border: 1px solid rgba(127, 86, 217, 0.14);
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-card-hover);
  border-color: rgba(127, 86, 217, 0.28);
}

.card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 15%, rgba(127, 86, 217, 0.18), transparent 55%), radial-gradient(circle at 80% 20%, rgba(249, 115, 22, 0.18), transparent 60%);
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
  border-bottom: 1px solid rgba(127, 86, 217, 0.12);
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
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.85), rgba(249, 115, 22, 0.75));
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
  border: 1px solid rgba(127, 86, 217, 0.18);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
}

:root[data-theme='dark'] .card-ad-label {
  border-color: rgba(249, 115, 22, 0.28);
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
  background: rgba(249, 115, 22, 0.18);
  color: var(--accent);
  font-weight: 600;
  padding: 0.35rem 0.7rem;
  border-radius: 12px;
  border: 1px solid rgba(249, 115, 22, 0.35);
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
  border: 1px solid rgba(127, 86, 217, 0.24);
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
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.12), rgba(249, 115, 22, 0.1)), var(--card);
  border-radius: 30px;
  border: 1px solid rgba(127, 86, 217, 0.16);
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
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.12), rgba(249, 115, 22, 0.1)), var(--card);
  border: 1px solid rgba(127, 86, 217, 0.2);
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
  background: radial-gradient(circle, rgba(127, 86, 217, 0.28), transparent 65%);
}

.newsletter-banner::after {
  bottom: -40%;
  right: -10%;
  width: 70%;
  height: 130%;
  background: radial-gradient(circle, rgba(249, 115, 22, 0.2), transparent 60%);
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
  border: 1px solid rgba(127, 86, 217, 0.22);
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
  box-shadow: 0 24px 48px rgba(127, 86, 217, 0.32);
  transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.newsletter-fields button:hover,
.newsletter-fields button:focus {
  transform: translateY(-2px);
  box-shadow: 0 30px 60px rgba(127, 86, 217, 0.38);
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
  border: 1px solid rgba(127, 86, 217, 0.16);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.value-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top right, rgba(127, 86, 217, 0.22), transparent 60%), radial-gradient(circle at bottom left, rgba(249, 115, 22, 0.18), transparent 60%);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.value-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-card-hover);
  border-color: rgba(127, 86, 217, 0.28);
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
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.16), rgba(249, 115, 22, 0.16));
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
  border: 1px solid rgba(127, 86, 217, 0.24);
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
  background: rgba(127, 86, 217, 0.08);
  border: 1px solid rgba(127, 86, 217, 0.24);
  border-radius: 999px;
  padding: 0.45rem 1.2rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--brand);
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.wishlist-toggle:hover,
.wishlist-toggle:focus {
  background: rgba(127, 86, 217, 0.16);
  border-color: rgba(127, 86, 217, 0.32);
  box-shadow: 0 12px 26px rgba(127, 86, 217, 0.24);
}

.wishlist-toggle.is-active {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
  box-shadow: 0 14px 32px rgba(127, 86, 217, 0.3);
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
  box-shadow: 0 16px 34px rgba(127, 86, 217, 0.28);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.share-primary:hover,
.share-primary:focus {
  transform: translateY(-2px);
  box-shadow: 0 20px 42px rgba(127, 86, 217, 0.32);
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
  border: 1px solid rgba(127, 86, 217, 0.18);
  color: var(--accent);
  font-weight: 500;
  cursor: pointer;
}

.share-copy {
  background: rgba(127, 86, 217, 0.08);
}

:root[data-theme='dark'] .share-links a,
:root[data-theme='dark'] .share-copy {
  background: rgba(42, 12, 50, 0.72);
  border-color: rgba(249, 115, 22, 0.32);
}

:root[data-theme='dark'] .share-copy {
  background: rgba(127, 86, 217, 0.25);
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
  background: linear-gradient(135deg, rgba(127, 86, 217, 0.12), rgba(249, 115, 22, 0.12)), var(--card);
  padding: 1.8rem 2rem;
  border-radius: 24px;
  box-shadow: var(--shadow-card);
  border: 1px solid rgba(127, 86, 217, 0.16);
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
  border: 1px solid rgba(127, 86, 217, 0.14);
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
  border: 1px solid rgba(127, 86, 217, 0.14);
  border-radius: 24px;
  padding: 1.5rem 1.75rem;
  box-shadow: var(--shadow-card);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.search-result:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-card-hover);
  border-color: rgba(127, 86, 217, 0.28);
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
  border-top: 1px solid rgba(127, 86, 217, 0.16);
  margin-top: 3.5rem;
  padding: 2.75rem 1.5rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.92rem;
  background: linear-gradient(180deg, rgba(127, 86, 217, 0.08), transparent 45%, rgba(249, 115, 22, 0.08));
  transition: background 0.35s ease, color 0.35s ease, border-color 0.35s ease;
}

:root[data-theme='dark'] footer {
  background: linear-gradient(180deg, rgba(12, 15, 34, 0.65), rgba(127, 86, 217, 0.22));
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
    padding: 1.1rem 1.8rem;
  }

  .nav-groups {
    gap: 1.25rem;
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
    grid-template-columns: 1fr auto;
    align-items: start;
    padding: 1rem 1.4rem;
  }

  .nav-brand {
    gap: 0.25rem;
  }

  .nav-tagline {
    font-size: 0.65rem;
    letter-spacing: 0.22em;
  }

  .nav-toggle {
    display: inline-flex;
  }

  .nav-groups {
    display: none;
    grid-column: 1 / -1;
    width: 100%;
    flex-direction: column;
    align-items: stretch;
    gap: 1.25rem;
    margin-top: 0.4rem;
    padding: 1.35rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--card);
  }

  nav.nav-open .nav-groups {
    display: flex;
  }

  .nav-links {
    flex-direction: column;
    align-items: stretch;
    gap: 0.75rem;
  }

  .nav-links a {
    justify-content: flex-start;
  }

  .nav-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 0.9rem;
  }

  .search-form {
    width: 100%;
    margin: 0;
  }
}

@media (max-width: 720px) {
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
    padding: 0.85rem 1.05rem;
    grid-template-columns: 1fr auto;
  }

  .logo {
    font-size: 1.2rem;
  }

  .logo-mark {
    width: 38px;
    height: 38px;
  }

  .nav-tagline {
    display: none;
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
        self.guides_dir = self.output_dir / "guides"
        self.weekly_dir = self.output_dir / "weekly"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.categories_dir.mkdir(parents=True, exist_ok=True)
        self.products_dir.mkdir(parents=True, exist_ok=True)
        self.guides_dir.mkdir(parents=True, exist_ok=True)
        self.weekly_dir.mkdir(parents=True, exist_ok=True)
        self._nav_cache: List[Category] = []
        self._category_lookup: dict[str, Category] = {}
        self._product_lookup: dict[str, Product] = {}
        self._generated_lookup: dict[str, GeneratedProduct] = {}
        self._roundups: List[RoundupArticle] = []
        self._best_generated: GeneratedProduct | None = None
        self._has_deals_page = False
        self._deals_products: List[Product] = []
        self._seo_failures: set[str] = set()

    def build(
        self,
        categories: List[Category],
        products: List[Product],
        *,
        articles: Sequence[Article] | None = None,
        generated_products: Sequence[GeneratedProduct] | None = None,
        roundups: Sequence[RoundupArticle] | None = None,
        best_generated: GeneratedProduct | None = None,
    ) -> None:
        logger.info("Generating site with %s products", len(products))
        self._write_assets()
        self.preload_navigation(categories)
        self._category_lookup = {category.slug: category for category in categories}
        self._has_deals_page = False
        self._deals_products = []
        self._seo_failures.clear()
        products_sorted = sorted(products, key=lambda p: p.updated_at, reverse=True)
        self._product_lookup = {product.slug: product for product in products_sorted}
        generated_list = [
            product
            for product in (generated_products or [])
            if getattr(product, "status", "published") == "published"
        ]
        self._generated_lookup = {product.slug: product for product in generated_list}
        self._roundups = [
            roundup
            for roundup in (roundups or [])
            if getattr(roundup, "status", "published") == "published"
        ]
        if best_generated is None and generated_list:
            sorted_candidates = sorted(
                generated_list,
                key=lambda item: (
                    item.score,
                    item.published_at or item.updated_at,
                ),
                reverse=True,
            )
            self._best_generated = sorted_candidates[0]
        else:
            self._best_generated = best_generated
        self._deals_products = self._select_deals_products(products_sorted)
        self._has_deals_page = bool(self._deals_products)
        if self._has_deals_page:
            self._write_deals_page(self._deals_products)
        self._write_index(
            categories,
            products_sorted[:12],
            products_sorted,
            best_generated=self._best_generated,
            roundups=self._roundups,
        )
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
        for generated in generated_list:
            self._write_generated_product_page(generated)
        for roundup in self._roundups:
            self._write_roundup_page(roundup)
        articles_list = [article for article in (articles or []) if article.status == "published"]
        if articles_list:
            self._write_articles(articles_list, categories, products_sorted)
        self._write_feed(products_sorted, generated_list, self._roundups)
        self._write_sitemap(
            categories,
            products_sorted,
            articles_list,
            generated_list,
            self._roundups,
        )
        self._write_robots()

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
        raw_site_name = (self.settings.site_name or "Grab Gifts").strip() or "Grab Gifts"
        site_words = [word for word in raw_site_name.split() if word]
        highlight_word = site_words[-1] if site_words else raw_site_name
        primary_words = site_words[:-1]
        primary_text = " ".join(primary_words)
        logo_segments: list[str] = []
        if primary_text:
            logo_segments.append(
                f'<span class="logo-word">{html.escape(primary_text)}</span>'
            )
        logo_segments.append(
            f'<span class="logo-highlight">{html.escape(highlight_word)}</span>'
        )
        logo_text_markup = " ".join(logo_segments)
        logo_aria = html.escape(f"{raw_site_name} home")
        tagline_value = getattr(self.settings, "tagline", None)
        tagline_default = "Gift commerce intelligence that sells itself"
        tagline_text = str(tagline_value).strip() if tagline_value else tagline_default
        nav_tagline = html.escape(tagline_text)
        nav_brand = (
            "<div class=\"nav-brand\">"
            f"<a href=\"/index.html\" class=\"logo\" aria-label=\"{logo_aria}\">"
            "<span class=\"logo-mark\" aria-hidden=\"true\"><span class=\"logo-spark\"></span></span>"
            f"<span class=\"logo-text\">{logo_text_markup}</span>"
            "</a>"
            f"<p class=\"nav-tagline\">{nav_tagline}</p>"
            "</div>"
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
      <nav aria-label=\"Primary\" data-nav>
        {nav_brand}
        <button type=\"button\" class=\"nav-toggle\" aria-expanded=\"false\" aria-controls=\"nav-menu\" data-nav-toggle>
          <span class=\"nav-toggle-icon\" aria-hidden=\"true\"></span>
          <span class=\"sr-only\">Toggle navigation</span>
        </button>
        <div class=\"nav-groups\" id=\"nav-menu\">
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

        var nav = document.querySelector('[data-nav]');
        var navToggle = document.querySelector('[data-nav-toggle]');
        var navMenu = document.getElementById('nav-menu');

        if (nav && navToggle && navMenu) {{
          function setNavState(open) {{
            nav.classList.toggle('nav-open', open);
            navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
          }}

          navToggle.addEventListener('click', function () {{
            var next = !nav.classList.contains('nav-open');
            setNavState(next);
          }});

          window.addEventListener('resize', function () {{
            if (window.innerWidth > 900) {{
              setNavState(false);
            }}
          }});

          document.addEventListener('keydown', function (event) {{
            if (event.key === 'Escape') {{
              setNavState(false);
            }}
          }});

          navMenu.addEventListener('click', function (event) {{
            var target = event.target;
            if (target instanceof Element) {{
              var link = target.closest('a');
              if (link) {{
                setNavState(false);
              }}
            }}
          }});
        }}
      }})();
    </script>
    <script>
      (function () {{
        function findTrackable(start) {{
          if (!(start instanceof Element)) {{
            return null;
          }}
          return start.closest('[data-analytics]');
        }}

        function buildDetail(element) {{
          if (!(element instanceof Element)) {{
            return null;
          }}
          var eventName = element.getAttribute('data-event') || 'interaction';
          var category = element.getAttribute('data-category') || element.getAttribute('data-placement') || 'engagement';
          var rawLabel = element.getAttribute('data-label');
          var label = rawLabel;
          if (!label) {{
            var aria = element.getAttribute('aria-label');
            if (aria) {{
              label = aria;
            }} else {{
              var text = element.textContent || '';
              text = text.replace(/\\s+/g, ' ').trim();
              label = text || undefined;
            }}
          }}
          var params = {{ event_category: category }};
          if (label) {{
            params.event_label = label;
          }}
          var placement = element.getAttribute('data-placement');
          if (placement) {{
            params.engagement_location = placement;
          }}
          var productSlug = element.getAttribute('data-product');
          var productName = element.getAttribute('data-product-name');
          var categoryName = element.getAttribute('data-category-name');
          var categorySlug = element.getAttribute('data-category');
          var retailerName = element.getAttribute('data-retailer-name');
          var retailerSlug = element.getAttribute('data-retailer');
          var items = null;
          if (productSlug || productName || categoryName || categorySlug || retailerName || retailerSlug) {{
            items = [{{
              item_id: productSlug || undefined,
              item_name: productName || label || undefined,
              item_category: categoryName || categorySlug || undefined,
              item_brand: retailerName || retailerSlug || undefined,
            }}];
            if (productSlug) {{
              params.product_slug = productSlug;
            }}
            if (categoryName) {{
              params.product_category = categoryName;
            }}
            if (categorySlug) {{
              params.product_category_slug = categorySlug;
            }}
            if (retailerName) {{
              params.product_retailer = retailerName;
            }}
            if (retailerSlug) {{
              params.product_retailer_slug = retailerSlug;
            }}
          }}
          var rawValue = element.getAttribute('data-value');
          if (rawValue) {{
            var numericValue = Number(rawValue);
            if (Number.isFinite(numericValue)) {{
              params.value = numericValue;
            }}
          }}
          if (items) {{
            params.items = items;
          }}
          return {{ name: eventName, params: params }};
        }}

        function sendEvent(element) {{
          if (typeof window === 'undefined' || typeof window.gtag !== 'function') {{
            return;
          }}
          var detail = buildDetail(element);
          if (!detail) {{
            return;
          }}
          try {{
            window.gtag('event', detail.name, detail.params);
          }} catch (error) {{
            console.warn('Analytics dispatch failed', error);
          }}
        }}

        document.addEventListener('click', function (event) {{
          var target = event.target;
          if (!(target instanceof Element)) {{
            return;
          }}
          var trackable = findTrackable(target);
          if (!trackable) {{
            return;
          }}
          if (trackable instanceof HTMLButtonElement && trackable.type === 'submit') {{
            return;
          }}
          sendEvent(trackable);
        }});

        document.addEventListener('submit', function (event) {{
          var form = event.target;
          if (!(form instanceof HTMLFormElement)) {{
            return;
          }}
          var candidate = null;
          var submitter = event.submitter;
          if (submitter instanceof Element) {{
            candidate = findTrackable(submitter);
          }}
          if (!candidate) {{
            candidate = findTrackable(form);
          }}
          if (!candidate) {{
            candidate = form.querySelector('[data-analytics]');
          }}
          if (candidate instanceof Element) {{
            sendEvent(candidate);
          }}
        }}, true);
      }})();
    </script>
  </body>
</html>
"""

    def _write_assets(self) -> None:
        stylesheet_path = self.assets_dir / "styles.css"
        stylesheet_path.write_text(ASSETS_STYLES, encoding="utf-8")
        self._copy_retailer_assets()

    def _copy_retailer_assets(self) -> None:
        retailers_dir = DATA_DIR / "retailers"
        if not retailers_dir.exists():
            return

        for retailer_dir in sorted(retailers_dir.iterdir()):
            if not retailer_dir.is_dir():
                continue
            source = retailer_dir / "images"
            if not source.exists() or not source.is_dir():
                continue

            destination = self.assets_dir / retailer_dir.name
            destination.mkdir(parents=True, exist_ok=True)

            copied: set[str] = set()
            for path in sorted(source.glob("**/*")):
                if path.is_dir():
                    continue
                relative_parent = path.parent.relative_to(source)
                target_dir = destination / relative_parent
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / path.name
                shutil.copy2(path, target_path)
                copied.add(str(target_path.relative_to(destination)))

            for path in destination.glob("**/*"):
                if path.is_dir():
                    continue
                relative = str(path.relative_to(destination))
                if relative not in copied:
                    path.unlink()

    def _write_index(
        self,
        categories: List[Category],
        featured_products: List[Product],
        all_products: List[Product],
        *,
        best_generated: GeneratedProduct | None = None,
        roundups: Sequence[RoundupArticle] | None = None,
    ) -> None:
        cta_href = f"/{self._category_path(categories[0].slug)}" if categories else "#"
        total_products = len(all_products)
        category_count = len(categories)
        retailer_keys = {
            (product.retailer_slug or product.retailer_name or "amazon").strip().lower()
            for product in all_products
            if (product.retailer_slug or product.retailer_name)
        }
        if not retailer_keys and all_products:
            retailer_keys = {"amazon"}
        retailer_count = len(retailer_keys)
        deals_count = len(self._deals_products)
        latest_site_update = self._latest_updated_datetime(all_products)
        last_sync_display = self._format_display_date(latest_site_update)
        hero_cards: List[tuple[str, str, str]] = [
            ("Fresh drops", f"{total_products:,}", "live gift ideas ready to convert."),
            ("Active vibes", str(category_count), "curated shopping storylines."),
            ("Partner sources", str(retailer_count), "retail feeds fueling affiliates."),
        ]
        if deals_count:
            hero_cards.append(("Live deals", str(deals_count), "price drops flagged for urgency plays."))
        hero_cards.append(("Last sync", last_sync_display, "latest catalogue refresh."))
        dashboard_items = [
            (
                f'<article class="dashboard-card" role="listitem">'
                f'<span class="dashboard-label">{html.escape(label)}</span>'
                f'<strong>{html.escape(value)}</strong>'
                f'<span>{html.escape(caption)}</span>'
                "</article>"
            )
            for label, value, caption in hero_cards
        ]
        dashboard_inner = "\n    ".join(dashboard_items)
        hero_dashboard = (
            "  <div class=\"hero-dashboard\" role=\"list\" aria-label=\"Gift commerce insights\">\n"
            f"    {dashboard_inner}\n"
            "  </div>"
        )
        hero_description = (
            f"{self.settings.description.strip()} "
            "Launch scroll-stopping gift funnels complete with affiliate wiring, ad inventory, and conversion copy."
        )
        hero = f"""
<section class=\"hero\">
  <span class=\"eyebrow\">Gift commerce dashboard</span>
  <h1>{html.escape(self.settings.site_name)}</h1>
  <p>{html.escape(hero_description)}</p>
  <div class=\"hero-actions\">
    <a class=\"button-link\" href=\"{cta_href}\">Explore today's drops</a>
    <button type=\"button\" class=\"cta-secondary surprise-button\" data-surprise>Spin up a surprise</button>
    <a class=\"cta-secondary\" href=\"/latest.html\">See the live changelog</a>
  </div>
{hero_dashboard}
</section>
"""
        category_cards = "".join(
            self._category_card(category) for category in categories
        )
        feed_section = self._news_feed_section(all_products)
        best_gift_section = self._best_gift_section(best_generated)
        roundup_section = self._roundup_listing(roundups or [])
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
        body = (
            f"{hero}{best_gift_section}{feed_section}{roundup_section}{category_section}{newsletter_banner}{value_props}"
        )
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

    def _best_gift_section(self, product: GeneratedProduct | None) -> str:
        if product is None:
            return ""
        image_seed = slugify(product.category or product.name or "gift")
        fallback_image = f"https://source.unsplash.com/600x400/?{html.escape(image_seed)}"
        image_url = html.escape(product.image or fallback_image)
        detail_url = f"/{self._generated_product_path(product)}"
        intro_text = product.intro or intro_breakdown(product.name, product.price_cap)
        intro = html.escape(intro_text)
        affiliate = html.escape(product.affiliate_url)
        bullet_items = "".join(
            f"<li>{html.escape(line)}</li>" for line in product.bullets
        )
        bullets_html = (
            f"<ul class=\"best-gift-highlights\">{bullet_items}</ul>"
            if bullet_items
            else ""
        )
        caveat_items = "".join(
            f"<li>{html.escape(line)}</li>" for line in product.caveats
        )
        caveats_html = (
            f"<div class=\"best-gift-consider\"><h4>Consider</h4><ul>{caveat_items}</ul></div>"
            if caveat_items
            else ""
        )
        return f"""
<section class=\"best-gift\">
  <div class=\"section-heading\">
    <span class=\"badge\">Weekly spotlight</span>
    <h2>Best Gift This Week</h2>
    <p>Highest scoring roundup pick from the past seven days.</p>
  </div>
  <article class=\"card best-gift-card\">
    <a class=\"card-media\" href=\"{detail_url}\">
      <img src=\"{image_url}\" alt=\"{html.escape(product.name)}\" loading=\"lazy\" decoding=\"async\" />
    </a>
    <div class=\"card-content\">
      <h3><a href=\"{detail_url}\">{html.escape(product.name)}</a></h3>
      <p>{intro}</p>
      {bullets_html}
      {caveats_html}
      <div class=\"card-actions\">
        <a class=\"button-link\" href=\"{detail_url}\">See details</a>
        <a class=\"cta-secondary\" href=\"{affiliate}\" target=\"_blank\" rel=\"nofollow sponsored noopener\">Check current price on Amazon</a>
      </div>
    </div>
  </article>
</section>
"""

    def _roundup_listing(self, roundups: Sequence[RoundupArticle]) -> str:
        if not roundups:
            return ""
        cards: List[str] = []
        for roundup in list(roundups)[:6]:
            image_seed = slugify(roundup.topic or "gifts")
            fallback_image = f"https://source.unsplash.com/600x400/?{html.escape(image_seed)}"
            image_url = html.escape(getattr(roundup, "hero_image", None) or fallback_image)
            url = f"/{self._roundup_path(roundup)}"
            intro = html.escape(roundup.intro)
            preview_items = "".join(
                f"<li>{html.escape(item.title)}</li>" for item in roundup.items[:3]
            )
            preview_html = (
                f"<ul class=\"roundup-preview\">{preview_items}</ul>"
                if preview_items
                else ""
            )
            cards.append(
                f"""
<article class=\"card roundup-card\">
  <a class=\"card-media\" href=\"{url}\">
    <img src=\"{image_url}\" alt=\"{html.escape(roundup.title)}\" loading=\"lazy\" decoding=\"async\" />
  </a>
  <div class=\"card-content\">
    <h3><a href=\"{url}\">{html.escape(roundup.title)}</a></h3>
    <p>{intro}</p>
    {preview_html}
    <div class=\"card-actions\"><a class=\"button-link\" href=\"{url}\">See the picks</a></div>
  </div>
</article>
"""
            )
        cards_html = "".join(cards)
        return f"""
<section class=\"roundup-section\">
  <div class=\"section-heading\">
    <span class=\"badge\">Daily automation</span>
    <h2>Fresh roundup playbooks</h2>
    <p>Run these pre-built top 10 lists with internal product pages and Amazon search links.</p>
  </div>
  <div class=\"grid\">{cards_html}</div>
</section>
"""

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
        breadcrumb_data = self._breadcrumb_structured_data(
            [
                ("Home", self._absolute_url("index.html")),
                (category.name, self._absolute_url(self._category_path(category.slug))),
            ]
        )
        item_list_data = self._item_list_structured_data(
            f"{category.name} gift ideas",
            [
                (product.title, self._absolute_url(self._product_path(product)))
                for product in products
            ],
        )
        collection_page_data = self._collection_page_structured_data(
            name=f"{category.name} gift ideas",
            description=category.blurb or self.settings.description,
            url=self._absolute_url(self._category_path(category.slug)),
            item_list=item_list_data,
        )
        structured_data = [breadcrumb_data, item_list_data, collection_page_data]
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
        product_slug_attr = html.escape(product.slug, quote=True)
        category_slug_attr = html.escape(product.category_slug or "", quote=True)
        category_name_attr = html.escape(category.name, quote=True)
        retailer_slug_attr = html.escape(product.retailer_slug or "", quote=True)
        retailer_name_attr = html.escape(product.retailer_name or "", quote=True)
        product_title_attr = html.escape(product.title, quote=True)
        analytics_base_parts = [
            f'data-product="{product_slug_attr}"',
            f'data-product-name="{product_title_attr}"',
            f'data-category="{category_slug_attr}"',
            f'data-category-name="{category_name_attr}"',
            f'data-retailer="{retailer_slug_attr}"',
        ]
        if retailer_name_attr:
            analytics_base_parts.append(
                f'data-retailer-name="{retailer_name_attr}"'
            )
        analytics_base = " ".join(analytics_base_parts)
        engagement_html = f"""
<div class="engagement-tools">
  <button class="wishlist-toggle" type="button" data-wishlist="toggle" {analytics_base} data-analytics="wishlist" data-event="wishlist-toggle" data-placement="product-page" data-label="Save to shortlist" aria-pressed="false">Save to shortlist</button>
  <div class="share-controls">
    <button class="share-primary" type="button" data-share {analytics_base} data-analytics="share" data-event="share-open" data-placement="product-page" data-label="Open share menu">Share with a friend</button>
    <div class="share-links">
      <button class="share-copy" type="button" data-copy="{html.escape(canonical_url)}" {analytics_base} data-analytics="share" data-event="share-copy" data-placement="product-page" data-label="Copy product link">Copy link</button>
      <a href="{tweet_url}" target="_blank" rel="noopener" {analytics_base} data-analytics="share" data-event="share-twitter" data-placement="product-page" data-label="Tweet share">Tweet</a>
      <a href="{facebook_url}" target="_blank" rel="noopener" {analytics_base} data-analytics="share" data-event="share-facebook" data-placement="product-page" data-label="Facebook share">Share</a>
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
                f'<p class="cta-row"><a class="cta-button" href="{html.escape(product.link)}" target="_blank" rel="noopener sponsored" {analytics_base} data-analytics="product-cta" data-event="cta-click" data-placement="product-page" data-label="{html.escape(cta_label, quote=True)}">{html.escape(cta_label)}</a></p>'
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
        primary_use = product.keywords[0] if product.keywords else None
        page_title = make_title(
            TitleParams(
                name=product.title,
                brand=product.brand,
                category=category.name,
                use=primary_use,
            )
        )
        if product.summary:
            description = product.summary
        else:
            parsed = parse_price_string(product.price)
            price_value = parsed[0] if parsed else None
            currency = parsed[1] if parsed else None
            description = make_meta(
                MetaParams(
                    name=product.title,
                    price=price_value,
                    currency=currency,
                    specs=(product.keywords or [])[:3],
                    use=primary_use,
                )
            )
        context = PageContext(
            title=page_title,
            description=description or self.settings.description,
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
        if not passes_seo(
            SeoPayload(title=context.title, description=context.description, body=body)
        ):
            logger.warning(
                "SEO gate failed for product %s; marking page as noindex", product.slug
            )
            context.noindex = True
            self._seo_failures.add(product.slug)
        path = self.products_dir / product.slug / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(path, context)

    def _write_generated_product_page(self, product: GeneratedProduct) -> None:
        category_seed = slugify(product.category or "gifts")
        fallback_image = f"https://source.unsplash.com/1200x630/?{html.escape(category_seed)}"
        image_url = html.escape(product.image or fallback_image)
        bullet_items = "".join(
            f"<li>{html.escape(line)}</li>" for line in product.bullets
        )
        bullets_html = (
            f"<ul class=\"generated-highlights\">{bullet_items}</ul>"
            if bullet_items
            else "<p>Quick gifting win with practical utility.</p>"
        )
        caveat_items = "".join(
            f"<li>{html.escape(line)}</li>" for line in product.caveats
        )
        caveats_html = (
            f"<section><h2>Consider</h2><ul>{caveat_items}</ul></section>"
            if caveat_items
            else ""
        )
        affiliate = html.escape(product.affiliate_url)
        intro_text = product.intro or intro_breakdown(product.name, product.price_cap)
        intro = html.escape(intro_text)
        query = html.escape(product.query)
        body = f"""
<article class=\"generated-product\">
  <header>
    <h1>{html.escape(product.name)}</h1>
    <p>{intro}</p>
    <div class=\"card-actions\">
      <a class=\"button-link\" href=\"{affiliate}\" target=\"_blank\" rel=\"nofollow sponsored noopener\">Check current price on Amazon</a>
    </div>
  </header>
  <div class=\"generated-product__media\">
    <img src=\"{image_url}\" alt=\"{html.escape(product.name)}\" loading=\"lazy\" decoding=\"async\" />
  </div>
  <section>
    <h2>Highlights</h2>
    {bullets_html}
  </section>
  {caveats_html}
  <section>
    <h2>Search it on Amazon</h2>
    <p><a href=\"{affiliate}\" target=\"_blank\" rel=\"nofollow sponsored noopener\">{query}</a></p>
  </section>
</article>
"""
        canonical = self._absolute_url(self._generated_product_path(product))
        structured_data = [
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": product.name,
                "description": desc_breakdown(product.name),
                "brand": product.category or "Gift Idea",
                "offers": {
                    "@type": "Offer",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock",
                    "url": product.affiliate_url,
                },
            }
        ]
        context = PageContext(
            title=title_breakdown(product.name, product.category, product.price_cap),
            description=desc_breakdown(product.name),
            canonical_url=canonical,
            body=body,
            og_image=image_url,
            og_type="article",
            structured_data=structured_data,
            updated_time=self._format_iso8601(self._parse_iso_datetime(product.updated_at)),
            published_time=self._format_iso8601(self._parse_iso_datetime(product.published_at)),
        )
        output_path = self.output_dir / self._generated_product_path(product)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(output_path, context)

    def _write_roundup_page(self, roundup: RoundupArticle) -> None:
        items_html = []
        list_items: List[tuple[str, str]] = []
        for item in roundup.items:
            target_product = self._generated_lookup.get(item.product_slug)
            if target_product:
                product_url = f"/{self._generated_product_path(target_product)}"
            else:
                product_url = f"/products/{item.product_slug}/index.html"
            list_items.append((item.title, self._absolute_url(product_url)))
            items_html.append(
                f"""
<li>
  <h3><a href=\"{product_url}\">{html.escape(item.title)}</a></h3>
  <p>{html.escape(item.summary)}</p>
</li>
"""
            )
        items_markup = "".join(items_html)
        search_link = html.escape(roundup.amazon_search_url)
        body = f"""
<article class=\"roundup-detail\">
  <header>
    <h1>{html.escape(roundup.title)}</h1>
    <p>{html.escape(roundup.intro)}</p>
  </header>
  <ol class=\"roundup-list\">{items_markup}</ol>
  <section class=\"roundup-search\">
    <a class=\"cta-secondary\" href=\"{search_link}\" target=\"_blank\" rel=\"nofollow sponsored noopener\">Search Amazon for {html.escape(roundup.topic)} ideas</a>
  </section>
</article>
"""
        canonical = self._absolute_url(self._roundup_path(roundup))
        structured_data = [
            self._item_list_structured_data(roundup.title, list_items)
        ]
        updated_time = self._format_iso8601(self._parse_iso_datetime(roundup.updated_at))
        published_time = self._format_iso8601(self._parse_iso_datetime(roundup.published_at))
        og_image = f"https://source.unsplash.com/1200x630/?{html.escape(slugify(roundup.topic or 'gifts'))}"
        context = PageContext(
            title=roundup.title,
            description=roundup.description,
            canonical_url=canonical,
            body=body,
            og_image=og_image,
            og_type="article",
            structured_data=structured_data,
            updated_time=updated_time,
            published_time=published_time,
        )
        output_path = self.output_dir / self._roundup_path(roundup)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_page(output_path, context)

    def _write_articles(
        self,
        articles: Sequence[Article],
        categories: List[Category],
        products: List[Product],
    ) -> None:
        category_lookup = {category.slug: category for category in categories}
        product_lookup = {product.slug: product for product in products}
        for article in articles:
            output_path = self.output_dir / article.path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            context = self._article_page_context(article, category_lookup, product_lookup)
            self._write_page(output_path, context)

    def _article_page_context(
        self,
        article: Article,
        category_lookup: dict[str, Category],
        product_lookup: dict[str, Product],
    ) -> PageContext:
        canonical_url = self._absolute_url(article.path)
        body = self._render_article_body(article, category_lookup, product_lookup)
        structured_data = [self._article_structured_data(article, canonical_url)]
        hero = article.hero_image or DEFAULT_SOCIAL_IMAGE
        return PageContext(
            title=article.title,
            description=article.description,
            canonical_url=canonical_url,
            body=body,
            og_image=hero,
            structured_data=structured_data,
            og_type="article",
            og_image_alt=article.title,
            updated_time=article.updated_at,
            published_time=article.published_at,
        )

    def _render_article_body(
        self,
        article: Article,
        category_lookup: dict[str, Category],
        product_lookup: dict[str, Product],
    ) -> str:
        hero_image = html.escape(article.hero_image or DEFAULT_SOCIAL_IMAGE)
        hero_html = f"""
<header class="guide-hero">
  <div class="guide-hero-media">
    <img src="{hero_image}" alt="{html.escape(article.title)}" loading="lazy" decoding="async" />
  </div>
  <div class="guide-hero-copy">
    <span class="guide-kind">{html.escape(article.kind.title())}</span>
    <h1>{html.escape(article.title)}</h1>
    <p>{html.escape(article.description)}</p>
  </div>
</header>
""".strip()
        toc_links = ""
        if article.table_of_contents:
            links = "".join(
                f'<li><a href="#{html.escape(anchor, quote=True)}">{html.escape(title)}</a></li>'
                for anchor, title in article.table_of_contents
            )
            toc_links = f"""
<nav class="guide-toc" aria-label="In this guide">
  <strong>In this guide</strong>
  <ol>{links}</ol>
</nav>
""".strip()
        intro_paragraphs = "".join(
            f"<p>{html.escape(paragraph)}</p>" for paragraph in article.intro
        )
        hub_links: List[str] = []
        for slug in article.hub_slugs:
            category = category_lookup.get(slug)
            if not category:
                continue
            hub_links.append(
                f'<li><a href="/{html.escape(self._category_path(category.slug))}">{html.escape(category.name)}</a></li>'
            )
        hubs_html = ""
        if hub_links:
            hubs_html = (
                "<div class=\"guide-hubs\">"
                "<h2>Explore related hubs</h2>"
                f"<ul>{''.join(hub_links)}</ul>"
                "</div>"
            )
        items_html: List[str] = []
        ads_enabled = self._adsense_inline_enabled()
        for index, item in enumerate(article.items, start=1):
            items_html.append(self._render_article_item(index, item, product_lookup))
            if ads_enabled and index % 4 == 0:
                ad_unit = self._adsense_unit(
                    self.settings.adsense_slot or "",
                    extra_class="adsense-slot--article",
                )
                if ad_unit:
                    items_html.append(f'<div class="guide-ad">{ad_unit}</div>')
        items_section = "".join(items_html)
        who_anchor = slugify("who-its-for")
        consider_anchor = slugify("consider")
        related_anchor = slugify("related-picks")
        who_html = f"""
<section class="guide-section" id="{html.escape(who_anchor, quote=True)}">
  <h2>Who it's for</h2>
  <p>{html.escape(article.who_for)}</p>
</section>
""".strip()
        consider_html = f"""
<section class="guide-section" id="{html.escape(consider_anchor, quote=True)}">
  <h2>Consider</h2>
  <p>{html.escape(article.consider)}</p>
</section>
""".strip()
        related_links: List[str] = []
        for slug in article.related_product_slugs:
            product = product_lookup.get(slug)
            if product:
                related_links.append(
                    f'<li><a href="/{html.escape(self._product_path(product))}">{html.escape(product.title)}</a></li>'
                )
                continue
            category = category_lookup.get(slug)
            if category:
                related_links.append(
                    f'<li><a href="/{html.escape(self._category_path(category.slug))}">{html.escape(category.name)}</a></li>'
                )
        related_html = ""
        if related_links:
            related_html = f"""
<section class="guide-related" id="{html.escape(related_anchor, quote=True)}">
  <h2>Related picks</h2>
  <ul>{''.join(related_links)}</ul>
</section>
""".strip()
        return f"""
<article class="guide">
  {hero_html}
  {toc_links}
  <section class="guide-intro">
    {intro_paragraphs}
    {hubs_html}
  </section>
  <section class="guide-items">
    {items_section}
  </section>
  {who_html}
  {consider_html}
  {related_html}
</article>
""".strip()

    def _render_article_item(
        self,
        index: int,
        item: ArticleItem,
        product_lookup: dict[str, Product],
    ) -> str:
        anchor = html.escape(item.anchor or f"item-{index}", quote=True)
        image = html.escape(item.image or DEFAULT_SOCIAL_IMAGE)
        title = html.escape(item.title)
        blurb = html.escape(item.blurb)
        specs_html = "".join(
            f"<li>{html.escape(spec)}</li>" for spec in item.specs if spec
        )
        product = product_lookup.get(item.product_slug)
        if product:
            product_path = self._product_path(product)
            internal_url = f"/{product_path}"
        else:
            fallback_slug = slugify(item.product_slug)
            internal_url = f"/products/{fallback_slug}/index.html"
        internal_link = (
            f'<a class="pill-link" href="{html.escape(internal_url)}">Read the hype</a>'
        )
        outbound_link = ""
        if item.outbound_url:
            outbound_link = (
                f'<a class="cta-secondary" href="{html.escape(item.outbound_url)}" '
                "target=\"_blank\" rel=\"noopener sponsored\">Shop now</a>"
            )
        tags_html = ""
        if item.tags:
            tags_html = "".join(
                f"<span>{html.escape(tag)}</span>" for tag in item.tags[:3]
            )
            tags_html = f'<div class="guide-item-tags">{tags_html}</div>'
        return f"""
<section class="guide-item" id="{anchor}">
  <div class="guide-item-media">
    <img src="{image}" alt="{title}" loading="lazy" decoding="async" />
  </div>
  <div class="guide-item-body">
    <h2><span class="guide-item-index">{index}</span> {title}</h2>
    <p>{blurb}</p>
    <ul class="guide-item-specs">{specs_html}</ul>
    {tags_html}
    <div class="guide-item-links">{internal_link}{outbound_link}</div>
  </div>
</section>
""".strip()

    def _article_structured_data(self, article: Article, canonical_url: str) -> dict:
        base_url = self.settings.base_url.rstrip("/")
        tags = [
            {"@type": "Thing", "name": tag}
            for tag in (article.tags[:10] if article.tags else [])
        ]
        publisher_logo = self.settings.logo_url or DEFAULT_SOCIAL_IMAGE
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": article.title,
            "description": article.description,
            "image": article.hero_image or DEFAULT_SOCIAL_IMAGE,
            "datePublished": article.published_at or article.updated_at,
            "dateModified": article.updated_at,
            "mainEntityOfPage": canonical_url,
            "isPartOf": {
                "@type": "WebSite",
                "name": self.settings.site_name,
                "url": base_url,
            },
            "about": tags,
            "author": {
                "@type": "Organization",
                "name": self.settings.site_name,
            },
            "publisher": {
                "@type": "Organization",
                "name": self.settings.site_name,
                "url": base_url,
                "logo": {
                    "@type": "ImageObject",
                    "url": publisher_logo,
                },
            },
        }

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
        item_list_data = self._item_list_structured_data(
            "Latest gift ideas",
            [
                (product.title, self._absolute_url(self._product_path(product)))
                for product in products[:30]
            ],
        )
        collection_page_data = self._collection_page_structured_data(
            name="Latest gift drops",
            description="The newest Grab Gifts drops from Amazon and partners, refreshed automatically for maximum conversion potential.",
            url=self._absolute_url("latest.html"),
            item_list=item_list_data,
        )
        structured_data = [item_list_data, collection_page_data]
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
        breadcrumb_data = self._breadcrumb_structured_data(
            [
                ("Home", self._absolute_url("index.html")),
                ("Deals", self._absolute_url("deals.html")),
            ]
        )
        item_list_data = self._item_list_structured_data(
            "Top gift deals",
            [
                (product.title, self._absolute_url(self._product_path(product)))
                for product in top_products[:30]
            ],
        )
        deals_description = "See the biggest price drops across Grab Gifts' Amazon finds, refreshed daily."
        collection_page_data = self._collection_page_structured_data(
            name="Today's best gift deals",
            description=deals_description,
            url=self._absolute_url("deals.html"),
            item_list=item_list_data,
        )
        structured_data = [breadcrumb_data, item_list_data, collection_page_data]
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
            description=deals_description,
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
            drop_amount = product.price_drop_amount()
            drop_percent = product.price_drop_percent()
            on_deal = drop_amount is not None
            drop_label = ""
            if drop_amount is not None:
                currency_code = latest_point.currency if latest_point else None
                formatted_amount = self._format_currency(drop_amount, currency_code)
                if drop_percent is not None:
                    drop_label = f"↓ {drop_percent:.0f}% ({formatted_amount} off)"
                else:
                    drop_label = f"↓ {formatted_amount} off"
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
                    "priceDropAmount": drop_amount,
                    "priceDropPercent": drop_percent,
                    "priceDropLabel": drop_label,
                    "onDeal": on_deal,
                    "rating": product.rating,
                    "retailerName": product.retailer_name,
                    "retailerSlug": product.retailer_slug,
                }
            )
        dataset = json.dumps(index_entries, ensure_ascii=False).replace("</", "<\\/")
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
    <label for="filter-deal">Deal status</label>
    <select id="filter-deal" name="deal">
      <option value="all">Any status</option>
      <option value="on-sale">On sale</option>
      <option value="drop-10">Price drop ≥ 10%</option>
      <option value="drop-25">Price drop ≥ 25%</option>
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
const dealSelect = document.getElementById('filter-deal');
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
    deal: dealSelect.value || 'all',
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
  if (filters.deal !== 'all') {{
    const percent = typeof item.priceDropPercent === 'number' ? item.priceDropPercent : null;
    const onSale = Boolean(item.onDeal) || (percent !== null && percent > 0);
    if (filters.deal === 'on-sale') {{
      if (!onSale) {{
        return false;
      }}
    }} else if (filters.deal === 'drop-10') {{
      if (!(percent !== null && percent >= 10)) {{
        return false;
      }}
    }} else if (filters.deal === 'drop-25') {{
      if (!(percent !== null && percent >= 25)) {{
        return false;
      }}
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
  const hasFilters = filters.price !== 'all' || filters.rating !== 'all' || filters.deal !== 'all' || filters.retailer !== 'all';
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
    if (match.priceDropLabel) {{
      metaParts.push(match.priceDropLabel);
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
  deal: params.get('deal') || 'all',
  retailer: params.get('retailer') || 'all',
}};
const priceOptions = new Set(['all', 'under-25', '25-50', '50-100', '100-plus']);
const ratingOptions = new Set(['all', '4', '4.5']);
const dealOptions = new Set(['all', 'on-sale', 'drop-10', 'drop-25']);
if (!priceOptions.has(initialFilters.price)) {{
  initialFilters.price = 'all';
}}
if (!ratingOptions.has(initialFilters.rating)) {{
  initialFilters.rating = 'all';
}}
if (!dealOptions.has(initialFilters.deal)) {{
  initialFilters.deal = 'all';
}}
if (initialFilters.retailer && !retailerMap.has(initialFilters.retailer)) {{
  initialFilters.retailer = 'all';
}}
input.value = initial;
priceSelect.value = initialFilters.price;
ratingSelect.value = initialFilters.rating;
dealSelect.value = initialFilters.deal;
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
dealSelect.addEventListener('change', () => {{
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

    def _write_feed(
        self,
        products: List[Product],
        generated: Sequence[GeneratedProduct] | None = None,
        roundups: Sequence[RoundupArticle] | None = None,
    ) -> None:
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
        generated_items = [
            product
            for product in (generated or [])
            if getattr(product, "status", "published") == "published"
        ]
        if generated_items:
            for product in generated_items[:15]:
                link = self._absolute_url(self._generated_product_path(product))
                published = product.published_at or product.updated_at or ""
                description = product.intro or "Check highlights and caveats before gifting."
                item_blocks.append(
                    f"""
    <item>
      <title>{html.escape(product.name)}</title>
      <link>{html.escape(link)}</link>
      <guid>{html.escape(f'generated:{product.slug}')}</guid>
      <description>{html.escape(description)}</description>
      <pubDate>{html.escape(published)}</pubDate>
    </item>
"""
                )
        roundup_items = [
            roundup
            for roundup in (roundups or [])
            if getattr(roundup, "status", "published") == "published"
        ]
        if roundup_items:
            for roundup in roundup_items[:15]:
                link = self._absolute_url(self._roundup_path(roundup))
                published = roundup.published_at or roundup.updated_at or ""
                item_blocks.append(
                    f"""
    <item>
      <title>{html.escape(roundup.title)}</title>
      <link>{html.escape(link)}</link>
      <guid>{html.escape(f'roundup:{roundup.slug}')}</guid>
      <description>{html.escape(roundup.description)}</description>
      <pubDate>{html.escape(published)}</pubDate>
    </item>
"""
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

    def _write_sitemap(
        self,
        categories: List[Category],
        products: List[Product],
        articles: Sequence[Article] | None = None,
        generated_products: Sequence[GeneratedProduct] | None = None,
        roundups: Sequence[RoundupArticle] | None = None,
    ) -> None:
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
        generated_items = [
            product
            for product in (generated_products or [])
            if getattr(product, "status", "published") == "published"
        ]
        roundup_items = [
            roundup
            for roundup in (roundups or [])
            if getattr(roundup, "status", "published") == "published"
        ]
        for product in generated_items:
            updated = (
                self._parse_iso_datetime(product.updated_at)
                or self._parse_iso_datetime(product.published_at)
            )
            if updated and updated > latest_site_update:
                latest_site_update = updated
        for roundup in roundup_items:
            updated = (
                self._parse_iso_datetime(roundup.updated_at)
                or self._parse_iso_datetime(roundup.published_at)
            )
            if updated and updated > latest_site_update:
                latest_site_update = updated
        article_entries: List[dict[str, str | None]] = []
        for article in articles or []:
            if article.status != "published" or article.body_length < 800:
                continue
            updated = self._parse_iso_datetime(article.updated_at)
            if updated and updated > latest_site_update:
                latest_site_update = updated
            entry = {
                "loc": self._absolute_url(article.path),
                "lastmod": self._format_iso8601(updated),
                "changefreq": "weekly",
                "priority": "0.65",
            }
            article_entries.append(entry)
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
            if product.slug in self._seo_failures:
                continue
            entries.append(
                {
                    "loc": self._absolute_url(self._product_path(product)),
                    "lastmod": self._format_iso8601(product_lastmods.get(product.slug)),
                    "changefreq": "weekly",
                    "priority": "0.6",
                }
            )
        for product in generated_items:
            path = self._generated_product_path(product)
            updated = self._parse_iso_datetime(product.updated_at) or self._parse_iso_datetime(
                product.published_at
            )
            entries.append(
                {
                    "loc": self._absolute_url(path),
                    "lastmod": self._format_iso8601(updated),
                    "changefreq": "daily",
                    "priority": "0.55",
                }
            )
        for roundup in roundup_items:
            path = self._roundup_path(roundup)
            updated = self._parse_iso_datetime(roundup.updated_at) or self._parse_iso_datetime(
                roundup.published_at
            )
            entries.append(
                {
                    "loc": self._absolute_url(path),
                    "lastmod": self._format_iso8601(updated),
                    "changefreq": "daily",
                    "priority": "0.58",
                }
            )
        entries.extend(article_entries)
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

    def _write_robots(self) -> None:
        sitemap_url = self._absolute_url("sitemap.xml")
        content = "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                f"Sitemap: {sitemap_url}",
            ]
        )
        (self.output_dir / "robots.txt").write_text(f"{content}\n", encoding="utf-8")

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
      <button type=\"submit\" data-analytics=\"newsletter\" data-event=\"newsletter-submit\" data-category=\"newsletter\" data-placement=\"newsletter-banner\" data-label=\"{button_label}\">{button_label}</button>
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

    def _collection_page_structured_data(
        self, *, name: str, description: str, url: str, item_list: dict
    ) -> dict:
        has_part = {key: value for key, value in item_list.items() if key != "@context"}
        website_url = (self.settings.base_url or "").strip()
        website: dict[str, str] = {"@type": "WebSite", "name": self.settings.site_name}
        if website_url:
            website["url"] = website_url
        data: dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": name,
            "description": description,
            "url": url,
            "hasPart": has_part,
        }
        if website:
            data["isPartOf"] = website
        return data

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
        if product.brand:
            data["brand"] = {"@type": "Brand", "name": product.brand}
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
    def _format_display_date(value: datetime | None) -> str:
        if not value:
            return "—"
        return value.strftime("%b %d, %Y")

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
        category = self._category_lookup.get(product.category_slug)
        fallback_seed = (category.slug if category else product.category_slug) or "gifts"
        fallback_image = f"https://source.unsplash.com/600x400/?{fallback_seed}"
        image_url = product.image or fallback_image
        image = html.escape(image_url)
        category_badge = ""
        if category:
            category_badge = f'<span class="card-badge">{html.escape(category.name)}</span>'
        product_slug_attr = html.escape(product.slug, quote=True)
        category_slug_attr = html.escape(product.category_slug or "", quote=True)
        category_name_attr = (
            html.escape(category.name, quote=True) if category else ""
        )
        retailer_slug_attr = html.escape(product.retailer_slug or "", quote=True)
        retailer_name_attr = html.escape(product.retailer_name or "", quote=True)
        product_label_attr = html.escape(product.title, quote=True)
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
            analytics_attrs = [
                'data-analytics="product-cta"',
                'data-event="cta-click"',
                f'data-product="{product_slug_attr}"',
                f'data-product-name="{product_label_attr}"',
                f'data-category="{category_slug_attr}"',
                f'data-retailer="{retailer_slug_attr}"',
                'data-placement="product-card"',
                f'data-label="{product_label_attr}"',
            ]
            if category_name_attr:
                analytics_attrs.append(
                    f'data-category-name="{category_name_attr}"'
                )
            if retailer_name_attr:
                analytics_attrs.append(
                    f'data-retailer-name="{retailer_name_attr}"'
                )
            analytics_attr_str = " ".join(analytics_attrs)
            outbound_cta = (
                f' <a class="cta-secondary" href="{html.escape(product.link)}" target="_blank" rel="noopener sponsored" {analytics_attr_str}>{html.escape(cta_copy)}</a>'
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

    def _generated_product_path(self, product: GeneratedProduct) -> str:
        return f"products/{product.slug}/index.html"

    def _roundup_path(self, roundup: RoundupArticle) -> str:
        return f"guides/{roundup.slug}/index.html"

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
