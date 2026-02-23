"""
Incubator / accelerator detection — identifies founders who are
part of YC, 500 Global (500 Startups), or Plug and Play batches.

Detection sources:
  - Bio / about text parsing (e.g. "YC W26", "500 Startups Batch 30")
  - HN posts mentioning batch (e.g. "Launch YC: ...")
  - GitHub repo topics and descriptions
  - Product Hunt taglines

This is a strong founder_quality signal and affects deal_availability
timing (batch founders raise on a known schedule).
"""

import re

# ── Incubator pattern matchers ───────────────────────────────

# YC batch patterns: "YC W26", "Y Combinator S25", "YC Winter 2026", "(YC W26)"
_YC_PATTERNS = [
    re.compile(r"\bYC\s*[WSws]\d{2}\b", re.IGNORECASE),
    re.compile(r"\bY\s*Combinator\s*[WSws]\d{2}\b", re.IGNORECASE),
    re.compile(r"\bYC\s*(?:Winter|Summer|Fall|Spring)\s*\d{4}\b", re.IGNORECASE),
    re.compile(r"\bY\s*Combinator\s*(?:Winter|Summer|Fall|Spring)\s*\d{4}\b", re.IGNORECASE),
    re.compile(r"\(YC\s*[WSws]\d{2}\)", re.IGNORECASE),
    re.compile(r"\bYC\s*(?:backed|alum|alumni|batch)\b", re.IGNORECASE),
]

# 500 Global / 500 Startups patterns
_500_PATTERNS = [
    re.compile(r"\b500\s*(?:Global|Startups)\b", re.IGNORECASE),
    re.compile(r"\b500\s*Batch\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b500\.co\b", re.IGNORECASE),
]

# Plug and Play patterns
_PNP_PATTERNS = [
    re.compile(r"\bPlug\s*(?:and|&)\s*Play\b", re.IGNORECASE),
    re.compile(r"\bPnP\s*(?:Tech|batch|accelerator)\b", re.IGNORECASE),
]

# All incubators with their canonical names
INCUBATOR_PATTERNS = {
    "YC": _YC_PATTERNS,
    "500 Global": _500_PATTERNS,
    "Plug and Play": _PNP_PATTERNS,
}


def detect_incubator(text):
    """
    Detect incubator affiliation from text (bio, about, tagline, etc.).

    Returns:
        (incubator_name, batch_info) tuple, e.g. ("YC", "W26") or ("500 Global", "").
        Returns (None, None) if no match.
    """
    if not text:
        return None, None

    for name, patterns in INCUBATOR_PATTERNS.items():
        for pattern in patterns:
            m = pattern.search(text)
            if m:
                matched = m.group(0)
                # Try to extract batch info for YC
                if name == "YC":
                    batch_m = re.search(r"[WSws]\d{2}", matched)
                    if batch_m:
                        return name, batch_m.group(0).upper()
                    season_m = re.search(r"(Winter|Summer|Fall|Spring)\s*(\d{4})", matched, re.IGNORECASE)
                    if season_m:
                        season_code = {"winter": "W", "summer": "S", "fall": "F", "spring": "S"}
                        s = season_code.get(season_m.group(1).lower(), "")
                        y = season_m.group(2)[-2:]
                        return name, f"{s}{y}" if s else ""
                return name, ""

    return None, None


def detect_incubator_from_signals(signals):
    """
    Detect incubator affiliation from signal labels.

    Checks for "Launch YC:" prefix (YC companies use this on HN),
    and other incubator mentions in signal text.

    Args:
        signals: List of signal dicts with 'label' field

    Returns:
        (incubator_name, batch_info) or (None, None)
    """
    for s in signals:
        label = s.get("label", "")
        # "Launch YC: Product Name — N pts" is the canonical HN launch format
        if label.lower().startswith("launch yc"):
            return "YC", ""
        # Also check signal text for batch mentions
        inc, batch = detect_incubator(label)
        if inc:
            return inc, batch
    return None, None


def format_incubator(name, batch):
    """Format incubator name with optional batch info."""
    if not name:
        return ""
    if batch:
        return f"{name} {batch}"
    return name
