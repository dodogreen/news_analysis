"""Shared utilities for fetcher modules."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_RETRY = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])


def create_session() -> requests.Session:
    """Create a requests session with retry and default headers."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": _USER_AGENT,
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    s.mount("https://", HTTPAdapter(max_retries=_RETRY))
    s.mount("http://", HTTPAdapter(max_retries=_RETRY))
    return s
