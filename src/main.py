"""Main pipeline orchestrator: news + YouTube → summarize → email."""

from __future__ import annotations

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

from src import config
from src.email_sender import render_email, render_video_email, send_email, send_email_to
from src.fetchers.newsapi_fetcher import fetch_newsapi_articles
from src.fetchers.rss_fetcher import fetch_rss_feeds
from src.fetchers.web_scraper import scrape_news_sites
from src.fetchers.youtube_fetcher import fetch_channel_videos
from src.filter import filter_and_rank
from src.summarizer import summarize_articles
from src.transcriber import transcribe_video
from src.video_summarizer import summarize_videos

_TW_TZ = timezone(timedelta(hours=8))


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )


def _is_manual_trigger() -> bool:
    """Check if running via GitHub Actions workflow_dispatch."""
    return os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"


def _current_time_hhmm() -> str:
    """Return current UTC+8 time as HH:MM string."""
    return datetime.now(_TW_TZ).strftime("%H:%M")


def _should_run_schedule(schedule_times: list[str]) -> bool:
    """Check if current time matches any scheduled time."""
    if _is_manual_trigger():
        return True
    if not schedule_times:
        return True
    return _current_time_hhmm() in schedule_times


# ---------------------------------------------------------------------------
# News pipeline
# ---------------------------------------------------------------------------

def _news_pipeline(now: str, logger: logging.Logger) -> None:
    """Run the news digest pipeline: fetch → filter → summarize → email."""
    if not config.NEWS_ENABLED:
        logger.info("News pipeline disabled, skipping")
        return

    if not _should_run_schedule(config.SCHEDULE_TIMES):
        logger.info("News: not a scheduled time, skipping")
        return

    logger.info("=== News pipeline started ===")

    # Fetch from all sources (in parallel)
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

    # Summarize with Gemini
    if filtered:
        try:
            summary = summarize_articles(filtered)
        except Exception:
            logger.exception("Gemini failed, sending digest with links only")
            summary = "⚠️ AI 摘要生成失敗，請查看下方原始新聞連結。"
    else:
        summary = "今日無符合過濾條件的重大新聞。系統持續監控中。"
        logger.warning("No articles passed filter")

    # Render and send email
    html = render_email(summary, filtered, now)
    subject = f"{config.EMAIL_SUBJECT_PREFIX} {now[:10]} 每日摘要"
    send_email(html, subject)

    logger.info("=== News pipeline completed ===")


# ---------------------------------------------------------------------------
# YouTube pipeline
# ---------------------------------------------------------------------------

def _get_show_setting(show: dict, key: str, yt_config: dict, default=None):
    """Get a setting from show config, falling back to global youtube config."""
    return show.get(key, yt_config.get(key, default))


def _youtube_pipeline(now: str, logger: logging.Logger) -> None:
    """Run the YouTube video digest pipeline for each configured show."""
    yt_config = config.YOUTUBE_CONFIG
    if not yt_config.get("enabled", False):
        logger.info("YouTube pipeline disabled, skipping")
        return

    shows = yt_config.get("shows", [])
    if not shows:
        logger.info("No YouTube shows configured")
        return

    global_email = yt_config.get("email", {})

    for show in shows:
        show_name = show.get("name", "Unknown")
        schedule = show.get("schedule_times", [])

        if not _should_run_schedule(schedule):
            logger.info("YouTube [%s]: not a scheduled time, skipping", show_name)
            continue

        try:
            _process_show(show, show_name, yt_config, global_email, now, logger)
        except Exception:
            logger.exception("YouTube show [%s] failed", show_name)


def _process_show(
    show: dict,
    show_name: str,
    yt_config: dict,
    global_email: dict,
    now: str,
    logger: logging.Logger,
) -> None:
    """Process a single YouTube show: fetch → transcribe → summarize → email."""
    channel_id = show.get("channel_id", "")
    if not channel_id:
        logger.warning("YouTube [%s]: no channel_id configured", show_name)
        return

    max_videos = show.get("max_videos", 3)
    stt_model = _get_show_setting(show, "stt_model", yt_config, "gemini-2.5-flash")
    summary_model = _get_show_setting(show, "summary_model", yt_config, "gemini-2.5-flash")
    summary_prompt = _get_show_setting(show, "summary_prompt", yt_config)

    # Resolve email settings (show overrides global)
    show_email = show.get("email", {})
    recipients = show_email.get("recipients", global_email.get("recipients", []))
    subject_prefix = show_email.get("subject_prefix", global_email.get("subject_prefix", "[影片摘要]"))

    logger.info("=== YouTube [%s] started ===", show_name)

    # Fetch videos
    videos = fetch_channel_videos(
        channel_id, show_name, config.YOUTUBE_API_KEY, max_videos,
    )
    if not videos:
        logger.info("YouTube [%s]: no videos found", show_name)
        return

    # Transcribe each video
    for video in videos:
        try:
            video.transcript = transcribe_video(video.video_id, stt_model)
        except Exception:
            logger.exception("Failed to transcribe [%s] %s", show_name, video.title)

    # Filter out videos with no transcript
    videos_with_transcript = [v for v in videos if v.transcript]
    if not videos_with_transcript:
        logger.warning("YouTube [%s]: no videos with transcript", show_name)
        return

    # Summarize
    video_summaries = summarize_videos(
        videos_with_transcript, summary_model, summary_prompt, show_name,
    )

    # Render and send email
    html = render_video_email(video_summaries, show_name, summary_model, now)
    subject = f"{subject_prefix} {now[:10]} {show_name}"
    send_email_to(html, subject, recipients)

    logger.info("=== YouTube [%s] completed ===", show_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)
    now = datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")
    logger.info("=== Pipeline started at %s ===", now)

    try:
        _news_pipeline(now, logger)
    except Exception:
        logger.exception("News pipeline failed")

    try:
        _youtube_pipeline(now, logger)
    except Exception:
        logger.exception("YouTube pipeline failed")

    logger.info("=== All pipelines completed ===")


if __name__ == "__main__":
    main()
