"""
LinkedIn enrichment via Proxycurl API.

Pulls:
  - Full employment history (current + past companies, tenures)
  - Education (school, degree, field)
  - Serial founder detection (>1 company founded)
  - Alumni network signals (YC, top universities, FAANG)
  - Headline and summary for bio enrichment

Requires: PROXYCURL_API_KEY in environment.
Falls back gracefully if key is missing or profile not found.
"""

import logging

import httpx

from backend.config import PROXYCURL_API_KEY

logger = logging.getLogger(__name__)

PROXYCURL_BASE = "https://nubela.co/proxycurl/api/v2"

FAANG = {"google", "meta", "apple", "amazon", "microsoft", "netflix",
         "openai", "anthropic", "deepmind", "stripe", "airbnb", "uber"}

TOP_UNIVERSITIES = {
    "mit", "stanford", "harvard", "caltech", "carnegie mellon", "cmu",
    "berkeley", "oxford", "cambridge", "eth", "epfl", "imperial",
}

YC_SIGNALS = {"y combinator", "yc", "ycombinator"}


def _fetch_profile(linkedin_url: str) -> dict | None:
    """Call Proxycurl Person Profile endpoint."""
    if not PROXYCURL_API_KEY:
        logger.warning("PROXYCURL_API_KEY not set — skipping LinkedIn enrichment")
        return None

    try:
        resp = httpx.get(
            f"{PROXYCURL_BASE}/linkedin",
            headers={"Authorization": f"Bearer {PROXYCURL_API_KEY}"},
            params={"url": linkedin_url, "use_cache": "if-present", "fallback_to_cache": "on-error"},
            timeout=30,
        )
        if resp.status_code == 404:
            logger.info("LinkedIn profile not found: %s", linkedin_url)
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Proxycurl request failed for %s: %s", linkedin_url, e)
        return None


def _detect_serial_founder(experiences: list[dict]) -> bool:
    """Return True if the person founded more than one company."""
    founder_titles = {"founder", "co-founder", "cofounder", "ceo & founder", "founding"}
    companies_founded = set()
    for exp in experiences:
        title = (exp.get("title") or "").lower()
        company = exp.get("company") or ""
        if any(kw in title for kw in founder_titles) and company:
            companies_founded.add(company.lower().strip())
    return len(companies_founded) > 1


def _extract_background(profile: dict) -> dict:
    """Extract key signals from a Proxycurl profile response."""
    experiences = profile.get("experiences") or []
    education = profile.get("education") or []

    # Current role
    current = next((e for e in experiences if not e.get("ends_at")), None)
    current_company = current.get("company", "") if current else ""
    current_title = current.get("title", "") if current else ""

    # Prior companies
    companies = [e.get("company", "").lower() for e in experiences if e.get("company")]

    # FAANG signal
    ex_faang = any(c in FAANG for c in companies)

    # Education signals
    schools = [e.get("school", "").lower() for e in education if e.get("school")]
    top_uni = any(any(uni in school for uni in TOP_UNIVERSITIES) for school in schools)
    has_phd = any("phd" in (e.get("degree_name") or "").lower() for e in education)

    # YC signal
    has_yc = any(any(y in c for y in YC_SIGNALS) for c in companies)

    # Serial founder
    is_serial = _detect_serial_founder(experiences)

    # Build bio enrichment string
    signals = []
    if ex_faang:
        faang_co = next((c.title() for c in companies if c in FAANG), "FAANG")
        signals.append(f"ex-{faang_co}")
    if has_phd:
        signals.append("PhD")
    if top_uni and not has_phd:
        signals.append("top university")
    if has_yc:
        signals.append("YC")
    if is_serial:
        signals.append("serial founder")

    summary = profile.get("summary") or profile.get("headline") or ""
    if signals:
        summary = f"[{', '.join(signals)}] {summary}".strip()

    logger.info(
        "LinkedIn enriched: serial=%s, exFAANG=%s, YC=%s, PhD=%s",
        is_serial, ex_faang, has_yc, has_phd,
    )

    return {
        "linkedin_summary": summary[:500],  # cap length
        "is_serial_founder": is_serial,
        "linkedin_ex_faang": ex_faang,
        "linkedin_has_yc": has_yc,
        "linkedin_has_phd": has_phd,
        "linkedin_current_company": current_company,
        "linkedin_current_title": current_title,
    }


def enrich_linkedin(linkedin_url: str) -> dict | None:
    """
    Enrich a founder's LinkedIn profile.

    Returns dict with enrichment fields or None if enrichment failed.
    """
    if not linkedin_url or not linkedin_url.startswith("http"):
        return None

    profile = _fetch_profile(linkedin_url)
    if not profile:
        return None

    return _extract_background(profile)
