# Deploying Precognition

Three components to deploy. Do them in this order.

---

## 1. Database — Turso (5 min)

Turso is a hosted libsql database. Free tier: 8GB, 9B row reads/month.

```bash
# Install Turso CLI
curl -sSfL https://get.tur.so/install.sh | bash

# Sign up / log in
turso auth signup   # or: turso auth login

# Create the database
turso db create precognition

# Get your credentials
turso db show precognition --url    # → TURSO_DATABASE_URL
turso db tokens create precognition # → TURSO_AUTH_TOKEN
```

Save both values — you'll need them in steps 2 and 3.

---

## 2. API — Render (10 min)

The `render.yaml` at the repo root auto-configures everything.

1. Go to [render.com](https://render.com) → **New** → **Blueprint**
2. Connect your GitHub repo (`0xthc/yc-scout`)
3. Render detects `render.yaml` and creates the `precognition-api` service
4. Go to the service → **Environment** → add these secrets:

| Key | Value | Required |
|-----|-------|----------|
| `TURSO_DATABASE_URL` | from Step 1 | ✅ |
| `TURSO_AUTH_TOKEN` | from Step 1 | ✅ |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | ✅ for clustering |
| `SCOUT_GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) — read:public scope | Recommended |
| `APIFY_API_TOKEN` | [apify.com](https://console.apify.com/account/integrations) | Optional (Twitter) |
| `PROXYCURL_API_KEY` | [nubela.co/proxycurl](https://nubela.co/proxycurl) | Optional (LinkedIn) |
| `SLACK_WEBHOOK_URL` | Slack app webhook URL | Optional (alerts) |

5. Deploy → wait ~2 min for the Docker build
6. Health check: `https://your-service.onrender.com/api/stats` should return `{"total":0,...}`
7. **Save your Render URL** — you'll need it in Step 3

---

## 3. Frontend — GitHub Pages (5 min)

### Enable GitHub Pages

1. Repo → **Settings** → **Pages**
2. Source: **GitHub Actions**

### Set the API URL

1. Repo → **Settings** → **Secrets and variables** → **Actions** → **Variables** tab
2. Add a **Repository variable** (not secret):
   - Name: `VITE_API_URL`
   - Value: your Render URL (e.g. `https://precognition-api.onrender.com`)

### Deploy

Push any commit to `main` — the deploy workflow triggers automatically.

Your dashboard will be live at:
```
https://<your-github-username>.github.io/yc-scout/
```

---

## 4. Pipeline — GitHub Actions (5 min)

The pipeline runs hourly via `.github/workflows/pipeline.yml`.

### Add pipeline secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **Secrets** tab:

| Secret | Value |
|--------|-------|
| `TURSO_DATABASE_URL` | same as Step 1 |
| `TURSO_AUTH_TOKEN` | same as Step 1 |
| `OPENAI_API_KEY` | same as Step 2 |
| `SCOUT_GITHUB_TOKEN` | same as Step 2 |
| `APIFY_API_TOKEN` | same as Step 2 (if using) |
| `PROXYCURL_API_KEY` | same as Step 2 (if using) |

### Trigger a manual run

Actions tab → **Precognition Pipeline** → **Run workflow**

Check the logs — you should see scraping, embedding, clustering, and scoring output.

---

## 5. Verify Everything Works

```bash
# Check API
curl https://your-service.onrender.com/api/stats
# → {"total": N, "strong": N, "toContact": N, "avgScore": N}

# Check themes (after pipeline runs with 20+ founders)
curl https://your-service.onrender.com/api/themes
# → [...theme clusters...]

# Check pulse
curl https://your-service.onrender.com/api/pulse
# → [...recent signals...]
```

Dashboard: `https://<username>.github.io/yc-scout/`

---

## Cost Breakdown

| Service | Free tier | Paid |
|---------|-----------|------|
| Turso | 8GB, 9B reads/mo | $29/mo (500GB) |
| Render | 512MB RAM, sleeps after 15min idle | $7/mo (always-on) |
| GitHub Actions | 2,000 min/mo | — |
| OpenAI embeddings | ~$0.002 per 1M tokens | Pay per use |
| Apify | $5 free credit | ~$0.002 per Twitter profile |
| Proxycurl | 10 free credits | $0.01 per LinkedIn profile |

**For personal use: ~$0/month** (free tiers cover it all, enrichment costs pennies per founder).

---

## Render Free Tier Note

Render free services **spin down after 15 minutes of inactivity** and take ~30s to wake up on the next request. For a personal VC tool this is fine — the dashboard loads in a few seconds after the first request.

To avoid cold starts, upgrade to Render Starter ($7/mo) or set up a simple uptime ping.
