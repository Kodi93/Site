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

from .config import OUTPUT_DIR, SiteSettings, ensure_directories
from .models import Category, Product

logger = logging.getLogger(__name__)

ASSETS_STYLES = """
:root {
  color-scheme: light dark;
  --brand: #ff5a5f;
  --brand-dark: #e04850;
  --accent: #2563eb;
  --bg: #f6f7fb;
  --bg-muted: #eef1f9;
  --text: #0f172a;
  --muted: #52606d;
  --muted-strong: #334155;
  --card: #ffffff;
  --card-elevated: #fefefe;
  --border: rgba(15, 23, 42, 0.08);
  --border-strong: rgba(15, 23, 42, 0.14);
  --overlay: rgba(15, 23, 42, 0.04);
  --pill-bg: rgba(255, 90, 95, 0.12);
  --pill-bg-hover: rgba(255, 90, 95, 0.22);
  --badge-bg: rgba(37, 99, 235, 0.14);
  --badge-color: #1d4ed8;
  --price-bg: rgba(37, 99, 235, 0.12);
  --rating-bg: rgba(255, 90, 95, 0.16);
  --newsletter-bg: rgba(37, 99, 235, 0.08);
  --newsletter-border: rgba(37, 99, 235, 0.28);
  --input-bg: #ffffff;
  --input-border: rgba(15, 23, 42, 0.12);
  --shadow-soft: 0 12px 28px rgba(15, 23, 42, 0.08);
  --shadow-card: 0 20px 45px rgba(15, 23, 42, 0.12);
  --shadow-card-hover: 0 28px 55px rgba(15, 23, 42, 0.18);
  --header-bg: rgba(255, 255, 255, 0.82);
  --hero-glow: radial-gradient(120% 120% at 50% 0%, rgba(255, 90, 95, 0.08) 0%, rgba(37, 99, 235, 0.05) 42%, transparent 100%);
  --theme-track: rgba(15, 23, 42, 0.12);
  --theme-thumb: #ffffff;
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

:root[data-theme='dark'] {
  color-scheme: dark light;
  --bg: #0f172a;
  --bg-muted: #111c2f;
  --text: #f8fafc;
  --muted: #94a3b8;
  --muted-strong: #e2e8f0;
  --card: #0f1d32;
  --card-elevated: #13233b;
  --border: rgba(148, 163, 184, 0.18);
  --border-strong: rgba(148, 163, 184, 0.32);
  --overlay: rgba(148, 163, 184, 0.16);
  --pill-bg: rgba(255, 90, 95, 0.25);
  --pill-bg-hover: rgba(255, 90, 95, 0.35);
  --badge-bg: rgba(37, 99, 235, 0.35);
  --badge-color: #93c5fd;
  --price-bg: rgba(37, 99, 235, 0.28);
  --rating-bg: rgba(255, 90, 95, 0.35);
  --newsletter-bg: rgba(37, 99, 235, 0.24);
  --newsletter-border: rgba(37, 99, 235, 0.38);
  --input-bg: rgba(15, 23, 42, 0.8);
  --input-border: rgba(148, 163, 184, 0.35);
  --shadow-soft: 0 18px 38px rgba(0, 0, 0, 0.35);
  --shadow-card: 0 30px 55px rgba(0, 0, 0, 0.45);
  --shadow-card-hover: 0 36px 65px rgba(0, 0, 0, 0.55);
  --header-bg: rgba(15, 23, 42, 0.82);
  --hero-glow: radial-gradient(120% 120% at 50% 0%, rgba(255, 90, 95, 0.18) 0%, rgba(37, 99, 235, 0.14) 45%, rgba(2, 6, 23, 0.9) 100%);
  --theme-track: rgba(148, 163, 184, 0.32);
  --theme-thumb: #0b1526;
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
  background-image: var(--hero-glow);
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
  border-bottom: 1px solid var(--border-strong);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  transition: background 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease;
}

:root[data-theme='dark'] header {
  box-shadow: 0 22px 48px rgba(0, 0, 0, 0.45);
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
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  box-shadow: 0 0 0 3px rgba(255, 90, 95, 0.2);
}

:root[data-theme='dark'] .logo::before {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3);
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
  color: var(--text);
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
  border: 1px solid transparent;
  font-weight: 600;
  color: var(--brand);
  background: var(--pill-bg);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}

.pill-link:hover,
.pill-link:focus {
  background: var(--pill-bg-hover);
  color: var(--brand-dark);
  transform: translateY(-2px);
  border-color: rgba(255, 90, 95, 0.35);
}

.search-form {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.6rem;
  background: var(--overlay);
  border-radius: 999px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-soft);
}

:root[data-theme='dark'] .search-form {
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
  color: var(--brand);
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
  border-color: rgba(255, 90, 95, 0.4);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-text {
  color: var(--brand);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-track {
  background: linear-gradient(135deg, var(--brand), var(--accent));
  box-shadow: 0 10px 25px rgba(255, 90, 95, 0.35);
}

.theme-toggle-input:checked + .theme-toggle-label .theme-toggle-thumb {
  transform: translateX(26px);
  box-shadow: 0 8px 18px rgba(255, 90, 95, 0.4);
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 2.5rem 2rem 4rem;
  flex: 1;
  width: 100%;
  transition: color 0.35s ease;
}

main > section + section {
  margin-top: 3.5rem;
}

.hero {
  position: relative;
  text-align: center;
  padding: 3.5rem 1.5rem;
  margin: 0 auto 3.5rem;
  max-width: 980px;
  background: linear-gradient(135deg, rgba(255, 90, 95, 0.08), rgba(37, 99, 235, 0.08)), var(--card);
  border-radius: 28px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top right, rgba(37, 99, 235, 0.28), transparent 55%), radial-gradient(circle at bottom left, rgba(255, 90, 95, 0.28), transparent 60%);
  opacity: 0.75;
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
  background: rgba(37, 99, 235, 0.14);
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 1.15rem;
}

.hero h1 {
  font-size: clamp(2.5rem, 4.5vw, 3.4rem);
  margin-bottom: 0.85rem;
}

.hero p {
  color: var(--muted);
  margin: 0 auto;
  max-width: 650px;
  font-size: 1.05rem;
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
  background: linear-gradient(135deg, var(--brand), var(--brand-dark));
  color: #fff;
  font-weight: 600;
  letter-spacing: 0.01em;
  box-shadow: 0 18px 40px rgba(255, 90, 95, 0.35);
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
  white-space: nowrap;
}

.button-link:hover,
.button-link:focus,
.cta-button:hover,
.cta-button:focus {
  transform: translateY(-2px);
  box-shadow: 0 24px 48px rgba(224, 72, 80, 0.4);
  filter: brightness(1.03);
}

.cta-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.8rem 1.15rem;
  border-radius: 999px;
  border: 1px solid transparent;
  font-weight: 600;
  color: var(--brand);
  background: var(--pill-bg);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}

.cta-secondary:hover,
.cta-secondary:focus {
  background: var(--pill-bg-hover);
  color: var(--brand-dark);
  transform: translateY(-2px);
  border-color: rgba(255, 90, 95, 0.35);
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

.grid {
  display: grid;
  gap: 1.75rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.card {
  background: var(--card);
  border-radius: 22px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-card-hover);
  border-color: var(--border-strong);
}

.card-media {
  position: relative;
  display: block;
  overflow: hidden;
  border-bottom: 1px solid var(--border);
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
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.3);
}

:root[data-theme='dark'] .card-badge {
  background: rgba(15, 23, 42, 0.9);
}

.card-content {
  padding: 1.35rem 1.5rem 1.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  flex: 1;
}

.card-content h3 {
  margin: 0;
  font-size: 1.15rem;
}

.card-content p {
  color: var(--muted);
  margin: 0;
  font-size: 0.97rem;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.92rem;
  color: var(--muted);
  align-items: center;
}

.card-price {
  font-weight: 600;
  color: var(--accent);
  background: var(--price-bg);
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
}

.card-rating {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--rating-bg);
  color: #fff;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
}

.card-rating svg {
  width: 14px;
  height: 14px;
}

.card-rating-count {
  color: var(--muted);
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
  gap: 2.25rem;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  align-items: center;
  margin-bottom: 2.8rem;
}

.category-hero p {
  color: var(--muted);
  font-size: 1.05rem;
}

.newsletter-banner {
  margin: 3.5rem auto 0;
  background: var(--newsletter-bg);
  border: 1px dashed var(--newsletter-border);
  border-radius: 22px;
  padding: 2.25rem;
  text-align: center;
  max-width: 760px;
  box-shadow: var(--shadow-soft);
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
  border: 1px solid var(--input-border);
  background: var(--input-bg);
  font-size: 1rem;
  color: var(--text);
  box-shadow: var(--shadow-soft);
}

.newsletter-fields input[type="email"]::placeholder {
  color: var(--muted);
}

.newsletter-fields button {
  flex: 0 0 auto;
  padding: 0.9rem 1.45rem;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, var(--brand), var(--brand-dark));
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 18px 38px rgba(255, 90, 95, 0.38);
  transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.newsletter-fields button:hover,
.newsletter-fields button:focus {
  transform: translateY(-2px);
  box-shadow: 0 26px 46px rgba(224, 72, 80, 0.42);
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
  background: var(--card);
  border-radius: 22px;
  padding: 1.75rem;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.value-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at top right, rgba(37, 99, 235, 0.15), transparent 60%);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.value-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-card-hover);
  border-color: var(--border-strong);
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
  background: var(--badge-bg);
  color: var(--badge-color);
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

.feature-list {
  padding-left: 1.2rem;
}

.cta-row {
  margin-top: 1.35rem;
}

.related-grid {
  margin-top: 3rem;
}

.related-grid h2 {
  text-align: center;
  margin-bottom: 1.6rem;
}

.adsense-slot {
  margin: 2rem auto;
  text-align: center;
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
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 1.5rem 1.75rem;
  box-shadow: var(--shadow-card);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.search-result:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-card-hover);
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
  border-top: 1px solid var(--border);
  margin-top: 3.5rem;
  padding: 2.5rem 1.5rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.92rem;
  background: linear-gradient(0deg, rgba(15, 23, 42, 0.02), transparent 60%);
  transition: background 0.35s ease, color 0.35s ease, border-color 0.35s ease;
}

:root[data-theme='dark'] footer {
  background: linear-gradient(0deg, rgba(15, 23, 42, 0.45), transparent 60%);
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
}

@media (max-width: 1024px) {
  nav {
    padding: 1rem 1.5rem;
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

  main {
    padding: 2rem 1.25rem 3rem;
  }

  .grid {
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
    """Generate static HTML pages for the curated gift site."""

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

    def build(self, categories: List[Category], products: List[Product]) -> None:
        logger.info("Generating site with %s products", len(products))
        self._write_assets()
        self.preload_navigation(categories)
        self._category_lookup = {category.slug: category for category in categories}
        products_sorted = sorted(products, key=lambda p: p.updated_at, reverse=True)
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
        nav_action_links = ['<a href="/latest.html">Latest</a>']
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
            "<label class=\"sr-only\" for=\"nav-search\">Search curated gifts</label>"
            "<input id=\"nav-search\" type=\"search\" name=\"q\" placeholder=\"Search curated gifts...\" aria-label=\"Search curated gifts\" />"
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
            "var storageKey='giftgrab-theme';"
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
        if self.settings.adsense_client_id and self.settings.adsense_slot:
            adsense_slot = (
                "<div class=\"adsense-slot\">"
                f"<ins class=\"adsbygoogle\" style=\"display:block\" data-ad-client=\"{self.settings.adsense_client_id}\" "
                f"data-ad-slot=\"{self.settings.adsense_slot}\" data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>"
                "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"
                "</div>"
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
    <main id=\"main-content\">
      {context.body}
      {adsense_slot}
    </main>
    <footer>
      <p>&copy; {now.year} {html.escape(self.settings.site_name)}. Updated {html.escape(now.strftime('%b %d, %Y'))}.</p>
      <p>As an Amazon Associate we earn from qualifying purchases. Links may generate affiliate revenue.</p>
      {footer_links}
    </footer>
    <script>
      (function() {
        var storageKey = 'giftgrab-theme';
        var root = document.documentElement;
        var toggle = document.getElementById('theme-switch');
        var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

        function setToggleState(theme) {
          if (!toggle) {
            return;
          }
          var isDark = theme === 'dark';
          toggle.checked = isDark;
          toggle.setAttribute('aria-checked', String(isDark));
        }

        function applyTheme(next) {
          var theme = next === 'dark' ? 'dark' : 'light';
          root.setAttribute('data-theme', theme);
          setToggleState(theme);
        }

        function readPreference() {
          try {
            return window.localStorage.getItem(storageKey);
          } catch (error) {
            return null;
          }
        }

        function storePreference(value) {
          try {
            window.localStorage.setItem(storageKey, value);
          } catch (error) {
            return;
          }
        }

        var saved = readPreference();
        if (saved === 'dark' || saved === 'light') {
          applyTheme(saved);
        } else {
          applyTheme(mediaQuery.matches ? 'dark' : 'light');
        }

        mediaQuery.addEventListener('change', function (event) {
          if (!readPreference()) {
            applyTheme(event.matches ? 'dark' : 'light');
          }
        });

        if (toggle) {
          toggle.addEventListener('change', function (event) {
            var mode = event.target.checked ? 'dark' : 'light';
            applyTheme(mode);
            storePreference(mode);
          });
        }

        window.addEventListener('storage', function (event) {
          if (event.key === storageKey) {
            applyTheme(event.newValue === 'dark' ? 'dark' : 'light');
          }
        });
      })();
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
        hero = f"""
