# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated Financial News Intelligence System (自動化金融新聞情報系統) — a Python pipeline that ingests financial news from multiple sources, filters by keywords, summarizes via Gemini, and delivers HTML email digests. Also supports YouTube video summarization with STT transcription. Supports two execution modes: local Docker + launchd scheduling, or GitHub Actions cloud scheduling.

## Tech Stack

- **Runtime:** Python 3.11 (Docker or GitHub Actions)
- **AI Engine:** `google-genai` SDK 1.0.0+ — uses `genai.Client()` (NOT the old `google-generativeai`)
- **Scheduling:** GitHub Actions cron (primary) or macOS launchd + Docker (local)
- **Libraries:** feedparser, beautifulsoup4, lxml, requests, Jinja2, PyYAML, python-dateutil, yt-dlp, google-api-python-client, youtube-transcript-api

## Infrastructure Files

| File | Purpose |
|------|---------|
| `.github/workflows/news-digest.yml` | GitHub Actions workflow: cron every 30 min, schedule check in Python, manual trigger |
| `Dockerfile` | Python 3.11-slim image, installs system deps for lxml compilation (gcc, libxml2-dev, libxslt1-dev) |
| `docker-compose.yml` | Mounts `config.yaml` (read-only) + loads `.env` secrets, no restart policy (one-shot) |
| `requirements.txt` | Python packages for news + YouTube pipelines |
| `config_example.yaml` | User settings template: keywords, news sources, YouTube shows, email recipients. Copy to `config.yaml` to use |
| `.env.example` | Secrets template: GEMINI_API_KEY, NEWSAPI_KEY, YOUTUBE_API_KEY, SMTP credentials |
| `.gitignore` | Excludes .env, config.yaml, `__pycache__/`, .venv, .DS_Store, logs/ |

## User Configuration

### `config.yaml` — user-editable settings (gitignored, copied from `config_example.yaml`)

| Section | Description |
|---------|-------------|
| `news.enabled` | Toggle news pipeline on/off (default: true) |
| `keywords` | Keyword → weight mapping (e.g. `台積電: 10`, `TSMC: 10`). Higher weight = higher priority for AI summarization |
| `min_score` | Filter threshold: articles below this total weight are discarded (default: 5) |
| `max_articles` | Max articles sent to Gemini in one prompt (default: 50) |
| `gemini_model` | Model name (default: `gemini-2.5-flash`) |
| `rss_feeds` | RSS source name → URL mapping (MoneyDJ, TechNews, BBC Business/Tech) |
| `scrape_targets` | Web scraping targets with CSS selectors or API URLs (鉅亨網, 工商時報) |
| `newsapi` | NewsAPI.org settings: enabled flag, query string, language, sort order |
| `email.recipients` | List of recipient email addresses |
| `email.subject_prefix` | Email subject prefix (default: `[金融情報]`) |
| `schedule_times` | List of UTC+8 times for news pipeline (e.g. `["08:30", "18:00"]`) |
| `youtube.enabled` | Toggle YouTube pipeline on/off |
| `youtube.stt_model` | Global default STT model for audio transcription |
| `youtube.summary_model` | Global default summarization model |
| `youtube.summary_prompt` | Global default summarization prompt |
| `youtube.email` | Global default email settings (recipients, subject_prefix) |
| `youtube.shows[]` | List of YouTube shows, each with: name, channel_id, max_videos, schedule_times, and optional overrides for stt_model, summary_model, summary_prompt, email |
| `categories` | AI summary categorization labels (半導體, 台股, 國際宏觀經濟) |

### `.env` — secrets (gitignored, never committed)

- `GEMINI_API_KEY` — auto-loaded by google-genai SDK
- `NEWSAPI_KEY` — NewsAPI.org API key
- `YOUTUBE_API_KEY` — YouTube Data API v3 key
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` — Gmail app password recommended
- `EMAIL_FROM` — sender address

Changes to `config.yaml` take effect immediately on next run (no rebuild needed). Changes to `.env` also take effect without rebuild.

## Core Modules

| File | Purpose |
|------|---------|
| `src/main.py` | Pipeline orchestrator: news pipeline + YouTube pipeline. Handles schedule checking and error isolation. Entry point via `python -m src.main` |
| `src/config.py` | Merges `config.yaml` (user settings) + environment variables (secrets) into a unified config interface |
| `src/models.py` | `Article`, `FilteredArticle`, and `Video` dataclasses shared across all modules |
| `src/filter.py` | Time-based filtering (discard >2 days old), keyword-weighted scoring, URL deduplication, ranking by score descending |
| `src/summarizer.py` | Builds Gemini prompt (articles first, instructions at end), calls `genai.Client().models.generate_content()` |
| `src/video_summarizer.py` | Summarizes YouTube video transcripts with configurable Gemini model and prompt |
| `src/transcriber.py` | YouTube transcription: tries subtitles first (youtube-transcript-api), falls back to yt-dlp audio + Gemini STT |
| `src/email_sender.py` | Converts Gemini markdown to inline-CSS HTML, renders Jinja2 templates, sends via SMTP/TLS. Supports both news and video digests |
| `src/fetchers/__init__.py` | Shared `create_session()` with retry logic (3 retries, backoff, handles 429/5xx) |
| `src/fetchers/rss_fetcher.py` | feedparser-based RSS parsing for MoneyDJ, TechNews, BBC. Handles date parsing and HTML stripping |
| `src/fetchers/web_scraper.py` | 鉅亨網 via public JSON API (`api.cnyes.com`), 工商時報 via BeautifulSoup HTML scraping |
| `src/fetchers/newsapi_fetcher.py` | NewsAPI.org `/v2/everything` endpoint, keyword-based international news search |
| `src/fetchers/youtube_fetcher.py` | YouTube Data API v3: fetches latest videos from configured channels |
| `templates/digest.html` | News digest email template with inline CSS |
| `templates/video_digest.html` | Video digest email template with per-video summaries |
| `launchd/com.news.summary.plist` | macOS launchd agent example: triggers `docker compose run --rm` at scheduled times |

## Architecture

```
News Pipeline:
  RSS/Web Sources (parallel) → Time Filter → Keyword Filter → Gemini → HTML Email → SMTP

