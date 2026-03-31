# Cron-Based AI Pipeline Design

**Date:** 2026-03-31
**Status:** Approved

## Problem

Claude CLI cannot run inside Docker containers (`--dangerously-skip-permissions` is blocked as root). Both the researcher (code parsing) and poster (copy generation) have been silently falling back to regex/template alternatives since deployment. The AI features have never actually worked in Docker.

## Solution

Invert the architecture: move AI processing out of Docker and into cron-triggered scripts that run Claude Code CLI on the host machine. Services expose new API endpoints to supply raw data and accept AI-processed results.

```
[cron on host] -> [claude CLI on host]
                     |              ^
              GET /raw-codes   POST /parsed-codes
              GET /best-coupon POST /copy
                     |              ^
              [Docker services (no AI)]
```

The existing orchestrator schedule (scraping, validation, template-based posting) continues unchanged. The cron scripts layer AI quality on top, with graceful degradation if they fail.

## New API Endpoints

All routed through orchestrator on port 8080.

### Researcher

| Endpoint | Method | Description |
|---|---|---|
| `/api/raw-codes` | GET | Returns latest raw scraped entries (up to 50) |
| `/api/parsed-codes` | POST | Accepts AI-parsed JSON array, merges into research.json |

### Poster

| Endpoint | Method | Description |
|---|---|---|
| `/api/best-coupon` | GET | Returns the top coupon (most recently validated) |
| `/api/copy` | POST | Accepts generated copy text + coupon code + platform, triggers posting |

### Orchestrator (proxy)

The orchestrator proxies `/api/*` requests to the appropriate internal service. No new ports exposed.

## Cron Scripts

### `scripts/cron-research.sh`

1. `curl GET http://localhost:8080/api/raw-codes` -> raw JSON
2. Pipe to `claude -p "parse these codes..." --model haiku --output-format json`
3. `curl POST http://localhost:8080/api/parsed-codes` with Claude's output

### `scripts/cron-poster.sh`

1. `curl GET http://localhost:8080/api/best-coupon` -> coupon JSON
2. Pipe to `claude -p "write a tweet..." --model haiku --output-format text`
3. `curl POST http://localhost:8080/api/copy` with generated text + platform

### Schedule

| Script | Cron | Rationale |
|---|---|---|
| `cron-research.sh` | `0 7,19 * * *` (2x/day) | After orchestrator's randomized scrape windows |
| `cron-poster.sh` | `30 8,12,17 * * *` (3x/day) | 30min before Twitter posting at 9/13/18, so AI copy is ready |

### Error handling

If Claude CLI fails (rate limit, network), scripts exit non-zero. The orchestrator's scheduled posting still fires using template copy. No data loss, no broken state.

## Service Changes

### Researcher

- `/run` continues to work but uses regex fallback only (no Claude CLI dependency)
- New `GET /raw-codes` endpoint returns latest scraped raw entries
- New `POST /parsed-codes` endpoint accepts parsed JSON and merges into research.json

### Poster

- Existing `/run` continues with template copy fallback
- New `GET /best-coupon` endpoint returns top coupon metadata
- New `POST /copy` endpoint accepts copy text and triggers actual social media posting

### Orchestrator

- New proxy routes: `/api/raw-codes`, `/api/parsed-codes`, `/api/best-coupon`, `/api/copy`
- Proxies to internal researcher (8001) and poster (8003) services

### No changes

- Validator service: unchanged
- Docker compose: unchanged (no new ports)
- Existing orchestrator schedule: unchanged

## Logging

Scripts log to `/var/log/anyadeals/`:
- `cron-research.log` — timestamped entries per run (raw count, parsed count, success/failure)
- `cron-poster.log` — timestamped entries per run (coupon code, platform, success/failure)

### Log rotation

Logrotate config at `/etc/logrotate.d/anyadeals`:
- Daily rotation
- Keep 30 days
- Compress after 1 day
- Auto-create log directory

## Files to Create

| File | Purpose |
|---|---|
| `scripts/cron-research.sh` | Host cron script for AI research parsing |
| `scripts/cron-poster.sh` | Host cron script for AI copy generation |
| `deploy/logrotate-anyadeals` | Logrotate config file |

## Files to Modify

| File | Change |
|---|---|
| `services/researcher/server.py` | Add `GET /raw-codes` and `POST /parsed-codes` endpoints |
| `services/poster/server.py` | Add `GET /best-coupon` and `POST /copy` endpoints |
| `services/orchestrator/server.py` | Add `/api/*` proxy routes to researcher and poster |

## Cost Impact

- Zero API token cost — all AI runs through Claude Code CLI on the host (subscription)
- Model: haiku (cheapest, sufficient for these tasks)
- No `--effort max` (no extended thinking overhead)
