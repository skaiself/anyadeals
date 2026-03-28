# AnyaDeals

Automated iHerb coupon pipeline with a static site frontend.

## Structure

```
anyadeals/
├── site/          # Next.js static site (Cloudflare Pages)
├── services/      # Backend pipeline (Docker Compose)
│   ├── orchestrator/  # Scheduler, git push, dashboard writer
│   ├── researcher/    # Coupon discovery (web scraping + Claude CLI)
│   ├── validator/     # Coupon testing (Playwright + HTTP proxies)
│   └── poster/        # Social media posting (Twitter/X, Reddit)
├── docker-compose.yml
└── docs/
    └── REDESIGN-GUIDE.md  # Instructions for redesigning the site
```

## How It Works

1. **Researcher** scrapes coupon codes from the web, parses them with Claude CLI
2. **Validator** tests each code against iHerb checkout using Playwright and regional proxies
3. **Orchestrator** commits validated results to GitHub, triggering a Cloudflare Pages rebuild
4. **Poster** shares valid codes on Twitter/X and Reddit
5. **Site** displays verified codes to visitors (static, no runtime API calls)

## Development

```bash
cd site
npm install
npm run dev        # http://localhost:3000
npm run build      # Static output in out/
npm test           # Run test suite (52 tests)
```

## Deployment (Cloudflare Pages)

1. Go to Cloudflare Pages dashboard
2. Create new project → Connect to GitHub → Select `skaiself/anyadeals`
3. Build settings:
   - Build command: `cd site && npm install && npm run build`
   - Build output directory: `site/out`
   - Root directory: `/`
4. Deploy

## Running the Pipeline

```bash
cp .env.example .env   # Fill in API keys (PROXY_URL required for validation)
docker compose up -d
```

The `PROXY_URL` environment variable is required for the validator to test coupons against iHerb. It should point to an IPRoyal Web Unblocker proxy (or similar) for Step 1 (API) validation. Step 2 (Browser) validation uses a local GOST proxy on port 8088 (see `/home/skaiself/repo/dockerproxy/`). iHerb blocks server IPs directly (403), Web Unblocker bypasses but breaks sessions, the local GOST proxy works for browser-based validation.

### Pipeline flow

1. **Researcher** scrapes web sources (CouponFollow, HotDeals, Reddit, Generic) → writes discovered codes to `site/data/research.json` (status: `pending`)
2. **Validator Step 1 (API)** reads pending codes from `research.json` + any static codes from `config.json` → tests each via httpx + Web Unblocker proxy → detects valid/invalid and code type (promo vs referral)
3. **Validator Step 2 (Browser)** codes that pass Step 1 are tested in Playwright via local GOST proxy (port 8088) → launches fresh browser per region → adds items from checkout.iherb.com "Recommended for you" (same-domain session persistence) → applies coupon → extracts discount amount and regional eligibility → writes valid codes to `site/data/coupons.json` and updates `research.json` statuses
4. **Orchestrator** commits data changes to GitHub → triggers Cloudflare Pages rebuild

The orchestrator runs on a schedule:
- **6:00 & 18:00 UTC** — research + validate + git push
- **12:00 UTC** — re-validate existing codes
- **9:00, 13:00, 18:00 UTC** — post to Twitter/X
- **Tue & Fri 10:00 UTC** — post to Reddit
- **Every hour** — update dashboard stats

## Troubleshooting

### Browser validation region issues

- **Working regions:** US, KR, JP, DE, GB, AU, SA, CA, CN, RS, HR (all 11 regions)
- **Region switching method:** "Ship to" modal → searchable country dropdown → type country name → click option → fill zip code → Save
- **Critical:** iHerb lists South Korea as "Korea, Republic of" (not "South Korea"), and the Save button is disabled without a zip/postal code
- **Post-region popups:** Some regions (e.g. KR) show a "Special note" modal after switching — automatically dismissed by the validator
- **Session tip:** Fresh browser is launched per region to avoid session degradation

### Referral code filtering

Referral codes (`appliedCouponCodeType=2`) are automatically rejected except OFR0296 (our affiliate code). This prevents competing referral codes from appearing on the site.

### Discount extraction fallback

Discount amounts are extracted using a 3-tier fallback: API response → research text parsing → code name parser (looks for numbers 5-50 at end of code name, e.g. "IHERB22OFF" → 22%).

### Services report `healthy: false` with `FileNotFoundError`

If all backend services fail with errors like `No such file or directory: '/data/coupons.json'`, the Docker volume mounts are stale. This happens when containers were created before the data directory was moved or restructured. Fix by recreating them:

```bash
docker compose down && docker compose up -d
```

### Healthcheck endpoints

Each service exposes a `/status` endpoint:

```bash
curl http://localhost:8080/status                                    # Orchestrator
docker exec anyadeals-researcher curl -s http://localhost:8001/status # Researcher
docker exec anyadeals-validator curl -s http://localhost:8002/status  # Validator
docker exec anyadeals-poster curl -s http://localhost:8003/status     # Poster
```

Note: researcher, validator, and poster ports are internal to the Docker network, so healthchecks must be run via `docker exec`.

## Tech Stack

- **Frontend:** Next.js 15 + React 19 + Tailwind CSS 3 + TypeScript
- **Backend:** Python 3.12 + FastAPI + APScheduler + Playwright
- **Hosting:** Cloudflare Pages (static export)
- **Data:** JSON files in `site/data/` (auto-updated by pipeline, committed to git)
