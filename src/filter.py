"""Keyword-weighted filtering and deduplication."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

from src.models import Article, FilteredArticle

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Strip query params and trailing slash for deduplication."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def filter_and_rank(
    articles: list[Article],
    keywords: dict[str, int],
    threshold: int,
    max_articles: int,
) -> list[FilteredArticle]:
    """Filter articles by keyword score and return ranked results.

    Args:
        articles: Raw articles from all fetchers.
        keywords: Keyword-to-weight mapping from config.
        threshold: Minimum score to pass filter.
        max_articles: Maximum number of articles to return.

    Returns:
        Filtered and ranked articles, highest score first.
    """
    # Discard articles older than 2 days (keep those without a publish date)
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    fresh: list[Article] = []
    stale_count = 0
    for art in articles:
        if art.published and art.published.tzinfo and art.published < cutoff:
            stale_count += 1
        else:
            fresh.append(art)
    if stale_count:
        logger.info("Dropped %d stale articles (older than 2 days)", stale_count)

    # Deduplicate by normalized URL
    seen_urls: set[str] = set()
    unique: list[Article] = []
    for art in fresh:
        norm = _normalize_url(art.link)
        if norm not in seen_urls:
            seen_urls.add(norm)
            unique.append(art)

    logger.info("Dedup: %d -> %d unique articles", len(fresh), len(unique))

    # Score each article
    results: list[FilteredArticle] = []
    for art in unique:
        text = f"{art.title} {art.summary}".lower()
        matched: list[str] = []
        score = 0.0

        for kw, weight in keywords.items():
            if kw.lower() in text:
                matched.append(kw)
                score += weight

        if score >= threshold:
            results.append(FilteredArticle(
                title=art.title,
                link=art.link,
                source=art.source,
                summary=art.summary,
                published=art.published,
                score=score,
                matched_keywords=matched,
            ))

    # Sort by score descending, then truncate
    results.sort(key=lambda a: a.score, reverse=True)
    results = results[:max_articles]

    logger.info("Filter: %d articles passed (threshold=%d)", len(results), threshold)
    return results
