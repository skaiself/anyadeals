# anyadeals — iHerb Coupon Pipeline

## Project Overview

Automated pipeline that discovers, validates, and promotes iHerb promo codes across 21 regions. Deployed on a CachyOS always-on server, auto-deploys to anyadeals.com via Cloudflare Pages on git push.

**Owner's referral code:** OFR0296 — reject any referral codes (type=2) that compete with it.

## Architecture

```
Host (CachyOS, user 1000:1000)
├── Docker Compose services (internal network "pipeline")
│   ├── orchestrator :8080 — schedules, proxies APIs, git push
│   ├── researcher   :8001 — scrapes 8+ coupon sources
│   ├── validator    :8002 — Playwright browser validation + gutschein scraper
│   └── poster       :8003 — Pillow images, Twitter/Reddit posting
├── Systemd timers (host-side AI — Claude CLI subscription, zero API cost)
│   ├── anyadeals-research.timer — AI parses raw codes (haiku model)
│   └── anyadeals-poster.timer  — AI generates social copy (haiku model)
└── GOST proxy :8088 — used by validator for browser sessions
```

**Key constraint:** Claude CLI cannot run inside Docker (root restriction). AI work runs on the host via systemd timers.

## Overnight Pipeline Schedule (UTC)

```
01:00-02:00  Scrape (researcher)
02:30-03:30  AI Parse (Claude CLI haiku via systemd timer)
04:00-07:00  Validate (Playwright, all 21 regions, random delays 30-120s)
```

## Tech Stack

- **Backend:** Python 3.12, FastAPI, httpx, Playwright + Chrome (headless)
- **Frontend:** Next.js (static export), Tailwind CSS, deployed to Cloudflare Pages
- **AI:** Claude CLI (haiku model) for code parsing and social copy
- **Infra:** Docker Compose, systemd timers, GOST proxy, logrotate (30-day retention)

## Service Details

### Researcher (`services/researcher/`)
- `server.py` — FastAPI, `/run` endpoint triggers scrape
- `sources/` — scraper modules, all extend `BaseScraper`:
  - `iherb_official.py` — iherb.com/info/sales-and-offers
  - `couponfollow.py`, `slickdeals.py`, `hotdeals.py` — coupon aggregators (HTTP)
  - `simplycodes.py` — HTTP scraper (gets 403, actual scraping done via Playwright in validator)
  - `reddit.py` — r/iherb, r/Supplements, r/herbalism, r/SkincareAddiction + search
  - `generic.py` — rakuten, savings.com, groupon, marieclaire (HTTP)
  - `gutschein.py` — calls validator's `/scrape-gutschein` endpoint for Playwright-based scraping
- `claude_parser.py` — CLAUDE_PROMPT_TEMPLATE for AI parsing, includes `notes` field

