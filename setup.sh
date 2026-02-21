#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
#  SCOUT — One-command setup for the free deployment stack
#  Render (API) + Turso (DB) + GitHub Actions (cron pipeline)
# ═══════════════════════════════════════════════════════════════

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[scout]${NC} $1"; }
ok()    { echo -e "${GREEN}  ✓${NC} $1"; }
warn()  { echo -e "${YELLOW}  ⚠${NC} $1"; }

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   SCOUT — Deployment Setup            ║"
echo "  ║   Render + Turso + GitHub Actions     ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ── Step 1: Python backend deps ─────────────────────────────
info "Installing Python dependencies..."
pip install -r backend/requirements.txt -q
ok "Backend dependencies installed"

# ── Step 2: Node frontend deps ──────────────────────────────
info "Installing Node dependencies..."
npm ci --silent 2>/dev/null || npm install --silent
ok "Frontend dependencies installed"

# ── Step 3: Turso database ──────────────────────────────────
info "Setting up Turso database..."
if command -v turso &>/dev/null; then
    ok "Turso CLI found"

    if ! turso auth status &>/dev/null 2>&1; then
        warn "Not logged in to Turso. Run: turso auth signup"
    else
        ok "Turso authenticated"

        DB_EXISTS=$(turso db list 2>/dev/null | grep -c "scout" || true)
        if [ "$DB_EXISTS" -eq 0 ]; then
            info "Creating Turso database 'scout'..."
            turso db create scout
            ok "Database created"
        else
            ok "Database 'scout' already exists"
        fi

        TURSO_URL=$(turso db show scout --url 2>/dev/null || echo "")
        TURSO_TOKEN=$(turso db tokens create scout 2>/dev/null || echo "")

        if [ -n "$TURSO_URL" ] && [ -n "$TURSO_TOKEN" ]; then
            ok "Turso URL:   $TURSO_URL"
            ok "Turso Token: ${TURSO_TOKEN:0:20}..."

            # Write to .env if it doesn't have them yet
            if [ ! -f .env ]; then
                cp .env.example .env
            fi
            if ! grep -q "^TURSO_DATABASE_URL=" .env 2>/dev/null || grep -q "^TURSO_DATABASE_URL=$" .env 2>/dev/null; then
                sed -i "s|^TURSO_DATABASE_URL=.*|TURSO_DATABASE_URL=$TURSO_URL|" .env
                sed -i "s|^TURSO_AUTH_TOKEN=.*|TURSO_AUTH_TOKEN=$TURSO_TOKEN|" .env
                ok "Wrote Turso credentials to .env"
            fi

            echo ""
            echo -e "${YELLOW}  Add these as GitHub repo secrets:${NC}"
            echo "    TURSO_DATABASE_URL=$TURSO_URL"
            echo "    TURSO_AUTH_TOKEN=$TURSO_TOKEN"
            echo ""
        fi
    fi
else
    warn "Turso CLI not found. Install it:"
    echo "    curl -sSfL https://get.tur.so/install.sh | bash"
    echo "    turso auth signup"
    echo ""
fi

# ── Step 4: Initialize DB + seed demo data ──────────────────
info "Initializing database schema and seeding demo data..."
python -m backend.seed
ok "Database ready"

# ── Step 5: Build frontend ──────────────────────────────────
info "Building frontend..."
npm run build --silent
ok "Frontend built to dist/"

# ── Step 6: Verify API ──────────────────────────────────────
info "Smoke-testing API..."
python -c "
from backend.db import init_db, get_db
from backend.api import _build_founder
init_db()
with get_db() as conn:
    rows = conn.execute('SELECT * FROM founders').fetchall()
    assert len(rows) > 0, 'No founders in DB'
    f = _build_founder(conn, rows[0])
    assert 'score' in f and 'signals' in f, 'API shape mismatch'
print(f'  API OK — {len(rows)} founders, all fields present')
"
ok "API verified"

# ── Summary ─────────────────────────────────────────────────
echo ""
echo "  ╔═══════════════════════════════════════════════════════════╗"
echo "  ║  Setup complete! Next steps:                             ║"
echo "  ╠═══════════════════════════════════════════════════════════╣"
echo "  ║                                                          ║"
echo "  ║  1. LOCAL DEV                                            ║"
echo "  ║     uvicorn backend.api:app --reload                     ║"
echo "  ║     VITE_API_URL=http://localhost:8000 npm run dev       ║"
echo "  ║                                                          ║"
echo "  ║  2. RENDER (you do manually)                             ║"
echo "  ║     → render.com → New Web Service → connect this repo   ║"
echo "  ║     → render.yaml auto-detected → add env vars           ║"
echo "  ║                                                          ║"
echo "  ║  3. GITHUB ACTIONS (you do manually)                     ║"
echo "  ║     → Repo Settings → Secrets → add:                     ║"
echo "  ║       TURSO_DATABASE_URL, TURSO_AUTH_TOKEN                ║"
echo "  ║       SCOUT_GITHUB_TOKEN, PH_API_TOKEN                   ║"
echo "  ║     → Repo Settings → Variables → add:                   ║"
echo "  ║       VITE_API_URL = https://your-app.onrender.com       ║"
echo "  ║                                                          ║"
echo "  ╚═══════════════════════════════════════════════════════════╝"
echo ""