<section class=\"hero\">
  <span class=\"eyebrow\">Conversion-optimized gift discovery</span>
  <h1>{html.escape(self.settings.site_name)}</h1>
  <p>{html.escape(self.settings.description)}</p>
  <div class=\"hero-actions\">
    <a class=\"button-link\" href=\"{cta_href}\">Browse curated gems</a>
    <a class=\"cta-secondary\" href=\"/latest.html\">See what's new today</a>
  </div>
</section>
"""
        category_cards = "".join(
            self._category_card(category) for category in categories
        )
        featured_cards = "".join(
            self._product_card(product) for product in featured_products
        )
        category_section = f"""
<section>
  <div class=\"section-heading\">
    <h2>Explore by vibe</h2>
    <p>Jump into themed collections that blend persuasive copy, contextual affiliate links, and display ad slots.</p>
  </div>
  <div class=\"grid\">{category_cards}</div>
</section>
"""
        featured_section = f"""
<section class=\"latest-intro\">
  <div class=\"section-heading\">
    <h2>Latest trending gifts</h2>
    <p>Freshly ingested Amazon finds with hype-driven descriptions, perfect for daily newsletter mentions or social promos.</p>
  </div>
  <div class=\"grid\">{featured_cards}</div>
  <p><a class=\"cta-secondary\" href=\"/latest.html\">View the full trending list</a></p>
