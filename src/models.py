from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    title: str
    link: str
    source: str
    summary: str = ""
    published: datetime | None = None


@dataclass
class FilteredArticle:
    title: str
    link: str
    source: str
    summary: str = ""
    published: datetime | None = None
    score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class Video:
    title: str
    video_id: str
    channel: str
    url: str
    published: datetime | None = None
    transcript: str = ""
