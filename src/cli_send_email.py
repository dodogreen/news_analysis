"""CLI: send email digest from a markdown summary file.

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
    """Deserialize FilteredArticle list from a JSON file produced by cli_fetch."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    articles = []
    for d in data:
        pub = None
        if d.get("published"):
            try:
                pub = datetime.fromisoformat(d["published"])
            except (ValueError, TypeError):
                pass
        articles.append(FilteredArticle(
            title=d["title"],
            link=d["link"],
            source=d["source"],
            summary=d.get("summary", ""),
            published=pub,
            score=d.get("score", 0.0),
            matched_keywords=d.get("matched_keywords", []),
        ))
    return articles


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email digest from a markdown file")
    parser.add_argument(
        "--type", required=True, choices=["news"],
        help="Digest type (currently only 'news' is supported)",
    )
    parser.add_argument("--file", required=True, help="Markdown summary file path")
    parser.add_argument(
        "--articles", default=None,
        help="Articles JSON file (produced by cli_fetch) for the links section",
    )
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger(__name__)

    # Read summary markdown
    with open(args.file, encoding="utf-8") as f:
        summary = f.read()

    # Load articles for the links section (optional)
    articles: list[FilteredArticle] = []
    if args.articles:
        articles = _load_articles(args.articles)
        logger.info("Loaded %d articles from %s", len(articles), args.articles)

    now = datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")

    if args.type == "news":
        html = render_email(summary, articles, now)
        subject = f"{config.EMAIL_SUBJECT_PREFIX} {now[:10]} 每日摘要"
        send_email(html, subject)
        logger.info("News digest sent (subject: %s)", subject)
        print(f"Email sent → {', '.join(config.EMAIL_RECIPIENTS)}")


if __name__ == "__main__":
    main()
