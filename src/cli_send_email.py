"""CLI for rendering and sending email digest from a summary file and articles JSON.

Usage:
    python -m src.cli_send_email --type news --file /tmp/summary.md --articles /tmp/articles.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta

from src import config
from src.email_sender import render_email, send_email
from src.models import FilteredArticle

_TW_TZ = timezone(timedelta(hours=8))


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )


def _load_articles(path: str) -> list[FilteredArticle]:
    """Deserialize articles from a JSON file produced by cli_fetch."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    articles = []
    for item in data:
        published = None
        if item.get("published"):
            try:
                published = datetime.fromisoformat(item["published"])
            except (ValueError, TypeError):
                pass
        articles.append(FilteredArticle(
            title=item.get("title", ""),
            link=item.get("link", ""),
            source=item.get("source", ""),
            summary=item.get("summary", ""),
            published=published,
            score=float(item.get("score", 0.0)),
            matched_keywords=item.get("matched_keywords", []),
        ))
    return articles


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Send email digest from summary + articles")
    parser.add_argument("--type", choices=["news"], required=True, help="Digest type")
    parser.add_argument("--file", required=True, help="Summary markdown file path")
    parser.add_argument("--articles", required=True, help="Articles JSON file path (from cli_fetch)")
    args = parser.parse_args()

    # Read summary markdown
    with open(args.file, encoding="utf-8") as f:
        summary = f.read()

    # Load articles
    articles = _load_articles(args.articles)
    logger.info("Loaded %d articles from %s", len(articles), args.articles)

    now = datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")

    if args.type == "news":
        html = render_email(summary, articles, now)
        subject = f"{config.EMAIL_SUBJECT_PREFIX} {now[:10]} 每日摘要"
        send_email(html, subject)
        logger.info("News digest email sent (subject: %s)", subject)


if __name__ == "__main__":
    main()
