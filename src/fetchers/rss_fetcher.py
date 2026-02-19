"""Fetch and parse RSS feeds using feedparser."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser

from src.models import Article

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _parse_date(entry: dict) -> datetime | None:
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                return dateparser.parse(raw)
            except (ValueError, TypeError):
                pass
    # feedparser's parsed struct_time
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from summary text."""
    from bs4 import BeautifulSoup

    return BeautifulSoup(text, "lxml").get_text(separator=" ", strip=True)


def fetch_rss_feeds(feed_urls: dict[str, str]) -> list[Article]:
    """Fetch articles from multiple RSS feeds.

    Args:
        feed_urls: Mapping of source name to RSS URL.

    Returns:
        List of Article objects.
    """
    articles: list[Article] = []

    for name, url in feed_urls.items():
        try:
            feed = feedparser.parse(url, agent=_USER_AGENT)
            if feed.bozo and not feed.entries:
                logger.warning("RSS feed %s (%s) failed: %s", name, url, feed.bozo_exception)
                continue

            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                summary_raw = entry.get("summary", "") or entry.get("description", "")
                summary = _strip_html(summary_raw)[:500]

                articles.append(Article(
                    title=title,
                    link=link,
                    source=name,
                    summary=summary,
                    published=_parse_date(entry),
                ))

            logger.info("RSS %s: fetched %d entries", name, len(feed.entries))

        except Exception:
            logger.exception("Failed to fetch RSS feed %s (%s)", name, url)

    return articles