</section>
"""
        value_props = """
<section class=\"value-prop\">
  <div class=\"section-heading\">
    <h2>Why marketers love Curated Gift Radar</h2>
    <p>We do the heavy lifting so you can focus on distribution, partnerships, and profitable ad spend.</p>
  </div>
  <div class=\"value-grid\">
    <article class=\"value-card\">
      <span class=\"badge\">SEO Ready</span>
      <h3>Long-form copy that ranks</h3>
      <p>Every page ships with keyword-rich storytelling, internal links, and structured data to woo organic traffic.</p>
    </article>
    <article class=\"value-card\">
      <span class=\"badge\">Affiliate Friendly</span>
      <h3>Monetize every click</h3>
      <p>Amazon partner tags are hard-wired into each CTA so discovery instantly turns into tracked commissions.</p>
    </article>
    <article class=\"value-card\">
      <span class=\"badge\">Fresh Daily</span>
      <h3>Automations keep it relevant</h3>
      <p>Nightly refreshes ensure your catalogue reflects the latest viral finds and seasonal crowd-pleasers.</p>
    </article>
  </div>
</section>
"""
        newsletter_banner = self._newsletter_banner()
        body = f"{hero}{category_section}{featured_section}{newsletter_banner}{value_props}"
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
            title=f"{self.settings.site_name} — Daily curated Amazon gift ideas",
            description=self.settings.description,
            canonical_url=f"{self.settings.base_url.rstrip('/')}/index.html",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
            og_image_alt=self.settings.site_name,
            updated_time=self._format_iso8601(latest_site_update),
        )
        self._write_page(self.output_dir / "index.html", context)

    def _write_category_page(self, category: Category, products: List[Product]) -> None:
        cards = "".join(self._product_card(product) for product in products)
        amazon_url = (
            f"https://www.amazon.com/s?k={html.escape('+'.join(category.keywords))}"
        )
        if self.settings.amazon_partner_tag:
            amazon_url = f"{amazon_url}&tag={html.escape(self.settings.amazon_partner_tag)}"
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
        price_line = f"<p class=\"price-callout\">{html.escape(product.price)}</p>" if product.price else ""
        rating_line = (
            f"<p class=\"review-callout\">{product.rating:.1f} / 5.0 ({product.total_reviews:,} reviews)</p>"
            if product.rating and product.total_reviews
            else ""
        )
        related_section = ""
        if related:
            related_cards = "".join(self._product_card(item) for item in related)
            related_section = f"""
