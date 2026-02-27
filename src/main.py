"""Main pipeline orchestrator: fetch → filter → summarize → email."""

from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

from src import config
from src.email_sender import render_email, send_email
from src.fetchers.newsapi_fetcher import fetch_newsapi_articles
from src.fetchers.rss_fetcher import fetch_rss_feeds
from src.fetchers.web_scraper import scrape_news_sites
from src.filter import filter_and_rank
from src.summarizer import summarize_articles


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== Pipeline started ===")

    try:
        # Step 1: Fetch from all sources (in parallel)
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

        # Step 2: Filter and rank
        filtered = filter_and_rank(
            articles,
            config.KEYWORDS,
            config.MIN_SCORE,
            config.MAX_ARTICLES,
        )
        logger.info("After filter: %d articles", len(filtered))

        # Step 3: Summarize with Gemini
        if filtered:
            try:
                summary = summarize_articles(filtered)
            except Exception:
                logger.exception("Gemini failed, sending digest with links only")
                summary = "⚠️ AI 摘要生成失敗，請查看下方原始新聞連結。"
        else:
            summary = "今日無符合過濾條件的重大新聞。系統持續監控中。"
            logger.warning("No articles passed filter")

        # Step 4: Render and send email
        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
        html = render_email(summary, filtered, now)
        subject = f"{config.EMAIL_SUBJECT_PREFIX} {now[:10]} 每日摘要"
        send_email(html, subject)

        logger.info("=== Pipeline completed successfully ===")

    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
