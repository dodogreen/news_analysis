"""CLI: read summary markdown + articles JSON, render and send email digest.

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


def _dict_to_article(d: dict) -> FilteredArticle:
    published = None
    if d.get("published"):
        try:
            published = datetime.fromisoformat(d["published"])
        except (ValueError, TypeError):
            pass
    return FilteredArticle(
        title=d.get("title", ""),
        link=d.get("link", ""),
        source=d.get("source", ""),
        summary=d.get("summary", ""),
        published=published,
        score=d.get("score", 0.0),
        matched_keywords=d.get("matched_keywords", []),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email digest from summary file")
    parser.add_argument("--type", required=True, choices=["news"], help="Pipeline type")
    parser.add_argument("--file", required=True, help="Markdown summary file path")
    parser.add_argument("--articles", required=True, help="Articles JSON file path")
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger(__name__)

    # Read summary markdown
    with open(args.file, encoding="utf-8") as f:
        summary = f.read()

    # Read articles JSON and deserialize
    with open(args.articles, encoding="utf-8") as f:
        articles_data = json.load(f)
    articles = [_dict_to_article(d) for d in articles_data]

    now = datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")

    if args.type == "news":
        html = render_email(summary, articles, now)
        subject = f"{config.EMAIL_SUBJECT_PREFIX} {now[:10]} 每日摘要"
        send_email(html, subject)
        logger.info("News digest email sent to %s", ", ".join(config.EMAIL_RECIPIENTS))


if __name__ == "__main__":
    main()
