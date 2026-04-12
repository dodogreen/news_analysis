"""CLI: fetch articles from all sources, filter/rank, write to JSON.

Usage:
    python -m src.cli_fetch --output /tmp/articles.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from src import config
from src.fetchers.newsapi_fetcher import fetch_newsapi_articles
from src.fetchers.rss_fetcher import fetch_rss_feeds
from src.fetchers.web_scraper import scrape_news_sites
from src.filter import filter_and_rank
from src.models import FilteredArticle


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )


def _article_to_dict(article: FilteredArticle) -> dict:
    return {
        "title": article.title,
        "link": article.link,
        "source": article.source,
        "summary": article.summary,
        "published": article.published.isoformat() if article.published else None,
        "score": article.score,
        "matched_keywords": article.matched_keywords,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and filter news articles to JSON")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger(__name__)

    # Fetch from all sources in parallel
    articles = []
    fetchers = [
        ("RSS", lambda: fetch_rss_feeds(config.RSS_FEEDS)),
        ("Scraper", lambda: scrape_news_sites(config.SCRAPE_TARGETS)),
        ("NewsAPI", lambda: fetch_newsapi_articles(config.NEWSAPI_CONFIG, config.NEWSAPI_KEY)),
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn): name for name, fn in fetchers}
        for future in as_completed(futures):
            name = futures[future]
            try:
                articles += future.result()
            except Exception:
                logger.exception("Fetcher %s failed", name)

    logger.info("Total fetched: %d articles", len(articles))

    # Filter and rank
    filtered = filter_and_rank(
        articles, config.KEYWORDS, config.MIN_SCORE, config.MAX_ARTICLES,
    )
    logger.info("After filter: %d articles", len(filtered))

    # Write to JSON
    data = [_article_to_dict(a) for a in filtered]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("Written %d articles to %s", len(data), args.output)


if __name__ == "__main__":
    main()
