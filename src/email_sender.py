"""Render Jinja2 HTML email and send via SMTP/TLS."""

from __future__ import annotations

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src import config
from src.models import FilteredArticle

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _markdown_to_html(md_text: str) -> str:
    """Convert simple markdown from Gemini output to inline HTML for email."""
    lines = md_text.split("\n")
    html_parts: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_parts.append("<br>")
            continue

        # ## Heading -> <h2>
        if stripped.startswith("## "):
            content = stripped[3:]
            # Detect importance emoji and color the heading
            color = "#333333"
            if "🔴" in content:
                color = "#e53935"
            elif "🟡" in content:
                color = "#f9a825"
            elif "🟢" in content:
                color = "#43a047"
            html_parts.append(
                f'<h2 style="margin:20px 0 8px; font-size:17px; color:{color}; '
                f'border-left:4px solid {color}; padding-left:12px;">{content}</h2>'
            )
        # ### Sub-heading -> <h3>
        elif stripped.startswith("### "):
            html_parts.append(
                f'<h3 style="margin:16px 0 6px; font-size:15px; color:#555;">'
                f'{stripped[4:]}</h3>'
            )
        # - bullet -> <li>
        elif stripped.startswith("- "):
            html_parts.append(
                f'<div style="margin:4px 0; padding-left:16px;">'
                f'• {stripped[2:]}</div>'
            )
        # **bold** -> <strong>
        else:
            converted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
            html_parts.append(f'<p style="margin:4px 0;">{converted}</p>')

    return "\n".join(html_parts)


def render_email(
    summary: str,
    articles: list[FilteredArticle],
    date: str,
) -> str:
    """Render the digest HTML email.

    Args:
        summary: Markdown summary text from Gemini.
        articles: Filtered articles for the links section.
        date: Formatted date string.

    Returns:
        Complete HTML email body.
    """
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("digest.html")

    sources = sorted({a.source for a in articles})
    summary_html = _markdown_to_html(summary)

    return template.render(
        date=date,
        summary_html=summary_html,
        articles=articles,
        model=config.GEMINI_MODEL,
        sources=sources,
    )


def send_email(html_body: str, subject: str) -> None:
    """Send HTML email via SMTP/TLS.

    Args:
        html_body: Rendered HTML content.
        subject: Email subject line.
    """
    if not config.EMAIL_RECIPIENTS:
        logger.warning("No email recipients configured, skipping send")
        return

    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        logger.error("SMTP credentials not configured (check .env)")
        raise RuntimeError("SMTP credentials missing")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(config.EMAIL_RECIPIENTS)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(
            config.EMAIL_FROM,
            config.EMAIL_RECIPIENTS,
            msg.as_string(),
        )

    logger.info("Email sent to %s", ", ".join(config.EMAIL_RECIPIENTS))
