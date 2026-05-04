"""
South Park Commons (SPC) company scraper.

Source: https://southparkcommons.com/companies
Fetched via Jina reader: https://r.jina.ai/https://southparkcommons.com/companies

Strategy:
  - Parse company names from ### headings in the Jina-rendered markdown
  - Capture the paragraph immediately following each heading as the description
  - 2026-only filter: only keep Seed stage companies (SPC doesn't expose cohort
    years in the public listing, so Seed stage is used as a proxy for recent/active)
  - Returns list of dicts: {name, stage, description, source}
"""

import logging
import re

import httpx

logger = logging.getLogger(__name__)

JINA_URL = "https://r.jina.ai/https://southparkcommons.com/companies"

# 2026-only filter: Seed stage is the proxy for recent SPC membership
# (SPC doesn't publish cohort years publicly; Seed ≈ active 2025-2026 members)
_TARGET_STAGE = "Seed"


def _fetch_markdown() -> str:
    """Fetch the SPC companies page via Jina reader and return raw markdown."""
    try:
        resp = httpx.get(
            JINA_URL,
            headers={"User-Agent": "Precognition/1.0", "Accept": "text/markdown"},
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as e:
        logger.warning("SPC Jina fetch failed: %s", e)
        return ""


def _parse_companies(markdown: str) -> list[dict]:
    """
    Parse company entries from Jina-rendered markdown.

    Jina renders each company roughly as:

        ### CompanyName
        Stage · Description text ...

    We capture the ### heading as the name and the first non-empty line
    after it as the description/stage line.
    """
    companies = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Match ### headings — company names
        m = re.match(r"^###\s+(.+)$", line)
        if m:
            name = m.group(1).strip()
            # Collect the next non-empty lines as context
            desc_lines = []
            j = i + 1
            while j < len(lines) and len(desc_lines) < 4:
                next_line = lines[j].strip()
                if next_line.startswith("#"):
                    break  # Hit the next heading
                if next_line:
                    desc_lines.append(next_line)
                j += 1

            description = " ".join(desc_lines)[:500]

            # Stage detection: look for explicit "Seed" mention in the nearby text
            stage_text = description.lower()
            if "seed" in stage_text or not stage_text:
                stage = "Seed"
            elif "series a" in stage_text or "series b" in stage_text:
                stage = "Series A/B+"
            elif "early" in stage_text:
                stage = "Early"
            else:
                # Default: treat unlabelled as Seed (SPC is predominantly pre-seed/seed)
                stage = "Seed"

            companies.append({
                "name": name,
                "stage": stage,
                "description": description,
                "source": "southparkcommons",
            })
            i = j
            continue
        i += 1

    return companies


def scrape_southparkcommons() -> list[dict]:
    """
    Scrape South Park Commons companies page and return Seed-stage entries.

    2026-only filter: Only Seed stage companies are returned, as a proxy for
    recent/active SPC membership (cohort years are not published publicly).

    Returns:
        List of dicts with keys: name, stage, description, source
    """
    logger.info("SPC: fetching companies via Jina")
    markdown = _fetch_markdown()
    if not markdown:
        logger.warning("SPC: empty response, returning no companies")
        return []

    all_companies = _parse_companies(markdown)
    logger.info("SPC: parsed %d total companies", len(all_companies))

    # 2026-only filter: keep only Seed stage as proxy for current/recent cohort
    filtered = [c for c in all_companies if c["stage"] == _TARGET_STAGE]
    logger.info("SPC: %d Seed-stage companies after 2026-only filter", len(filtered))
    return filtered
