"""Unified configuration: merges config.yaml (user settings) with .env (secrets)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _load_yaml() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


_cfg = _load_yaml()

# --- News pipeline toggle ---
NEWS_ENABLED: bool = _cfg.get("news", {}).get("enabled", True)

# --- Keywords & filtering ---
KEYWORDS: dict[str, int] = _cfg.get("keywords", {})
MIN_SCORE: int = _cfg.get("min_score", 5)
MAX_ARTICLES: int = _cfg.get("max_articles", 50)

# --- Gemini ---
GEMINI_MODEL: str = _cfg.get("gemini_model", "gemini-2.5-flash")
# GEMINI_API_KEY is read from env by google-genai SDK automatically

# --- Data sources ---
RSS_FEEDS: dict[str, str] = _cfg.get("rss_feeds", {})
SCRAPE_TARGETS: list[dict] = _cfg.get("scrape_targets", [])
NEWSAPI_CONFIG: dict = _cfg.get("newsapi", {})
NEWSAPI_KEY: str = os.environ.get("NEWSAPI_KEY", "")

# --- Email ---
SMTP_HOST: str = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER: str = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM: str = os.environ.get("EMAIL_FROM", SMTP_USER)
EMAIL_RECIPIENTS: list[str] = _cfg.get("email", {}).get("recipients", [])
EMAIL_SUBJECT_PREFIX: str = _cfg.get("email", {}).get("subject_prefix", "[金融情報]")

# --- YouTube ---
YOUTUBE_CONFIG: dict = _cfg.get("youtube", {})
YOUTUBE_API_KEY: str = os.environ.get("YOUTUBE_API_KEY", "")

# --- Schedule ---
SCHEDULE_TIMES: list[str] = _cfg.get("schedule_times", [])

# --- AI categories ---
CATEGORIES: list[str] = _cfg.get("categories", [
    "半導體與伺服器供應鏈",
    "台股大盤與上市櫃公司動態",
    "國際宏觀經濟（FED、通膨、關稅政策）",
])
