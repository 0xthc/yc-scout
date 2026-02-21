"""
Alerts system — Slack webhook and email (SMTP) notifications.

Triggers:
  1. New founder crosses the score threshold (default 85)
  2. Existing founder's momentum spikes (>15pt jump between runs)
  3. Strong signal detected on a tracked founder
"""

import json
import logging
import smtplib
from email.mime.text import MIMEText

import httpx

from backend.config import (
    ALERT_EMAIL_TO,
    ALERT_MOMENTUM_SPIKE,
    ALERT_SCORE_THRESHOLD,
    SLACK_WEBHOOK_URL,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)
from backend.db import get_previous_score

logger = logging.getLogger(__name__)


def _send_slack(message, blocks=None):
    """Send a message to Slack via webhook."""
    if not SLACK_WEBHOOK_URL:
        logger.debug("Slack webhook not configured, skipping")
        return False
    payload = {"text": message}
    if blocks:
        payload["blocks"] = blocks
    try:
        resp = httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.error("Slack alert failed: %s", e)
        return False


def _send_email(subject, body):
    """Send an email alert via SMTP."""
    if not all([SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO]):
        logger.debug("Email not configured, skipping")
        return False
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL_TO
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error("Email alert failed: %s", e)
        return False


def _format_slack_blocks(founder_name, handle, scores, alert_type, detail):
    """Rich Slack message with score breakdown."""
    color = "#34d399" if scores["composite"] >= 90 else "#f59e0b" if scores["composite"] >= 80 else "#60a5fa"
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"SCOUT Alert: {founder_name}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{alert_type}*\n"
                    f"Handle: `{handle}`\n"
                    f"{detail}\n\n"
                    f"*Composite Score: {scores['composite']}*\n"
                    f"Momentum: {scores['momentum']} | "
                    f"Domain: {scores['domain']} | "
                    f"Team: {scores['team']} | "
                    f"Traction: {scores['traction']} | "
                    f"YC Fit: {scores['ycfit']}"
                ),
            },
        },
    ]


def check_alerts(conn, founder_id, founder_name, handle, scores, log_alert):
    """
    Evaluate alert triggers for a scored founder.

    Args:
        conn: SQLite connection
        founder_id: Founder's DB id
        founder_name: Display name
        handle: @handle
        scores: Dict with momentum, domain, team, traction, ycfit, composite
        log_alert: Callable(founder_id, alert_type, channel, message) to persist

    Returns:
        Number of alerts sent.
    """
    alerts_sent = 0

    # Trigger 1: High composite score
    if scores["composite"] >= ALERT_SCORE_THRESHOLD:
        prev = get_previous_score(conn, founder_id)
        # Only alert if this is a new threshold crossing (not a re-alert)
        if not prev or prev["composite"] < ALERT_SCORE_THRESHOLD:
            alert_type = "High Score Threshold"
            detail = f"Composite score hit {scores['composite']} (threshold: {ALERT_SCORE_THRESHOLD})"
            msg = f"SCOUT: {founder_name} ({handle}) scored {scores['composite']} — {detail}"

            blocks = _format_slack_blocks(founder_name, handle, scores, alert_type, detail)
            if _send_slack(msg, blocks):
                log_alert(founder_id, alert_type, "slack", msg)
                alerts_sent += 1
            if _send_email(f"SCOUT Alert: {founder_name} — Score {scores['composite']}", msg):
                log_alert(founder_id, alert_type, "email", msg)
                alerts_sent += 1

    # Trigger 2: Momentum spike
    prev = get_previous_score(conn, founder_id)
    if prev:
        momentum_delta = scores["momentum"] - prev["momentum"]
        if momentum_delta >= ALERT_MOMENTUM_SPIKE:
            alert_type = "Momentum Spike"
            detail = f"Momentum jumped +{momentum_delta:.0f} pts ({prev['momentum']} → {scores['momentum']})"
            msg = f"SCOUT: {founder_name} ({handle}) momentum spike — {detail}"

            blocks = _format_slack_blocks(founder_name, handle, scores, alert_type, detail)
            if _send_slack(msg, blocks):
                log_alert(founder_id, alert_type, "slack", msg)
                alerts_sent += 1
            if _send_email(f"SCOUT Alert: {founder_name} — Momentum Spike", msg):
                log_alert(founder_id, alert_type, "email", msg)
                alerts_sent += 1

    return alerts_sent
