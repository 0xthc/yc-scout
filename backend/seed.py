"""
Seed the database with demo founders so the API returns data immediately.
Run: python -m backend.seed
"""

from backend.db import get_db, init_db, upsert_founder, add_source, add_signal, add_tags, save_stats, save_score

DEMO_FOUNDERS = [
    {
        "name": "Aiko Tanaka", "handle": "@aiko_builds", "location": "San Francisco, CA",
        "bio": "Ex-Google Brain. Building real-time financial data infra for emerging markets. 3 YC alumni in my network.",
        "domain": "Fintech Infra", "stage": "Pre-seed", "company": "StreamLedger",
        "founded": "2024-09", "status": "to_contact", "yc_alumni_connections": 3,
        "email": "aiko@streamledger.io", "twitter": "@aiko_builds", "linkedin": "linkedin.com/in/aikotanaka", "website": "streamledger.io",
        "sources": ["github", "hn"],
        "tags": ["infrastructure", "fintech", "api"],
        "signals": [
            {"source": "github", "label": "482 commits in 90 days", "strong": True},
            {"source": "hn", "label": "Show HN: Live market data API — 847 points", "strong": True},
            {"source": "github", "label": "3 new repos: fin-stream, edge-cache, devkit", "strong": False},
        ],
        "stats": {"github_stars": 2840, "github_commits_90d": 482, "github_repos": 12, "hn_karma": 4210, "hn_submissions": 8, "hn_top_score": 847, "ph_upvotes": 0, "ph_launches": 0, "followers": 12400},
        "scores": {"founder_quality": 92, "execution_velocity": 95, "market_conviction": 88, "early_traction": 94, "deal_availability": 78, "composite": 91},
    },
    {
        "name": "Marcus Webb", "handle": "@marcuswebb", "location": "New York, NY",
        "bio": "Biomedical engineer turned founder. Automating clinical trial recruitment with AI. FDA advisor background.",
        "domain": "Health AI", "stage": "Pre-seed", "company": "TrialMatch",
        "founded": "2024-11", "status": "watching", "yc_alumni_connections": 1,
        "email": "marcus@trialmatch.ai", "twitter": "@marcuswebb", "linkedin": "", "website": "trialmatch.ai",
        "sources": ["hn", "producthunt"],
        "tags": ["healthtech", "ai", "biotech"],
        "signals": [
            {"source": "hn", "label": "Ask HN: How do you handle HIPAA in early-stage? — 310 pts", "strong": False},
            {"source": "producthunt", "label": "#2 Product of the Day — TrialMatch AI", "strong": True},
            {"source": "hn", "label": "Show HN: AI clinical trial matching — 512 points", "strong": True},
        ],
        "stats": {"github_stars": 340, "github_commits_90d": 156, "github_repos": 4, "hn_karma": 2870, "hn_submissions": 6, "hn_top_score": 512, "ph_upvotes": 890, "ph_launches": 1, "followers": 5800},
        "scores": {"founder_quality": 85, "execution_velocity": 82, "market_conviction": 94, "early_traction": 80, "deal_availability": 88, "composite": 85},
    },
    {
        "name": "Priya Nair", "handle": "@priya_nair_dev", "location": "London, UK",
        "bio": "Previously DeepMind. Open source compiler toolchain for ML workloads — 2.8k GitHub stars in 6 weeks.",
        "domain": "Dev Tools / AI Infra", "stage": "Bootstrapped", "company": "MLCompile",
        "founded": "2024-08", "status": "contacted", "yc_alumni_connections": 5,
        "email": "priya@mlcompile.dev", "twitter": "@priya_nair_dev", "linkedin": "linkedin.com/in/priyanair", "website": "mlcompile.dev",
        "sources": ["github", "hn", "producthunt"],
        "tags": ["devtools", "ml", "open-source", "compiler"],
        "signals": [
            {"source": "github", "label": "Repo hit 2,800 stars in 6 weeks", "strong": True},
            {"source": "hn", "label": "Show HN: Open-source ML compiler — 1.2k points", "strong": True},
            {"source": "producthunt", "label": "#1 Product of the Day — MLCompile", "strong": True},
        ],
        "stats": {"github_stars": 2800, "github_commits_90d": 620, "github_repos": 9, "hn_karma": 6140, "hn_submissions": 12, "hn_top_score": 1200, "ph_upvotes": 1450, "ph_launches": 2, "followers": 28000},
        "scores": {"founder_quality": 96, "execution_velocity": 98, "market_conviction": 86, "early_traction": 90, "deal_availability": 62, "composite": 89},
    },
    {
        "name": "Jordan Cole", "handle": "@jordancole", "location": "Austin, TX",
        "bio": "Serial founder (2 exits). Building B2B SaaS for construction project management. $18k MRR in month 3.",
        "domain": "B2B SaaS / Proptech", "stage": "Seed", "company": "ConstructIQ",
        "founded": "2024-07", "status": "to_contact", "yc_alumni_connections": 2,
        "email": "", "twitter": "@jordancole", "linkedin": "linkedin.com/in/jordancole", "website": "constructiq.co",
        "sources": ["producthunt", "hn"],
        "tags": ["saas", "proptech", "construction", "b2b"],
        "signals": [
            {"source": "hn", "label": "Who's Hiring — ConstructIQ (seed round)", "strong": False},
            {"source": "producthunt", "label": "#3 Product of the Week", "strong": True},
            {"source": "hn", "label": "Show HN: Construction PM tool — $18k MRR", "strong": True},
        ],
        "stats": {"github_stars": 0, "github_commits_90d": 45, "github_repos": 2, "hn_karma": 1540, "hn_submissions": 4, "hn_top_score": 380, "ph_upvotes": 720, "ph_launches": 1, "followers": 7200},
        "scores": {"founder_quality": 88, "execution_velocity": 80, "market_conviction": 82, "early_traction": 92, "deal_availability": 52, "composite": 81},
    },
    {
        "name": "Elif Demir", "handle": "@elifdemir", "location": "Berlin, DE",
        "bio": "PhD dropout (NLP/multilingual). Building real-time translation infra for enterprise Slack/Teams.",
        "domain": "NLP / Enterprise", "stage": "Pre-seed", "company": "LinguaSync",
        "founded": "2024-10", "status": "watching", "yc_alumni_connections": 0,
        "email": "elif@linguasync.io", "twitter": "", "linkedin": "linkedin.com/in/elifdemir", "website": "linguasync.io",
        "sources": ["github", "producthunt"],
        "tags": ["nlp", "enterprise", "saas", "translation"],
        "signals": [
            {"source": "github", "label": "240 commits — multilang-core repo", "strong": False},
            {"source": "producthunt", "label": "Upcoming launch — 1,400 subscribers", "strong": True},
            {"source": "github", "label": "Released v0.3 — 680 GitHub stars", "strong": False},
        ],
        "stats": {"github_stars": 680, "github_commits_90d": 240, "github_repos": 3, "hn_karma": 890, "hn_submissions": 2, "hn_top_score": 85, "ph_upvotes": 320, "ph_launches": 0, "followers": 3100},
        "scores": {"founder_quality": 72, "execution_velocity": 78, "market_conviction": 80, "early_traction": 65, "deal_availability": 92, "composite": 76},
    },
    {
        "name": "Tomas Rivera", "handle": "@tomas_build", "location": "Mexico City, MX",
        "bio": "Ex-Stripe LATAM. Building payment infra for SMBs across LatAm — processing $200k/mo at month 6.",
        "domain": "Fintech / Payments", "stage": "Seed", "company": "PayFlow",
        "founded": "2024-05", "status": "pass", "yc_alumni_connections": 4,
        "email": "tomas@payflow.mx", "twitter": "@tomas_build", "linkedin": "", "website": "payflow.mx",
        "sources": ["hn", "github"],
        "tags": ["fintech", "payments", "latam", "infrastructure"],
        "signals": [
            {"source": "hn", "label": "Show HN: Stripe alternative for LatAm — 390 pts", "strong": True},
            {"source": "github", "label": "SDK released — 420 stars", "strong": False},
        ],
        "stats": {"github_stars": 420, "github_commits_90d": 310, "github_repos": 7, "hn_karma": 2100, "hn_submissions": 5, "hn_top_score": 390, "ph_upvotes": 0, "ph_launches": 0, "followers": 8900},
        "scores": {"founder_quality": 86, "execution_velocity": 75, "market_conviction": 90, "early_traction": 82, "deal_availability": 55, "composite": 79},
    },
]


