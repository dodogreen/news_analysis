"""Summarize YouTube video transcripts via Gemini."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from src.models import Video

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = (
    "你是一位資深財經分析師。請分析以下影片逐字稿，產出一份精簡的影片摘要。\n\n"
    "要求：\n"
    "- 提煉 3-5 個核心觀點\n"
    "- 標註提及的重要股票代號或公司名稱\n"
    "- 指出對投資決策有影響的關鍵資訊\n"
    "- 使用繁體中文\n"
    "- 使用 markdown 格式\n"
)


def _build_prompt(video: Video, custom_prompt: str) -> str:
    """Build summarization prompt for a single video."""
    lines = [
        f"影片標題：{video.title}",
        f"頻道：{video.channel}",
        f"連結：{video.url}",
        "",
        "--- 逐字稿開始 ---",
        video.transcript,
        "--- 逐字稿結束 ---",
        "",
        custom_prompt,
    ]
    return "\n".join(lines)


def summarize_videos(
    videos: list[Video],
    summary_model: str,
    summary_prompt: str | None = None,
    show_name: str = "",
) -> list[tuple[Video, str]]:
    """Summarize each video's transcript with Gemini.

    Args:
        videos: List of Video objects with transcripts filled in.
        summary_model: Gemini model name for summarization.
        summary_prompt: Custom prompt, or None to use default.
        show_name: Show name for logging.

    Returns:
        List of (video, summary_text) tuples.
    """
    prompt_template = summary_prompt or _DEFAULT_PROMPT
    client = genai.Client()
    results: list[tuple[Video, str]] = []

    for video in videos:
        if not video.transcript:
            logger.warning("Skipping %s — no transcript", video.title)
            continue

        prompt = _build_prompt(video, prompt_template)
        logger.info(
            "Summarizing [%s] %s (%d chars transcript)",
            show_name, video.title, len(video.transcript),
        )

        try:
            response = client.models.generate_content(
                model=summary_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )
            results.append((video, response.text))
            logger.info("Summary for %s: %d chars", video.title, len(response.text))
        except Exception:
            logger.exception("Failed to summarize %s", video.title)
            results.append((video, "⚠️ 摘要生成失敗"))

    return results
