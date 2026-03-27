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

The `PROXY_URL` environment variable is required for the validator to test coupons against iHerb. It should point to an IPRoyal Web Unblocker proxy (or similar). Without it, validation will fail with connection errors.

### Pipeline flow

1. **Researcher** scrapes web sources → writes discovered codes to `site/data/research.json` (status: `pending`)
2. **Validator** reads pending codes from `research.json` + any static codes from `config.json` → tests each against iHerb checkout → writes valid codes to `site/data/coupons.json` and updates `research.json` statuses
3. **Orchestrator** commits data changes to GitHub → triggers Cloudflare Pages rebuild

The orchestrator runs on a schedule:
- **6:00 & 18:00 UTC** — research + validate + git push
- **12:00 UTC** — re-validate existing codes
- **9:00, 13:00, 18:00 UTC** — post to Twitter/X
- **Tue & Fri 10:00 UTC** — post to Reddit
- **Every hour** — update dashboard stats

## Troubleshooting

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