def seed():
    init_db()
    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) as c FROM founders").fetchone()
        count = existing["c"] if hasattr(existing, "__getitem__") and not isinstance(existing, tuple) else existing[0]
        if count > 0:
            print(f"DB already has {count} founders — skipping seed.")
            return

        for f in DEMO_FOUNDERS:
            fid = upsert_founder(
                conn,
                name=f["name"], handle=f["handle"], location=f["location"],
                bio=f["bio"], domain=f["domain"], stage=f["stage"],
                company=f["company"], founded=f["founded"], status=f["status"],
                yc_alumni_connections=f["yc_alumni_connections"],
                email=f.get("email", ""), twitter=f.get("twitter", ""),
                linkedin=f.get("linkedin", ""), website=f.get("website", ""),
            )
            for src in f["sources"]:
                add_source(conn, fid, src)
            add_tags(conn, fid, f["tags"])
            for sig in f["signals"]:
                add_signal(conn, fid, sig["source"], sig["label"], strong=sig["strong"])
            save_stats(conn, fid, **f["stats"])
            save_score(conn, fid, **f["scores"])
            print(f"  Seeded: {f['name']} ({f['company']}) — score {f['scores']['composite']}")

    print(f"\nDone — {len(DEMO_FOUNDERS)} founders seeded.")


if __name__ == "__main__":
    seed()