### Validator (`services/validator/`)
- `server.py` — FastAPI, `/run` (validation), `/scrape-gutschein` (Playwright scraper)
- `browser_validator.py` — two-stage orchestrator:
  - Stage 1: `IHerbAPIValidator` — fast HTTP API check (~3s/code), no proxy needed
  - Stage 2: `IHerbRegionValidator` — Playwright cart check across all regions
  - Pre-flight before Stage 2: proxy health check (GET iherb.com/robots.txt) + canary check (GOLD60 must pass US)
  - If either pre-flight fails, Stage 2 is skipped entirely — `fail_count` not incremented
  - Stage 1 rejection → immediate invalidation; Stage 2 failure → immediate invalidation (pre-flights ensure it's trustworthy)
  - Stage 1 has `CascadingFailure` protection: aborts after 10 consecutive transient errors
- `browser_validate.py` — merges results into coupons.json; single failure invalidates (no threshold)
- `backfill_discounts.py` — one-shot script to fill empty `discount` on active coupons (deterministic + Claude CLI haiku)
- `gutschein_scraper.py` — Playwright scraper for sites that hide codes behind JS:
  - `scrape_welt_de()` — clicks "GUTSCHEIN SICHERN", reads code from `<input aria-label="Couponcode">`
  - `scrape_simplycodes()` — reads codes from DOM (site returns 403 to HTTP)

### Orchestrator (`services/orchestrator/`)
- `server.py` — FastAPI, dashboard, `/trigger/*` endpoints, API proxy routes
- `scheduler.py` — APScheduler with overnight windows, random timing
- `git_ops.py` — stages only content files, GITHUB_TOKEN auth, pushes only on change
- `dashboard_writer.py` — hourly stats, skips write when unchanged

### Poster (`services/poster/`)
- `server.py` — `/run` posts best coupon, `/best-coupon`, `/copy` endpoints
- `image_generator.py` — Pillow-only (sync), 1080x1080 branded images
- `copy_generator.py` — Claude CLI haiku for tweet copy
- `twitter_poster.py`, `reddit_poster.py` — social media posting

## Data Files (site/data/)

| File | Description |
|---|---|
| `coupons.json` | All coupons: status, discount, regions, notes, fail_count |
| `research.json` | AI-parsed research data from all scrapers |
| `raw_codes.json` | Latest raw scrape output (input for AI parsing) |
| `dashboard.json` | Runtime pipeline stats (not content — not staged for push) |
| `posts.json` | Social media post log |
| `posts/*.png` | Generated coupon images |

## Important Patterns

### Validation Logic
- Stage 1: HTTP API check on all codes (fast, no proxy) — unrecognised codes invalidated immediately
- Stage 2: Playwright cart check on Stage 1 survivors across all 21 regions
- Pre-flight before Stage 2: proxy health check + GOLD60 canary in US — skip Stage 2 if either fails
- Single Stage 2 failure → `status: "invalid"`, regions cleared (no threshold — pre-flights make results trustworthy)
- Success resets `fail_count` to 0
- Notes from AI parsing fill empty notes; existing notes never overwritten
- `discount` auto-resolved from cart HTML → API percentage → code-name inference on each validation

### Git Push Policy
- Only content files staged: `coupons.json`, `research.json`, `raw_codes.json`, `posts.json`
- `dashboard.json` gets `last_deploy` timestamp only at push time
- No push if no content changes
- Each push triggers Cloudflare Pages auto-deploy

### Frontend (site/app/coupons/iherb/page.tsx)
- Shows valid + region_limited codes (active table), expired codes (expired table)
- No "Status" column — only valid codes displayed
- Regions sorted US first
- Empty notes show blank (not "—")
- Empty discount shows "—" (not blank)

## Commands

```bash
# Rebuild and restart services
docker compose build && docker compose up -d

# Manual triggers
curl -X POST http://localhost:8080/trigger/research
curl -X POST http://localhost:8080/trigger/validate
curl -X POST http://localhost:8080/trigger/post

# Check status
curl http://localhost:8080/status
curl http://localhost:8080/jobs

# Logs
docker logs anyadeals-validator --tail 50
docker logs anyadeals-researcher --tail 50

# Systemd timers
systemctl list-timers | grep anyadeals
```

## Testing

```bash
# Validator unit tests
docker exec anyadeals-validator python -m pytest tests/ -v

# Test specific code validation
docker exec anyadeals-validator python browser_validator.py --codes GOLD60 --regions us --headless

# Test with brand notes
docker exec anyadeals-validator python3 -c "
import subprocess, json
subprocess.run(['python3', 'browser_validator.py', '--codes', 'SOMEBRAND',
  '--regions', 'us', '--headless',
  '--brand-notes', json.dumps({'SOMEBRAND': 'Some Brand brand only.'})],
)"
```

## Conventions

- All Docker containers run as `user: "1000:1000"` (matches host user)
- Services communicate via Docker network "pipeline" (service names as hostnames)
- AI models: always use `haiku` via Claude CLI subscription (zero API cost)
- Coupon notes format for brand codes: "Brand Name brand only." (auto-detected by validator)
- Regions: 2-letter lowercase codes (us, de, gb, etc.)
