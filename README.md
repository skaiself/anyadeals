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

The `BROWSER_PROXY_URL` environment variable is required for the validator. It should point to a local GOST proxy on port 8088 (see `/home/skaiself/repo/dockerproxy/`). iHerb blocks server IPs directly (403), the local GOST proxy forwards through residential proxies for browser-based validation. No paid Web Unblocker proxy is needed — the pipeline uses browser-only validation.

### Pipeline flow

1. **Researcher** scrapes web sources (CouponFollow, HotDeals, Reddit, Generic) → writes discovered codes to `site/data/research.json` (status: `pending`)
2. **Validator (Browser-only)** tests codes via Playwright through local GOST proxy (port 8088):
   - **Phase 1:** All pending + active codes tested in US only (~45s each) — quick filter
   - **Phase 2:** Codes that pass US → tested across all 21 regions (launches fresh browser per region)
   - Adds items from checkout.iherb.com "Recommended for you" (same-domain session persistence) → applies coupon → extracts discount amount and regional eligibility
   - Writes valid codes to `site/data/coupons.json` and updates `research.json` statuses
3. **Orchestrator** commits data changes to GitHub → triggers Cloudflare Pages rebuild

The orchestrator runs on a randomized schedule (to avoid bot detection):
- **2x daily** — research + validate + git push (random times within 5:00-11:00 and 15:00-21:00 UTC windows)
- **9:00, 13:00, 18:00 UTC** — post to Twitter/X
- **Tue & Fri 10:00 UTC** — post to Reddit
- **Every hour** — update dashboard stats

**Supported regions (21):** US, KR, JP, DE, GB, AU, SA, CA, CN, RS, HR, IT, FR, AT, NL, SE, CH, IE, TW, IN, HK

## Troubleshooting

### Browser validation region issues

- **Working regions:** US, KR, JP, DE, GB, AU, SA, CA, CN, RS, HR, IT, FR, AT, NL, SE, CH, IE, TW, IN, HK (21 regions)
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
