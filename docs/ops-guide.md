# anyadeals Operations Guide

## Architecture

```
Host machine (always-on server)
├── Docker services (docker-compose)
│   ├── orchestrator :8080  — schedules scraping, validation, posting
│   ├── researcher   :8001  — scrapes coupon sources
│   ├── validator    :8002  — browser-validates codes via Playwright
│   └── poster       :8003  — generates images, posts to Twitter/Reddit
│
├── Systemd timers (host-side AI)
│   ├── anyadeals-research.timer  — parses scraped codes with Claude CLI
│   └── anyadeals-poster.timer    — generates social copy with Claude CLI
│
└── Logrotate
    └── /var/log/anyadeals/*.log  — 30-day retention
```

**Key insight:** Claude CLI cannot run inside Docker (root restriction). AI work runs on the host via systemd timers, calling service APIs for data exchange.

## Docker Services

### Start/stop all services

```bash
docker compose up -d          # start all
docker compose down           # stop all
docker compose restart        # restart all
```

### Rebuild after code changes

```bash
docker compose build researcher poster orchestrator
docker compose up -d researcher poster orchestrator
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
docker compose logs researcher | grep ERROR
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
./scripts/cron-research.sh          # run research parse now
./scripts/cron-poster.sh twitter    # generate twitter copy now
```

### Check timer logs

```bash
cat /var/log/anyadeals/cron-research.log
cat /var/log/anyadeals/cron-poster.log
journalctl -u anyadeals-research.service --since today
journalctl -u anyadeals-poster.service --since today
```

## Timer Schedule

| Timer | Schedule (UTC) | Purpose |
|---|---|---|
| `anyadeals-research.timer` | 07:00, 19:00 | Parse scraped codes with Claude CLI |
| `anyadeals-poster.timer` | 08:30, 12:30, 17:30 | Generate social copy with Claude CLI |

Poster timers run 30 minutes before the orchestrator's Twitter posting schedule (09:00, 13:00, 18:00 UTC) so AI copy is ready.

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
| `coupons.json` | All coupons with validation status |
| `research.json` | Raw research data from scrapers |
| `raw_codes.json` | Latest scrape output (for AI parsing) |
| `ai_copy.json` | Staged AI copy (consumed by next post run) |
| `dashboard.json` | Pipeline status for dashboard |
| `posts.json` | Log of all social media posts |
| `posts/*.png` | Generated post images |

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
