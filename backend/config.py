import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("SCOUT_DB_PATH", str(BASE_DIR / "scout.db"))

# GitHub — requires a personal access token for higher rate limits
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Product Hunt — requires API credentials (developer.producthunt.com)
PH_API_TOKEN = os.getenv("PH_API_TOKEN", "")

# Alerts — Slack
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Alerts — Email (SMTP)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# Scoring thresholds
ALERT_SCORE_THRESHOLD = int(os.getenv("ALERT_SCORE_THRESHOLD", "85"))
ALERT_MOMENTUM_SPIKE = float(os.getenv("ALERT_MOMENTUM_SPIKE", "15.0"))

# Pipeline schedule (minutes between runs)
PIPELINE_INTERVAL_MINUTES = int(os.getenv("PIPELINE_INTERVAL_MINUTES", "60"))

# Enrichment — only fires after a founder crosses this score threshold
ENRICHMENT_SCORE_THRESHOLD = int(os.getenv("ENRICHMENT_SCORE_THRESHOLD", "75"))

# Apify — Twitter/X profile enrichment
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# Proxycurl — LinkedIn profile enrichment
PROXYCURL_API_KEY = os.getenv("PROXYCURL_API_KEY", "")
