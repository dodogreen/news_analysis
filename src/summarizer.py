"""Gemini 1.5 Flash summarization via google-genai SDK."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from src import config
from src.models import FilteredArticle

logger = logging.getLogger(__name__)


def _build_prompt(articles: list[FilteredArticle], categories: list[str]) -> str:
    """Build the full prompt: articles first, instructions at the end."""

    # --- Article data block ---
    lines = ["--- 新聞資料開始 ---", ""]
    for i, art in enumerate(articles, 1):
        lines.append(f"[{i}] 標題: {art.title}")
        lines.append(f"    來源: {art.source}")
        if art.summary:
            lines.append(f"    摘要: {art.summary}")
        lines.append(f"    連結: {art.link}")
        lines.append("")
    lines.append("--- 新聞資料結束 ---")
    lines.append("")

    # --- Instructions at the end (where Gemini attention is strongest) ---
    cat_list = "\n".join(f"{i}. {c}" for i, c in enumerate(categories, 1))
    lines.append(
        "你是一位資深科技產業分析師。請分析以上新聞資料，"
        "並產出一份《每日金融與科技決策簡報》。\n"
    )
    lines.append(f"請將新聞歸類為以下分類：\n{cat_list}\n")
    lines.append(
        "針對每個分類：\n"
        "- 提煉 3-5 個核心要點\n"
        "- 指出不同報導之間的矛盾點或潛在趨勢聯動\n"
        "- 為每個分類標注重要程度：🔴 高 / 🟡 中 / 🟢 低\n"
        "- 在要點中標註相關股票代號（如 2330.TW）\n"
        "\n"
        "輸出格式要求：\n"
        "- 使用繁體中文\n"
        "- 每個分類用 ## 標題開頭\n"
        "- 在分類標題旁標注重要程度 emoji\n"
        "- 最後附上一段「綜合研判」總結當日整體趨勢\n"
    )

    return "\n".join(lines)


def summarize_articles(articles: list[FilteredArticle]) -> str:
    """Send filtered articles to Gemini for summarization.

    Args:
        articles: Ranked and filtered articles.

    Returns:
        AI-generated summary text (markdown format).
    """
    if not articles:
        return "今日無符合條件的重大新聞。"

    prompt = _build_prompt(articles, config.CATEGORIES)
    logger.info("Prompt length: %d chars, %d articles", len(prompt), len(articles))

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
            ),
        )
        summary = response.text
        logger.info("Gemini response: %d chars", len(summary))
        return summary

    except Exception:
        logger.exception("Gemini summarization failed")
        return "⚠️ AI 摘要生成失敗，請查看下方原始新聞連結。"
