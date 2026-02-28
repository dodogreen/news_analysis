"""Fetch latest videos from YouTube channels via YouTube Data API v3."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dateutil import parser as dateparser
from googleapiclient.discovery import build

from src.models import Video

logger = logging.getLogger(__name__)


def fetch_channel_videos(
    channel_id: str,
    channel_name: str,
    api_key: str,
    max_videos: int = 3,
) -> list[Video]:
    """Fetch the latest videos from a YouTube channel.

    Args:
        channel_id: YouTube channel ID (starts with UC...).
        channel_name: Display name for logging.
        api_key: YouTube Data API v3 key.
        max_videos: Maximum number of videos to return.

    Returns:
        List of Video objects with metadata (no transcript yet).
    """
    if not api_key:
        logger.warning("YOUTUBE_API_KEY not set, skipping YouTube fetch")
        return []

    youtube = build("youtube", "v3", developerKey=api_key)

    # Only fetch videos published today (UTC+8)
    tw_tz = timezone(timedelta(hours=8))
    today_start = datetime.now(tw_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    published_after = today_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    response = (
        youtube.search()
        .list(
            channelId=channel_id,
            part="snippet",
            order="date",
            type="video",
            maxResults=max_videos,
            publishedAfter=published_after,
        )
        .execute()
    )

    videos: list[Video] = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        title = snippet.get("title", "").strip()

        published = None
        if snippet.get("publishedAt"):
            try:
                published = dateparser.parse(snippet["publishedAt"])
            except (ValueError, TypeError):
                pass

        videos.append(Video(
            title=title,
            video_id=video_id,
            channel=channel_name,
            url=f"https://www.youtube.com/watch?v={video_id}",
            published=published,
        ))

    videos = videos[:max_videos]
    logger.info("YouTube %s: fetched %d videos (today only, after %s)", channel_name, len(videos), published_after)
    return videos
