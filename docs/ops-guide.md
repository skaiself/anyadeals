# anyadeals Operations Guide

## Architecture

```
Host machine (always-on server, CachyOS)
├── Docker services (docker-compose, user 1000:1000)
│   ├── orchestrator :8080  — schedules scraping, validation, posting
│   ├── researcher   :8001  — scrapes coupon sources
│   ├── validator    :8002  — browser-validates codes via Playwright
│   └── poster       :8003  — generates images, posts to Twitter/Reddit
│
├── Systemd timers (host-side AI — uses Claude subscription, zero API cost)
│   ├── anyadeals-research.timer  — parses scraped codes with Claude CLI (haiku)
│   └── anyadeals-poster.timer    — generates social copy with Claude CLI (haiku)
│
├── GOST proxy (port 8088) — used by validator for browser validation
│
└── Logrotate
    └── /var/log/anyadeals/*.log  — 30-day retention
```

**Key insight:** Claude CLI cannot run inside Docker (root restriction). AI work runs on the host via systemd timers, calling service APIs for data exchange.

## Overnight Pipeline

The pipeline runs sequentially overnight to avoid iHerb rate limiting:

```
01:00─02:00 UTC   Scrape (researcher, ~10 min)
      ↓
02:30─03:30 UTC   AI Parse (Claude CLI haiku, ~2 min)
      ↓
04:00─07:00 UTC   Validate (Playwright browser, ~30-90 min)
```

Each step runs at a random time within its window. No overlap between steps.

| Step | Window (UTC) | Runs Where | What It Does |
|---|---|---|---|
| 1. Scrape | 01:00-02:00 | Docker (researcher) | Scrapes coupon sites, saves raw_codes.json |
| 2. AI Parse | 02:30-03:30 | Host (systemd timer) | Claude CLI parses raw codes into research.json |
| 3. Validate | 04:00-07:00 | Docker (validator) | Browser-tests 5-8 random regions, updates coupons.json |

### Other Scheduled Jobs

| Job | Schedule (UTC) | Description |
|---|---|---|
| Twitter posting | 09:00, 13:00, 18:00 | Posts best coupon with AI copy + Pillow image |
| Reddit posting | Tue & Fri 10:00 | Posts best coupon to Reddit |
| AI copy generation | 08:30, 12:30, 17:30 | Claude CLI generates tweet copy (systemd timer) |
| Dashboard check | Hourly (:00) | Recalculates stats, pushes only on change |

## Docker Services

### Start/stop all services

```bash
docker compose up -d          # start all
docker compose down           # stop all
docker compose restart        # restart all
```

### Rebuild after code changes

```bash
docker compose build researcher poster orchestrator validator
docker compose up -d
```

### Check status

```bash
docker compose ps                              # container status
curl -s http://localhost:8080/status            # orchestrator health
curl -s http://localhost:8080/jobs              # scheduled jobs
curl -s http://localhost:8080/dashboard         # HTML dashboard
```

### View logs

```bash
docker compose logs -f orchestrator    # follow orchestrator logs
docker compose logs --tail=50 poster   # last 50 poster log lines
docker compose logs validator | grep -i "error\|valid\|phase"
```

### Manual triggers

```bash
curl -X POST http://localhost:8080/trigger/research   # scrape now
curl -X POST http://localhost:8080/trigger/validate   # validate now
curl -X POST http://localhost:8080/trigger/post       # post now
```

## Systemd Timers (AI Pipeline)

### Check timer status

```bash
systemctl list-timers | grep anyadeals
```

### Stop timers

```bash
sudo systemctl stop anyadeals-research.timer anyadeals-poster.timer
```

### Start timers

```bash
sudo systemctl start anyadeals-research.timer anyadeals-poster.timer
```

### Disable timers (persist across reboot)

```bash
sudo systemctl disable anyadeals-research.timer anyadeals-poster.timer
```

### Re-enable timers

```bash
sudo systemctl enable --now anyadeals-research.timer anyadeals-poster.timer
```

### Run manually (one-off)

```bash
./scripts/cron-research.sh          # run AI parse now
./scripts/cron-poster.sh twitter    # generate twitter copy now
```

### Check timer logs

```bash
cat /var/log/anyadeals/cron-research.log
cat /var/log/anyadeals/cron-poster.log
journalctl -u anyadeals-research.service --since today
journalctl -u anyadeals-poster.service --since today
```

## Validation Details

- Runs 1x/day overnight (04:00-07:00 UTC window)
- Tests 5-8 random regions per run (always includes US)
- Over several days, all 21 regions get covered
- **3 consecutive failures** required before marking a coupon invalid
- fail_count resets to 0 on any successful validation
- Does not overwrite existing discount values or notes

### 21 Supported Regions

US, KR, JP, DE, GB, AU, SA, CA, CN, RS, HR, IT, FR, AT, NL, SE, CH, IE, TW, IN, HK

## Notes Pipeline

Coupon notes (brand restrictions, min order, etc.) flow automatically:

1. Claude CLI generates `notes` field when parsing raw codes
2. Notes stored in research.json
3. Validator copies notes to coupons.json for new/empty-notes coupons
4. Existing manually-curated notes are never overwritten

## API Endpoints

All accessible through orchestrator proxy on port 8080.

| Endpoint | Method | Description |
|---|---|---|
| `/api/raw-codes` | GET | Latest raw scraped entries (up to 50) |
| `/api/parsed-codes` | POST | Submit AI-parsed codes for merging |
| `/api/best-coupon` | GET | Top valid coupon (most recently validated) |
| `/api/copy` | POST | Submit AI-generated copy for next post |
| `/status` | GET | Orchestrator health |
| `/jobs` | GET | Scheduled jobs with next run times |
| `/dashboard` | GET | HTML dashboard |
| `/trigger/{service}` | POST | Manually trigger: research, validate, post |

## Data Files

All in `site/data/`:

| File | Description |
|---|---|
| `coupons.json` | All coupons with validation status, discount, notes |
| `research.json` | Raw research data from scrapers + AI parsing |
| `raw_codes.json` | Latest scrape output (for AI parsing) |
| `ai_copy.json` | Staged AI copy (consumed by next post run) |
| `dashboard.json` | Pipeline status for dashboard (runtime state) |
| `posts.json` | Log of all social media posts |
| `posts/*.png` | Pillow-generated branded images (1080x1080) |

## Git Push Policy

Pushes to GitHub only happen when content files change:
- `coupons.json`, `research.json`, `raw_codes.json`, `posts.json`
- `dashboard.json` gets `last_deploy` timestamp set only at push time
- Hourly dashboard checks with no data changes do NOT push
- Each push triggers a Cloudflare Pages rebuild of anyadeals.com

## Log Rotation

Configured via `/etc/logrotate.d/anyadeals`:
- Daily rotation
- 30-day retention
- Compressed after 1 day
- Applies to `/var/log/anyadeals/*.log`

## Ports

| Port | Service |
|---|---|
| 8080 | Orchestrator (exposed to host) |
| 8001 | Researcher (internal only) |
| 8002 | Validator (internal only) |
| 8003 | Poster (internal only) |
| 8088 | GOST proxy (host, used by validator) |