<section class=\"related-grid\">
  <h2>More {html.escape(category.name)} hits</h2>
  <div class=\"grid\">{related_cards}</div>
</section>
"""
        breadcrumbs_html = f"""
<div class=\"breadcrumbs\"><a href=\"/index.html\">Home</a> &rsaquo; <a href=\"/{self._category_path(category.slug)}\">{html.escape(category.name)}</a></div>
"""
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
        extra_head_parts.append(
            '<meta property="product:availability" content="in stock" />'
        )
        extra_head = "\n    ".join(extra_head_parts)
        body = f"""
{breadcrumbs_html}
<div class=\"product-page\">
  <div>
    <img src=\"{html.escape(image_url)}\" alt=\"{html.escape(product.title)}\" loading=\"lazy\" decoding=\"async\" />
  </div>
  <div class=\"product-meta\">
    <h1>{html.escape(product.title)}</h1>
    {price_line}
    {rating_line}
    {product.blog_content or ''}
    <p class=\"cta-row\"><a class=\"cta-button\" href=\"{html.escape(product.link)}\" target=\"_blank\" rel=\"noopener sponsored\">Grab it on Amazon</a></p>
  </div>
</div>
{related_section}
"""
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
        cards = "".join(self._product_card(product) for product in products[:60])
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
            description="The newest curated Amazon gift ideas, refreshed automatically for maximum conversion potential.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/latest.html",
            body=body,
            og_image=og_image,
            structured_data=structured_data,
            og_image_alt="Latest gift drops",
            updated_time=self._format_iso8601(latest_update),
        )
        self._write_page(self.output_dir / "latest.html", context)

    def _write_search_page(self, categories: List[Category], products: List[Product]) -> None:
        category_lookup = {category.slug: category.name for category in categories}
        index_entries = []
        for product in products:
            raw_keywords = product.keywords or []
            keywords = [keyword.strip() for keyword in raw_keywords if keyword and keyword.strip()]
            keyword_blob = " ".join(keyword.lower() for keyword in keywords)
            index_entries.append(
                {
                    "title": product.title,
                    "summary": product.summary or "",
                    "url": f"/{self._product_path(product)}",
                    "category": category_lookup.get(product.category_slug, ""),
                    "keywords": keywords,
                    "keywordBlob": keyword_blob,
                }
            )
        dataset = json.dumps(index_entries, ensure_ascii=False).replace("</", "<\\/")
        body = f"""
