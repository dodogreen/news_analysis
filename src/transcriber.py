"""Transcribe YouTube videos: subtitle fallback → Gemini YouTube URL."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def _get_subtitle(video_id: str) -> str | None:
    """Try to get subtitles via youtube-transcript-api (free, fast)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=["zh-TW", "zh", "zh-Hant", "en"])
        text = " ".join(snippet.text for snippet in transcript.snippets)
        logger.info("Subtitle found for %s (%d chars)", video_id, len(text))
        return text
    except Exception:
        logger.info("No subtitle available for %s, will use Gemini URL", video_id)
        return None


def _gemini_youtube_url(video_id: str, stt_model: str) -> str:
    """Transcribe video by passing the YouTube URL directly to Gemini.

    Gemini can process YouTube videos natively — no download needed,
    and no bot-detection issues since we never hit YouTube from CI.
    """
    client = genai.Client()
    url = f"https://www.youtube.com/watch?v={video_id}"

    response = client.models.generate_content(
        model=stt_model,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_uri(
                        file_uri=url,
                        mime_type="video/mp4",
                    ),
                    types.Part(
                        text=(
                            "請將這段影片的語音完整轉錄為文字。"
                            "只輸出轉錄文字，不需要加時間戳記或說話者標記。"
                        ),
                    ),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=16384,
        ),
    )

    text = response.text
    logger.info("Gemini YouTube URL transcription completed: %d chars", len(text))
    return text


def transcribe_video(video_id: str, stt_model: str) -> str:
    """Get transcript for a video: subtitle first, then Gemini YouTube URL.

    Args:
        video_id: YouTube video ID.
        stt_model: Gemini model name for transcription (e.g. "gemini-2.5-flash").

    Returns:
        Transcript text.
    """
    subtitle = _get_subtitle(video_id)
    if subtitle:
        return subtitle

    return _gemini_youtube_url(video_id, stt_model)
