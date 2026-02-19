"""Fetch articles from NewsAPI.org REST API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests
from dateutil import parser as dateparser

from src.models import Article

logger = logging.getLogger(__name__)

_BASE_URL = "https://newsapi.org/v2/everything"
_TIMEOUT = 15


def fetch_newsapi_articles(config: dict, api_key: str) -> list[Article]:
    """Fetch articles from NewsAPI.org.

    Args:
        config: NewsAPI section from config.yaml (query, language, sort_by).
        api_key: NewsAPI API key from environment.

    Returns:
        List of Article objects.
    """
    if not config.get("enabled", False):
        logger.info("NewsAPI is disabled in config")
        return []

    if not api_key:
        logger.warning("NEWSAPI_KEY not set, skipping NewsAPI")
        return []

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    params = {
        "q": config.get("query", "TSMC OR semiconductor"),
        "language": config.get("language", "en"),
        "sortBy": config.get("sort_by", "publishedAt"),
        "from": yesterday,
        "pageSize": 50,
        "apiKey": api_key,
    }

    try:
        resp = requests.get(_BASE_URL, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            logger.error("NewsAPI error: %s", data.get("message", "unknown"))
            return []

        articles: list[Article] = []
        for item in data.get("articles", []):
            title = (item.get("title") or "").strip()
            link = (item.get("url") or "").strip()
            if not title or not link or title == "[Removed]":
                continue

            summary = (item.get("description") or "")[:500]
            source_name = item.get("source", {}).get("name", "NewsAPI")
            published = None
            if item.get("publishedAt"):
                try:
                    published = dateparser.parse(item["publishedAt"])
                except (ValueError, TypeError):
                    pass

            articles.append(Article(
                title=title,
                link=link,
                source=source_name,
                summary=summary,
                published=published,
            ))

        logger.info("NewsAPI: fetched %d articles", len(articles))
        return articles

    except Exception:
        logger.exception("Failed to fetch from NewsAPI")
        return []