<section class=\"search-page\">
  <h1>Search the gift radar</h1>
  <p>Filter our conversion-ready product library by keyword, category, or gift recipient.</p>
  <form id=\"search-page-form\" class=\"search-form\" action=\"/search.html\" method=\"get\" role=\"search\">
    <label class=\"sr-only\" for=\"search-query\">Search curated gifts</label>
    <input id=\"search-query\" type=\"search\" name=\"q\" placeholder=\"Type a gift, keyword, or category\" aria-label=\"Search curated gifts\" />
    <button type=\"submit\" aria-label=\"Submit search\">
      <svg aria-hidden=\"true\" width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"11\" cy=\"11\" r=\"7\"></circle><line x1=\"20\" y1=\"20\" x2=\"16.65\" y2=\"16.65\"></line></svg>
    </button>
  </form>
  <div id=\"search-feedback\" class=\"search-empty\" role=\"status\" aria-live=\"polite\" aria-atomic=\"true\">Start typing to reveal the latest gift ideas.</div>
  <ol id=\"search-results\" class=\"search-results\" aria-live=\"polite\"></ol>
</section>
<script>
const PRODUCT_INDEX = {dataset};
const form = document.getElementById('search-page-form');
const input = document.getElementById('search-query');
const feedback = document.getElementById('search-feedback');
const resultsList = document.getElementById('search-results');
function renderResults(query) {
  resultsList.innerHTML = '';
  if (!query) {
    feedback.textContent = 'Start typing to reveal the latest gift ideas.';
    return;
  }
  const normalized = query.toLowerCase();
  const matches = PRODUCT_INDEX.filter((item) => {
    if (item.title.toLowerCase().includes(normalized)) {
      return true;
    }
    if (item.summary.toLowerCase().includes(normalized)) {
      return true;
    }
    if (item.category && item.category.toLowerCase().includes(normalized)) {
      return true;
    }
    if (item.keywordBlob && item.keywordBlob.includes(normalized)) {
      return true;
    }
    if (Array.isArray(item.keywords)) {
      return item.keywords.some((keyword) => {
        return (keyword || '').toLowerCase().includes(normalized);
      });
    }
    return false;
  }).slice(0, 30);
  if (!matches.length) {
    feedback.textContent = 'No matching gifts yet — try a different keyword.';
    return;
  }
  feedback.textContent = `Showing ${matches.length} conversion-ready picks.`;
  const frag = document.createDocumentFragment();
  for (const match of matches) {
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
    if (match.category) {
      const badge = document.createElement('p');
      badge.className = 'badge';
      badge.textContent = match.category;
      li.appendChild(badge);
    }
    frag.appendChild(li);
  }
  resultsList.appendChild(frag);
}
const params = new URLSearchParams(window.location.search);
const initial = (params.get('q') || '').trim();
input.value = initial;
renderResults(initial);
form.addEventListener('submit', (event) => {
  event.preventDefault();
  const value = input.value.trim();
  const url = new URL(window.location.href);
  if (value) {
    url.searchParams.set('q', value);
  } else {
    url.searchParams.delete('q');
  }
  window.history.replaceState(null, '', url.toString());
  renderResults(value);
});
input.addEventListener('input', (event) => {
  renderResults(event.target.value.trim());
});
</script>
"""
        structured_data = [
            {
                "@context": "https://schema.org",
                "@type": "SearchResultsPage",
                "name": f"Search {self.settings.site_name}",
                "description": "Search curated Amazon gift ideas across every category.",
                "url": f"{self.settings.base_url.rstrip('/')}/search.html",
            }
        ]
        context = PageContext(
            title=f"Search gifts — {self.settings.site_name}",
            description="Search curated Amazon gift ideas instantly.",
            canonical_url=f"{self.settings.base_url.rstrip('/')}/search.html",
            body=body,
            structured_data=structured_data,
            noindex=True,
        )
        self._write_page(self.output_dir / "search.html", context)

    def _write_feed(self, products: List[Product]) -> None:
        items = "".join(
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
  <h3>Steal our weekly bestseller intel</h3>
  <p>Subscribe to receive high-performing gift drops, category insights, and seasonal launch reminders.</p>
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
  <h3>Steal our weekly bestseller intel</h3>
  <p>Subscribe to receive high-performing gift drops, category insights, and seasonal launch reminders.</p>
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
        if not price:
            return None, None
        currency_map = {
            "C$": "CAD",
            "A$": "AUD",
            "£": "GBP",
            "€": "EUR",
            "¥": "JPY",
            "$": "USD",
        }
        currency = None
        for symbol, code in currency_map.items():
            if symbol in price:
                currency = code
                break
        numeric_match = re.search(r"(\d+[\d.,]*)", price)
        if not numeric_match:
            return None, currency
        numeric = numeric_match.group(1).replace(",", ".")
        if numeric.count(".") > 1:
            head, *tail = numeric.split(".")
            numeric = head + "." + "".join(tail)
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

    def _product_card(self, product: Product) -> str:
        description = html.escape(product.summary or "Discover why we love this find.")
        image = html.escape(product.image or "")
        category_badge = ""
        category = self._category_lookup.get(product.category_slug)
        if category:
            category_badge = f'<span class="card-badge">{html.escape(category.name)}</span>'
        price_html = (
            f'<span class="card-price">{html.escape(product.price)}</span>'
            if product.price
            else ""
        )
        amazon_cta = ""
        if product.link:
            amazon_cta = (
                f' <a class="cta-secondary" href="{html.escape(product.link)}" target="_blank" rel="noopener sponsored">Shop on Amazon</a>'
            )
        rating_html = ""
        if product.rating and product.total_reviews:
            rating_html = (
                f'<span class="card-rating" aria-label="{product.rating:.1f} out of 5 stars based on {product.total_reviews:,} reviews">'
                '<svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>'
                f'{product.rating:.1f}<span class="card-rating-count">({product.total_reviews:,})</span></span>'
            )
        meta_parts = [part for part in (price_html, rating_html) if part]
        meta_html = (
            f'<div class="card-meta">{"".join(meta_parts)}</div>'
            if meta_parts
            else ""
        )
        return f"""
<article class=\"card\">
  <a class=\"card-media\" href=\"/{self._product_path(product)}\">
    <img src=\"{image}\" alt=\"{html.escape(product.title)}\" loading=\"lazy\" decoding=\"async\" />
    {category_badge}
  </a>
  <div class=\"card-content\">
    <h3><a href=\"/{self._product_path(product)}\">{html.escape(product.title)}</a></h3>
    <p>{description}</p>
    {meta_html}
    <div class=\"card-actions\"><a class=\"button-link\" href=\"/{self._product_path(product)}\">Read the hype</a>{amazon_cta}</div>
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
