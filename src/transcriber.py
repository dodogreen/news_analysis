"""Transcribe YouTube videos: subtitle fallback → yt-dlp + Gemini STT."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

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
        logger.info("No subtitle available for %s, will use STT", video_id)
        return None


def _download_audio(video_id: str, output_dir: str) -> Path:
    """Download audio from YouTube video using yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = Path(output_dir) / f"{video_id}.mp3"

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "--output", str(output_path.with_suffix(".%(ext)s")),
        "--no-playlist",
        "--quiet",
        url,
    ]
    subprocess.run(cmd, check=True, timeout=300)

    if not output_path.exists():
        raise FileNotFoundError(f"Audio file not found: {output_path}")

    logger.info("Downloaded audio for %s (%d bytes)", video_id, output_path.stat().st_size)
    return output_path


def _gemini_stt(audio_path: Path, stt_model: str) -> str:
    """Transcribe audio using Gemini's audio understanding capability."""
    client = genai.Client()

    uploaded = client.files.upload(file=audio_path)
    logger.info("Uploaded audio to Gemini: %s", uploaded.name)

    response = client.models.generate_content(
        model=stt_model,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded.uri,
                        mime_type="audio/mpeg",
                    ),
                    types.Part(
                        text="請將這段音訊完整轉錄為文字。只輸出轉錄文字，不需要加時間戳記或說話者標記。",
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
    logger.info("Gemini STT completed: %d chars", len(text))
    return text


def transcribe_video(video_id: str, stt_model: str) -> str:
    """Get transcript for a video: subtitle first, then yt-dlp + Gemini STT.

    Args:
        video_id: YouTube video ID.
        stt_model: Gemini model name for STT (e.g. "gemini-2.5-flash").

    Returns:
        Transcript text.
    """
    # Try subtitles first
    subtitle = _get_subtitle(video_id)
    if subtitle:
        return subtitle

    # Fallback to audio download + Gemini STT
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = _download_audio(video_id, tmpdir)
        return _gemini_stt(audio_path, stt_model)
