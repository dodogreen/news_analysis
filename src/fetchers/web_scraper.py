"""Scrape news from sites without usable RSS feeds (Anue, CTEE, etc.)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.models import Article

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Anue (鉅亨網) — uses their public JSON API
# ---------------------------------------------------------------------------

def _fetch_anue(target: dict) -> list[Article]:
    api_url = target.get("api_url", "")
    if not api_url:
        logger.warning("Anue: no api_url configured")
        return []

    params = {"limit": 30}
    resp = requests.get(api_url, headers=_HEADERS, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    articles: list[Article] = []
    items = data.get("items", {}).get("data", [])
    for item in items:
        title = item.get("title", "").strip()
        news_id = item.get("newsId", "")
        link = f"https://news.cnyes.com/news/id/{news_id}" if news_id else ""
        summary = item.get("summary", "")[:500]
        pub_ts = item.get("publishAt")
        published = datetime.fromtimestamp(pub_ts, tz=timezone.utc) if pub_ts else None

        if title and link:
            articles.append(Article(
                title=title,
                link=link,
                source="鉅亨網",
                summary=summary,
                published=published,
            ))

    logger.info("Anue API: fetched %d articles", len(articles))
    return articles


# ---------------------------------------------------------------------------
# Generic HTML scraper (CTEE, etc.)
# ---------------------------------------------------------------------------

def _scrape_html(target: dict) -> list[Article]:
    name = target.get("name", "unknown")
    url = target.get("url", "")
    title_sel = target.get("title_selector", "")
    link_sel = target.get("link_selector", "")

    if not url or not title_sel:
        logger.warning("Scrape target %s missing url or title_selector", name)
        return []

    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding  # handle Big5/UTF-8 correctly

    soup = BeautifulSoup(resp.text, "lxml")
    title_elems = soup.select(title_sel)

    articles: list[Article] = []
    for elem in title_elems[:30]:
        title = elem.get_text(strip=True)
        # If link_selector is same as title_selector, get href from same element
        href = elem.get("href", "")
        if not href and link_sel and link_sel != title_sel:
            link_elem = elem.find_parent().select_one(link_sel)
            href = link_elem.get("href", "") if link_elem else ""

        if not title or not href:
            continue

        link = urljoin(url, href)
        articles.append(Article(
            title=title,
            link=link,
            source=name,
            summary="",
            published=None,
        ))

    logger.info("Scrape %s: fetched %d articles", name, len(articles))
    return articles


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_news_sites(targets: list[dict]) -> list[Article]:
    """Scrape articles from all configured web targets.

    Args:
        targets: List of target config dicts from config.yaml.

    Returns:
        List of Article objects.
    """
    all_articles: list[Article] = []

    for target in targets:
        try:
            if target.get("use_api"):
                all_articles.extend(_fetch_anue(target))
            else:
                all_articles.extend(_scrape_html(target))
        except Exception:
            logger.exception("Failed to scrape %s", target.get("name", "unknown"))

        time.sleep(1)  # polite delay between targets

    return all_articles