YouTube Pipeline (per show):
  YouTube API → yt-dlp/Subtitles → Gemini STT → Gemini Summary → HTML Email → SMTP
```

### Key Design Decisions

- **Config split:** `config.yaml` for user-editable settings; `.env` for secrets
- **Two independent pipelines:** News and YouTube run independently; one failing does not affect the other
- **YouTube show isolation:** Each show has its own try/except; one show failing does not affect others
- **Global + override pattern:** YouTube settings (model, prompt, email) have global defaults that each show can override
- **Parallel fetching:** News fetchers run concurrently via `ThreadPoolExecutor`
- **HTTP retry:** Shared `requests.Session` with automatic retry (3 attempts, exponential backoff, 429/5xx)
- **Stale article filtering:** Articles older than 2 days are discarded before keyword scoring
- **Subtitle-first transcription:** Tries free YouTube subtitles before downloading audio for Gemini STT
- **Prompt strategy:** Articles placed first in prompt, instructions at the end (Gemini attention is strongest at context end)
- **Fault tolerance:** Each fetcher/show is wrapped in try/except — one source failure does not crash the pipeline
- **Timezone:** All user-facing timestamps use UTC+8 (Taiwan time) explicitly
- **Schedule in Python:** main.py checks schedule_times directly, workflow just runs every 30 min

## Usage — Local (Docker)

```bash
# 1. Copy templates and fill in your settings
cp config_example.yaml config.yaml
cp .env.example .env

# 2. Edit config.yaml to set keywords, news sources, and recipient email addresses
vi config.yaml

# 3. Edit .env to fill in API keys and SMTP credentials
vi .env

# 4. Build Docker image
docker compose build

# 5. Run the full pipeline (container runs once then exits)
docker compose run --rm news-digest

# 6. (Optional) Set up launchd scheduling
#    - Edit launchd/com.news.summary.plist: replace USERNAME, verify docker path
cp launchd/com.news.summary.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.news.summary.plist

# Check scheduling status
launchctl list | grep com.news.summary

# Force immediate run
launchctl start com.news.summary

# View logs
tail -f /tmp/news_summary.log /tmp/news_summary.err

# Unload schedule
launchctl unload ~/Library/LaunchAgents/com.news.summary.plist
```

## Usage — GitHub Actions (Cloud)

GitHub Actions 可讓 pipeline 在雲端自動執行，不需要本機開機或安裝 Docker。

### Step 1: 設定 GitHub Secrets

到 GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，新增以下 secrets：

| Secret 名稱 | 說明 |
|---|---|
| `CONFIG_YAML` | `config.yaml` 的完整內容（整份貼上） |
| `GEMINI_API_KEY` | Google Gemini API 金鑰 |
| `NEWSAPI_KEY` | NewsAPI.org API 金鑰 |
| `YOUTUBE_API_KEY` | YouTube Data API v3 金鑰（使用 YouTube 功能時需要） |
| `SMTP_HOST` | SMTP 伺服器（如 `smtp.gmail.com`） |
| `SMTP_PORT` | SMTP 埠號（如 `587`） |
| `SMTP_USER` | SMTP 登入帳號 |
| `SMTP_PASSWORD` | SMTP 密碼（Gmail 建議使用應用程式密碼） |
| `EMAIL_FROM` | 寄件人 email 地址 |

### Step 2: 自動排程

Workflow 每 30 分鐘觸發一次，Python 程式自動比對 `config.yaml` 中的排程時間：
- **新聞摘要：** 比對頂層 `schedule_times`
- **YouTube 摘要：** 每個 show 各自比對自己的 `schedule_times`

修改排程時間只需更新 GitHub Secret `CONFIG_YAML` 中的對應欄位即可。

### Step 3: 手動觸發（測試用）

1. 到 GitHub repo → **Actions** 分頁
2. 左側選 **News Digest**
3. 點右邊 **Run workflow** → **Run workflow**
4. 手動觸發時所有 pipeline 和 show 都會執行（不受排程限制）

### 更新設定

- **修改排程時間：** 更新 GitHub Secret `CONFIG_YAML` 中的 `schedule_times`（不需要改程式碼）
- **修改關鍵字、收件人等設定：** 更新 GitHub Secret `CONFIG_YAML` 的內容
- **修改 API 金鑰或 SMTP 密碼：** 更新對應的 GitHub Secret
- 所有 secret 更新後，下次執行自動生效，不需要其他操作

## Specification

Full system spec: `自動化新聞摘要 SPEC 調整.md` (Traditional Chinese, 8 chapters covering architecture, AI engine selection, data sources, processing logic, automation, email templates, extensibility, and implementation roadmap).
