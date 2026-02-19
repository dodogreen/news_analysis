# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated Financial News Intelligence System (自動化金融新聞情報系統) — a Python pipeline that ingests financial news from multiple sources, filters by keywords, summarizes via Gemini 1.5 Flash, and delivers HTML email digests. Runs in Docker to avoid polluting the local macOS environment. Host launchd triggers `docker compose run --rm` on schedule.

## Tech Stack

- **Runtime:** Docker (python:3.11-slim), no local Python deps needed
- **AI Engine:** `google-genai` SDK 1.0.0+ — uses `genai.Client()` (NOT the old `google-generativeai`)
- **Scheduling:** macOS launchd triggers Docker container (sleep-aware, auto-resumes)
- **Libraries:** feedparser, beautifulsoup4, lxml, requests, Jinja2, PyYAML, python-dateutil

## Infrastructure Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.11-slim image, installs system deps for lxml compilation (gcc, libxml2-dev, libxslt1-dev) |
| `docker-compose.yml` | Mounts `config.yaml` (read-only) + loads `.env` secrets, no restart policy (one-shot) |
| `requirements.txt` | 8 Python packages: google-genai, feedparser, beautifulsoup4, lxml, requests, Jinja2, PyYAML, python-dateutil |
| `.env.example` | Secrets template: GEMINI_API_KEY, NEWSAPI_KEY, SMTP host/port/user/password, EMAIL_FROM |
| `.gitignore` | Excludes .env, `__pycache__/`, .venv, .DS_Store, logs/ |

## User Configuration

### `config.yaml` — user-editable settings, mounted into container via docker-compose volume

| Section | Description |
|---------|-------------|
| `keywords` | Keyword → weight mapping (e.g. `台積電: 10`, `TSMC: 10`). Higher weight = higher priority for AI summarization |
| `min_score` | Filter threshold: articles below this total weight are discarded (default: 5) |
| `max_articles` | Max articles sent to Gemini in one prompt (default: 50) |
| `gemini_model` | Model name (default: `gemini-1.5-flash`) |
| `rss_feeds` | RSS source name → URL mapping (MoneyDJ, TechNews, BBC Business/Tech) |
| `scrape_targets` | Web scraping targets with CSS selectors or API URLs (鉅亨網, 工商時報) |
| `newsapi` | NewsAPI.org settings: enabled flag, query string, language, sort order |
| `email.recipients` | List of recipient email addresses |
| `email.subject_prefix` | Email subject prefix (default: `[金融情報]`) |
| `categories` | AI summary categorization labels (半導體, 台股, 國際宏觀經濟) |

### `.env` — secrets (gitignored, never committed)

- `GEMINI_API_KEY` — auto-loaded by google-genai SDK
- `NEWSAPI_KEY` — NewsAPI.org API key
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` — Gmail app password recommended
- `EMAIL_FROM` — sender address

Changes to `config.yaml` take effect immediately on next run (no rebuild needed). Changes to `.env` also take effect without rebuild.

## Core Modules

| File | Purpose |
|------|---------|
| `src/main.py` | Pipeline orchestrator: fetch → filter → summarize → email. Entry point via `python -m src.main` |
| `src/config.py` | Merges `config.yaml` (user settings) + environment variables (secrets) into a unified config interface |
| `src/models.py` | `Article` and `FilteredArticle` dataclasses shared across all modules |
| `src/filter.py` | Keyword-weighted scoring, URL deduplication (normalized), ranking by score descending |
| `src/summarizer.py` | Builds Gemini prompt (articles first, instructions at end), calls `genai.Client().models.generate_content()` |
| `src/email_sender.py` | Converts Gemini markdown output to inline-CSS HTML, renders Jinja2 template, sends via SMTP/TLS |
| `src/fetchers/rss_fetcher.py` | feedparser-based RSS parsing for MoneyDJ, TechNews, BBC. Handles date parsing and HTML stripping |
| `src/fetchers/web_scraper.py` | 鉅亨網 via public JSON API (`api.cnyes.com`), 工商時報 via BeautifulSoup HTML scraping |
| `src/fetchers/newsapi_fetcher.py` | NewsAPI.org `/v2/everything` endpoint, keyword-based international news search |
| `templates/digest.html` | Responsive HTML email template with full inline CSS, sections: header → stats → AI summary → original links → footer |
| `launchd/com.news.summary.plist` | macOS launchd agent example: triggers `docker compose run --rm` at 08:30 and 18:00 daily |

## Architecture

```
RSS/Web Sources → Local Keyword Filter → Gemini 1.5 Flash → Jinja2 HTML Email → SMTP
```

### Key Design Decisions

- **Config split:** `config.yaml` for user-editable settings; `.env` for secrets
- **Prompt strategy:** Articles placed first in prompt, instructions at the end (Gemini attention is strongest at context end)
- **Reuters RSS discontinued:** Use NewsAPI to index Reuters content + BBC RSS as primary international source
- **Anue (鉅亨網):** Uses public JSON API (`api.cnyes.com`) instead of scraping JS-rendered pages
- **Docker volume mount:** `config.yaml` is mounted read-only, so changes take effect without rebuilding the image
- **Fault tolerance:** Each fetcher is wrapped in try/except — one source failure does not crash the pipeline

## Usage

```bash
# 1. Copy .env template and fill in your API keys and SMTP credentials
cp .env.example .env
vi .env

# 2. Edit config.yaml to set keywords, news sources, and recipient email addresses
vi config.yaml

# 3. Build Docker image
docker compose build

# 4. Run the full pipeline (container runs once then exits)
docker compose run --rm news-digest

# 5. (Optional) Set up launchd scheduling
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

## Specification

Full system spec: `自動化新聞摘要 SPEC 調整.md` (Traditional Chinese, 8 chapters covering architecture, AI engine selection, data sources, processing logic, automation, email templates, extensibility, and implementation roadmap).
