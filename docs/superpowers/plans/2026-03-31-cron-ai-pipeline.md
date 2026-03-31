# Cron-Based AI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move AI processing (coupon parsing + social copy generation) out of Docker and into host-side cron scripts that call Claude Code CLI, using new API endpoints on the existing services.

**Architecture:** Services expose raw data endpoints (`GET /raw-codes`, `GET /best-coupon`) and accept AI results (`POST /parsed-codes`, `POST /copy`). Orchestrator proxies `/api/*` to internal services. Two cron scripts on the host call Claude CLI for AI work and POST results back. Existing fallback paths remain unchanged.

**Tech Stack:** Python/FastAPI (services), Bash/curl/Claude CLI (cron scripts), logrotate (log management)

---

## File Structure

| File | Responsibility |
|---|---|
| `services/researcher/server.py` | **Modify** — add `GET /raw-codes` and `POST /parsed-codes` endpoints |
| `services/poster/server.py` | **Modify** — add `GET /best-coupon` and `POST /copy` endpoints |
| `services/orchestrator/server.py` | **Modify** — add `/api/*` proxy routes |
| `scripts/cron-research.sh` | **Create** — host cron script for AI research parsing |
| `scripts/cron-poster.sh` | **Create** — host cron script for AI copy generation |
| `deploy/logrotate-anyadeals` | **Create** — logrotate config (30-day retention) |
| `services/researcher/tests/test_server.py` | **Create** — tests for new researcher endpoints |
| `services/poster/tests/test_server.py` | **Modify** — add tests for new poster endpoints |
| `services/orchestrator/tests/test_server.py` | **Modify** — add tests for proxy routes |

---

### Task 1: Researcher — `GET /raw-codes` endpoint

**Files:**
- Modify: `services/researcher/server.py`
- Create: `services/researcher/tests/test_server.py`

This endpoint returns the latest raw scraped entries stored in the research data directory. It reads whatever was last scraped by the researcher's `/run` endpoint and returns the raw entries for external AI parsing.

- [ ] **Step 1: Write the failing test**

Create `services/researcher/tests/test_server.py`:

```python
import json
import os
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def data_dir(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_get_raw_codes_returns_latest_entries(data_dir):
    raw = [
        {"code": "GOLD60", "source": "retailmenot", "raw_description": "20% off $60+"},
        {"code": "WELLNESS2026", "source": "couponbirds", "raw_description": "15% off wellness"},
    ]
    (data_dir / "raw_codes.json").write_text(json.dumps(raw))

    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raw-codes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["code"] == "GOLD60"


@pytest.mark.asyncio
async def test_get_raw_codes_returns_empty_when_no_file(data_dir):
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raw-codes")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_raw_codes_limits_to_50(data_dir):
    raw = [{"code": f"CODE{i}", "source": "test", "raw_description": ""} for i in range(80)]
    (data_dir / "raw_codes.json").write_text(json.dumps(raw))

    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raw-codes")
    assert resp.status_code == 200
    assert len(resp.json()) == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/researcher && python -m pytest tests/test_server.py -v`
Expected: FAIL — `GET /raw-codes` route does not exist (404)

- [ ] **Step 3: Write the endpoint**

Add to `services/researcher/server.py`, after the existing `/run` endpoint:

```python
@app.get("/raw-codes")
def get_raw_codes():
    """Return latest raw scraped entries for external AI parsing."""
    raw_path = os.path.join(DATA_DIR, "raw_codes.json")
    if not os.path.exists(raw_path):
        return []
    with open(raw_path) as f:
        raw = json.load(f)
    return raw[:50]
```

Also update the `/run` endpoint to **save raw codes to `raw_codes.json`** before parsing. Add these lines after the `raw_codes = await run_all_scrapers()` line:

```python
        # Save raw codes for external AI processing
        raw_path = os.path.join(DATA_DIR, "raw_codes.json")
        import json as _json
        os.makedirs(os.path.dirname(raw_path) or ".", exist_ok=True)
        with open(raw_path, "w") as f:
            _json.dump(raw_codes[:50], f, indent=2, default=str)
```

Note: `json` is already imported at the top of server.py, so use it directly (the `import json as _json` is just to show it clearly — use the existing `json` import).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/researcher && python -m pytest tests/test_server.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/researcher/server.py services/researcher/tests/test_server.py
git commit -m "feat(researcher): add GET /raw-codes endpoint for external AI parsing"
```

---

### Task 2: Researcher — `POST /parsed-codes` endpoint

**Files:**
- Modify: `services/researcher/server.py`
- Modify: `services/researcher/tests/test_server.py`

This endpoint accepts AI-parsed coupon data and merges it into `research.json` using the existing `merge_research` function.

- [ ] **Step 1: Write the failing test**

Add to `services/researcher/tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_post_parsed_codes_merges_into_research(data_dir):
    existing = [{"code": "OLD1", "source": "test", "raw_description": "old"}]
    (data_dir / "research.json").write_text(json.dumps(existing))

    new_codes = [
        {"code": "GOLD60", "source": "retailmenot", "raw_description": "20% off $60+",
         "discount_type": "percentage", "discount_value": 20, "regions": ["us"],
         "discovered_at": "2026-03-31T00:00:00Z", "raw_context": "",
         "expiry_date": None, "confidence": "high", "validation_status": "pending"},
    ]

    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/parsed-codes", json=new_codes)
    assert resp.status_code == 200
    data = resp.json()
    assert data["merged_total"] == 2

    research = json.loads((data_dir / "research.json").read_text())
    codes = [r["code"] for r in research]
    assert "OLD1" in codes
    assert "GOLD60" in codes


@pytest.mark.asyncio
async def test_post_parsed_codes_rejects_non_list(data_dir):
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/parsed-codes", json={"not": "a list"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/researcher && python -m pytest tests/test_server.py::test_post_parsed_codes_merges_into_research -v`
Expected: FAIL — `POST /parsed-codes` route does not exist (404 or 405)

- [ ] **Step 3: Write the endpoint**

Add to `services/researcher/server.py`:

```python
from fastapi import FastAPI, HTTPException, Request


@app.post("/parsed-codes")
async def post_parsed_codes(request: Request):
    """Accept AI-parsed codes and merge into research.json."""
    body = await request.json()
    if not isinstance(body, list):
        raise HTTPException(status_code=422, detail="Expected a JSON array")

    from json_writer import load_research_json, merge_research, write_research_json

    research_path = os.path.join(DATA_DIR, "research.json")
    existing = load_research_json(research_path)
    merged = merge_research(existing, body)
    write_research_json(merged, research_path)

    return {"status": "ok", "merged_total": len(merged)}
```

Update the existing `from fastapi import FastAPI, HTTPException` at the top of the file to also import `Request`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/researcher && python -m pytest tests/test_server.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/researcher/server.py services/researcher/tests/test_server.py
git commit -m "feat(researcher): add POST /parsed-codes endpoint for AI result ingestion"
```

---

### Task 3: Poster — `GET /best-coupon` endpoint

**Files:**
- Modify: `services/poster/server.py`
- Modify: `services/poster/tests/test_server.py`

Returns the top coupon (most recently validated, status=valid) from `coupons.json`.

- [ ] **Step 1: Write the failing test**

Add to `services/poster/tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_get_best_coupon_returns_most_recently_validated(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [
        {"code": "OLD1", "status": "valid", "last_validated": "2026-03-28T00:00:00Z",
         "discount": "10% off"},
        {"code": "GOLD60", "status": "valid", "last_validated": "2026-03-31T00:00:00Z",
         "discount": "20% off $60+"},
        {"code": "EXPIRED1", "status": "expired", "last_validated": "2026-03-31T12:00:00Z",
         "discount": "5% off"},
    ]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/best-coupon")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "GOLD60"


@pytest.mark.asyncio
async def test_get_best_coupon_returns_404_when_no_valid(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [{"code": "EXP1", "status": "expired", "last_validated": "2026-03-01T00:00:00Z"}]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/best-coupon")
    assert resp.status_code == 404
```

Add `import os` and `import json` at the top of the test file if not already present.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/poster && python -m pytest tests/test_server.py::test_get_best_coupon_returns_most_recently_validated -v`
Expected: FAIL — `GET /best-coupon` route does not exist

- [ ] **Step 3: Write the endpoint**

Add to `services/poster/server.py`:

```python
@app.get("/best-coupon")
def get_best_coupon():
    """Return the top valid coupon (most recently validated)."""
    coupons_path = os.path.join(DATA_DIR, "coupons.json")
    if not os.path.exists(coupons_path):
        raise HTTPException(status_code=404, detail="No coupons file found")
    with open(coupons_path) as f:
        coupons = json.load(f)
    valid = [c for c in coupons if c.get("status") == "valid"]
    if not valid:
        raise HTTPException(status_code=404, detail="No valid coupons")
    best = max(valid, key=lambda c: c.get("last_validated", ""))
    return best
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/poster && python -m pytest tests/test_server.py -v`
Expected: All tests PASS (existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add services/poster/server.py services/poster/tests/test_server.py
git commit -m "feat(poster): add GET /best-coupon endpoint"
```

---

### Task 4: Poster — `POST /copy` endpoint

**Files:**
- Modify: `services/poster/server.py`
- Modify: `services/poster/tests/test_server.py`

Accepts AI-generated copy text and triggers social media posting for a specific coupon and platform.

- [ ] **Step 1: Write the failing test**

Add to `services/poster/tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_post_copy_stores_and_returns_success(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [
        {"code": "GOLD60", "status": "valid", "last_validated": "2026-03-31T00:00:00Z",
         "discount": "20% off $60+"},
    ]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))
    (tmp_path / "posts.json").write_text("[]")

    from server import state
    state["running"] = False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/copy", json={
            "coupon_code": "GOLD60",
            "copy_text": "Save 20% at iHerb with GOLD60! Stack with OFR0296. #iHerb #deals",
            "platform": "twitter",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["coupon_code"] == "GOLD60"


@pytest.mark.asyncio
async def test_post_copy_rejects_unknown_coupon(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [{"code": "GOLD60", "status": "valid", "last_validated": "2026-03-31T00:00:00Z"}]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/copy", json={
            "coupon_code": "NONEXISTENT",
            "copy_text": "Some copy",
            "platform": "twitter",
        })
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/poster && python -m pytest tests/test_server.py::test_post_copy_stores_and_returns_success -v`
Expected: FAIL — `POST /copy` route does not exist

- [ ] **Step 3: Write the endpoint**

Add to `services/poster/server.py`:

```python
from pydantic import BaseModel


class CopyRequest(BaseModel):
    coupon_code: str
    copy_text: str
    platform: str = "twitter"


@app.post("/copy")
async def post_copy(req: CopyRequest):
    """Accept AI-generated copy and trigger posting for a coupon."""
    coupons_path = os.path.join(DATA_DIR, "coupons.json")
    if not os.path.exists(coupons_path):
        raise HTTPException(status_code=404, detail="No coupons file")
    with open(coupons_path) as f:
        coupons = json.load(f)

    coupon = next((c for c in coupons if c["code"] == req.coupon_code), None)
    if not coupon:
        raise HTTPException(status_code=404, detail=f"Coupon {req.coupon_code} not found")

    # Store the AI copy for pickup by the next scheduled posting run
    copy_path = os.path.join(DATA_DIR, "ai_copy.json")
    copy_data = {
        "coupon_code": req.coupon_code,
        "copy_text": req.copy_text,
        "platform": req.platform,
    }
    with open(copy_path, "w") as f:
        json.dump(copy_data, f, indent=2)

    return {"status": "accepted", "coupon_code": req.coupon_code, "platform": req.platform}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/poster && python -m pytest tests/test_server.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/poster/server.py services/poster/tests/test_server.py
git commit -m "feat(poster): add POST /copy endpoint for AI-generated copy"
```

---

### Task 5: Poster — use stored AI copy in `/run`

**Files:**
- Modify: `services/poster/server.py`
- Modify: `services/poster/tests/test_server.py`

Update the existing `/run` endpoint to check for stored AI copy before falling back to template generation.

- [ ] **Step 1: Write the failing test**

Add to `services/poster/tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_run_uses_stored_ai_copy(tmp_path, monkeypatch):
    os.environ["DATA_DIR"] = str(tmp_path)
    coupons = [
        {"code": "GOLD60", "status": "valid", "last_validated": "2026-03-31T00:00:00Z",
         "discount": "20% off $60+"},
    ]
    (tmp_path / "coupons.json").write_text(json.dumps(coupons))
    (tmp_path / "posts.json").write_text("[]")
    ai_copy = {
        "coupon_code": "GOLD60",
        "copy_text": "AI generated copy for GOLD60!",
        "platform": "twitter",
    }
    (tmp_path / "ai_copy.json").write_text(json.dumps(ai_copy))

    # Mock out the actual posting and image generation
    monkeypatch.setattr("copy_generator.generate_copy", lambda c: "fallback")
    monkeypatch.setattr("image_generator.generate_image", lambda c: None)

    from server import state, app
    state["running"] = False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/run?platform=twitter")
    data = resp.json()
    assert data["status"] == "success"

    # Verify ai_copy.json was consumed (deleted)
    assert not (tmp_path / "ai_copy.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/poster && python -m pytest tests/test_server.py::test_run_uses_stored_ai_copy -v`
Expected: FAIL — `/run` doesn't check for `ai_copy.json`

- [ ] **Step 3: Update `/run` to check for stored AI copy**

In `services/poster/server.py`, in the `run_posting` function, replace the copy generation section. After the `best = max(...)` line, replace:

```python
        from copy_generator import generate_copy
        copy_text = await generate_copy(best)
```

With:

```python
        # Check for AI-generated copy (from cron scripts via POST /copy)
        ai_copy_path = os.path.join(DATA_DIR, "ai_copy.json")
        copy_text = None
        if os.path.exists(ai_copy_path):
            try:
                with open(ai_copy_path) as f:
                    ai_copy = json.load(f)
                if ai_copy.get("coupon_code") == best["code"]:
                    copy_text = ai_copy["copy_text"]
                    logger.info("Using AI-generated copy for %s", best["code"])
                os.remove(ai_copy_path)
            except Exception as e:
                logger.warning("Failed to read ai_copy.json: %s", e)

        if not copy_text:
            from copy_generator import generate_copy
            copy_text = await generate_copy(best)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/poster && python -m pytest tests/test_server.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/poster/server.py services/poster/tests/test_server.py
git commit -m "feat(poster): use stored AI copy in /run before fallback"
```

---

### Task 6: Orchestrator — proxy `/api/*` routes

**Files:**
- Modify: `services/orchestrator/server.py`
- Modify: `services/orchestrator/tests/test_server.py`

The orchestrator proxies `/api/*` requests to internal services so only port 8080 needs to be exposed.

- [ ] **Step 1: Write the failing test**

Add to `services/orchestrator/tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_api_raw_codes_proxies_to_researcher(monkeypatch):
    import httpx

    async def mock_get(self, url, **kwargs):
        resp = httpx.Response(200, json=[{"code": "GOLD60"}])
        return resp

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATA_DIR", "/tmp")
        from server import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/raw-codes")
        assert resp.status_code == 200
        assert resp.json() == [{"code": "GOLD60"}]


@pytest.mark.asyncio
async def test_api_best_coupon_proxies_to_poster(monkeypatch):
    import httpx

    async def mock_get(self, url, **kwargs):
        resp = httpx.Response(200, json={"code": "GOLD60", "discount": "20% off"})
        return resp

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATA_DIR", "/tmp")
        from server import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/best-coupon")
        assert resp.status_code == 200
        assert resp.json()["code"] == "GOLD60"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/orchestrator && python -m pytest tests/test_server.py::test_api_raw_codes_proxies_to_researcher -v`
Expected: FAIL — `GET /api/raw-codes` does not exist (404)

- [ ] **Step 3: Write the proxy routes**

Add to `services/orchestrator/server.py`:

```python
import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

RESEARCHER_URL = "http://researcher:8001"
POSTER_URL = "http://poster:8003"

API_ROUTES = {
    "raw-codes": {"service": RESEARCHER_URL, "path": "/raw-codes"},
    "parsed-codes": {"service": RESEARCHER_URL, "path": "/parsed-codes"},
    "best-coupon": {"service": POSTER_URL, "path": "/best-coupon"},
    "copy": {"service": POSTER_URL, "path": "/copy"},
}


@app.api_route("/api/{endpoint}", methods=["GET", "POST"])
async def api_proxy(endpoint: str, request: Request):
    """Proxy /api/* requests to internal services."""
    route = API_ROUTES.get(endpoint)
    if not route:
        return JSONResponse(status_code=404, content={"detail": f"Unknown endpoint: {endpoint}"})

    url = f"{route['service']}{route['path']}"
    async with httpx.AsyncClient(timeout=300) as client:
        if request.method == "GET":
            resp = await client.get(url)
        else:
            body = await request.body()
            resp = await client.post(url, content=body, headers={"content-type": "application/json"})

    return JSONResponse(status_code=resp.status_code, content=resp.json())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/orchestrator && python -m pytest tests/test_server.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/orchestrator/server.py services/orchestrator/tests/test_server.py
git commit -m "feat(orchestrator): add /api/* proxy routes to internal services"
```

---

### Task 7: Cron script — `cron-research.sh`

**Files:**
- Create: `scripts/cron-research.sh`

Fetches raw scraped codes from the API, sends them to Claude CLI for parsing, posts results back.

- [ ] **Step 1: Create the script**

Create `scripts/cron-research.sh`:

```bash
#!/usr/bin/env bash
# Cron job: fetch raw scraped codes, parse with Claude CLI, post results back.
# Runs on the host (not inside Docker). Logs to /var/log/anyadeals/cron-research.log.
set -euo pipefail

API_BASE="http://localhost:8080/api"
LOG_DIR="/var/log/anyadeals"
LOG_FILE="${LOG_DIR}/cron-research.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date -Iseconds)] $*" >> "$LOG_FILE"; }

log "=== Research parse started ==="

# Step 1: Fetch raw codes
RAW=$(curl -sf "${API_BASE}/raw-codes" 2>>"$LOG_FILE") || {
    log "ERROR: Failed to fetch raw codes from API"
    exit 1
}

COUNT=$(echo "$RAW" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
log "Fetched ${COUNT} raw codes"

if [ "$COUNT" = "0" ]; then
    log "No raw codes to parse, exiting"
    exit 0
fi

# Step 2: Parse with Claude CLI
PROMPT="You are a coupon code analyst. Parse these raw iHerb coupon entries and return a JSON array of deduplicated codes with fields: code (uppercase), source, discovered_at (ISO), raw_description, raw_context, discount_type (percentage|fixed|free_shipping|unknown), discount_value (number), regions (array), expiry_date (ISO or null), confidence (high|medium|low), validation_status (pending). Deduplicate by code. Filter non-codes. Return ONLY the JSON array.

Raw data:
${RAW}"

PARSED=$(claude -p "$PROMPT" --model haiku --output-format json 2>>"$LOG_FILE") || {
    log "ERROR: Claude CLI failed"
    exit 1
}

# Extract the result field from Claude's JSON wrapper
RESULT=$(echo "$PARSED" | python3 -c "
import sys, json, re
data = json.load(sys.stdin)
content = data.get('result', '') if isinstance(data, dict) else json.dumps(data)
if isinstance(content, str):
    m = re.search(r'\[.*\]', content, re.DOTALL)
    print(m.group() if m else '[]')
elif isinstance(content, list):
    print(json.dumps(content))
else:
    print('[]')
" 2>/dev/null) || {
    log "ERROR: Failed to extract JSON from Claude output"
    exit 1
}

PARSED_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
log "Claude parsed ${PARSED_COUNT} codes"

# Step 3: Post results back
RESP=$(curl -sf -X POST "${API_BASE}/parsed-codes" \
    -H "Content-Type: application/json" \
    -d "$RESULT" 2>>"$LOG_FILE") || {
    log "ERROR: Failed to post parsed codes"
    exit 1
}

log "Posted results: ${RESP}"
log "=== Research parse complete ==="
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/cron-research.sh
```

- [ ] **Step 3: Test manually**

Run: `./scripts/cron-research.sh`
Check: `cat /var/log/anyadeals/cron-research.log`
Expected: Log entries showing fetch, parse, and post steps (may fail if services are not rebuilt yet — that's fine, confirms the script runs)

- [ ] **Step 4: Commit**

```bash
git add scripts/cron-research.sh
git commit -m "feat: add cron-research.sh for host-side AI parsing"
```

---

### Task 8: Cron script — `cron-poster.sh`

**Files:**
- Create: `scripts/cron-poster.sh`

Fetches the best coupon, generates copy with Claude CLI, posts it back to the service.

- [ ] **Step 1: Create the script**

Create `scripts/cron-poster.sh`:

```bash
#!/usr/bin/env bash
# Cron job: fetch best coupon, generate copy with Claude CLI, post back.
# Runs on the host (not inside Docker). Logs to /var/log/anyadeals/cron-poster.log.
set -euo pipefail

API_BASE="http://localhost:8080/api"
LOG_DIR="/var/log/anyadeals"
LOG_FILE="${LOG_DIR}/cron-poster.log"
PLATFORM="${1:-twitter}"
mkdir -p "$LOG_DIR"

log() { echo "[$(date -Iseconds)] $*" >> "$LOG_FILE"; }

log "=== Copy generation started (platform: ${PLATFORM}) ==="

# Step 1: Fetch best coupon
COUPON=$(curl -sf "${API_BASE}/best-coupon" 2>>"$LOG_FILE") || {
    log "ERROR: Failed to fetch best coupon (maybe none valid)"
    exit 1
}

CODE=$(echo "$COUPON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('code',''))" 2>/dev/null)
DISCOUNT=$(echo "$COUPON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('discount',''))" 2>/dev/null)
log "Best coupon: ${CODE} (${DISCOUNT})"

if [ -z "$CODE" ]; then
    log "No coupon code found, exiting"
    exit 0
fi

# Step 2: Generate copy with Claude CLI
PROMPT="Write a short, engaging social media post promoting this iHerb coupon code.

Coupon: ${CODE}
Discount: ${DISCOUNT}
Referral code to stack: OFR0296
Link: https://anyadeals.com/coupons/iherb/

Requirements:
- Under 250 characters for Twitter
- Engaging, casual tone
- Include the coupon code prominently
- Mention stacking with referral code OFR0296
- Include 2-3 relevant hashtags
- No emojis unless they add value
- Return ONLY the post text, nothing else"

COPY=$(claude -p "$PROMPT" --model haiku --output-format text 2>>"$LOG_FILE") || {
    log "ERROR: Claude CLI failed"
    exit 1
}

log "Generated copy: ${COPY:0:80}..."

# Step 3: Post copy back to service
PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
    'coupon_code': sys.argv[1],
    'copy_text': sys.argv[2],
    'platform': sys.argv[3]
}))
" "$CODE" "$COPY" "$PLATFORM" 2>/dev/null)

RESP=$(curl -sf -X POST "${API_BASE}/copy" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>>"$LOG_FILE") || {
    log "ERROR: Failed to post copy"
    exit 1
}

log "Posted copy: ${RESP}"
log "=== Copy generation complete ==="
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/cron-poster.sh
```

- [ ] **Step 3: Test manually**

Run: `./scripts/cron-poster.sh twitter`
Check: `cat /var/log/anyadeals/cron-poster.log`
Expected: Log entries showing fetch, generate, and post steps

- [ ] **Step 4: Commit**

```bash
git add scripts/cron-poster.sh
git commit -m "feat: add cron-poster.sh for host-side AI copy generation"
```

---

### Task 9: Logrotate config + crontab

**Files:**
- Create: `deploy/logrotate-anyadeals`

- [ ] **Step 1: Create logrotate config**

Create `deploy/logrotate-anyadeals`:

```
/var/log/anyadeals/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
```

- [ ] **Step 2: Create crontab reference file**

Create `deploy/crontab-anyadeals`:

```
# anyadeals AI pipeline cron jobs
# Install with: crontab -l | cat - deploy/crontab-anyadeals | crontab -

# Research parsing: 2x/day at 07:00 and 19:00 UTC
0 7,19 * * * /home/skaiself/repo/anyadeals/scripts/cron-research.sh

# Twitter copy generation: 3x/day, 30min before scheduled posting (9/13/18)
30 8,12,17 * * * /home/skaiself/repo/anyadeals/scripts/cron-poster.sh twitter
```

- [ ] **Step 3: Commit**

```bash
git add deploy/logrotate-anyadeals deploy/crontab-anyadeals
git commit -m "feat: add logrotate config and crontab reference"
```

- [ ] **Step 4: Install logrotate config and crontab**

```bash
sudo cp deploy/logrotate-anyadeals /etc/logrotate.d/anyadeals
crontab -l 2>/dev/null | cat - deploy/crontab-anyadeals | crontab -
```

Verify: `crontab -l` should show the new entries.
Verify: `logrotate --debug /etc/logrotate.d/anyadeals` should show the config is valid.

- [ ] **Step 5: Commit any adjustments**

If paths needed adjustment during install, update the files and commit.

---

### Task 10: Rebuild Docker services + end-to-end test

**Files:** None new — integration verification only.

- [ ] **Step 1: Rebuild Docker services**

```bash
docker compose build researcher poster orchestrator
docker compose up -d researcher poster orchestrator
```

- [ ] **Step 2: Verify new endpoints are live**

```bash
# Researcher endpoints
curl -s http://localhost:8080/api/raw-codes | python3 -m json.tool | head -5

# Poster endpoint
curl -s http://localhost:8080/api/best-coupon | python3 -m json.tool

# Proxy health
curl -s http://localhost:8080/status
```

- [ ] **Step 3: Run cron-research.sh end-to-end**

```bash
./scripts/cron-research.sh
cat /var/log/anyadeals/cron-research.log
```

Expected: Successful fetch, Claude parse, and POST back.

- [ ] **Step 4: Run cron-poster.sh end-to-end**

```bash
./scripts/cron-poster.sh twitter
cat /var/log/anyadeals/cron-poster.log
```

Expected: Successful fetch, Claude copy generation, and POST back.

- [ ] **Step 5: Verify poster picks up AI copy**

```bash
# Check ai_copy.json was created
cat /data/ai_copy.json 2>/dev/null || cat site/data/ai_copy.json

# Trigger a posting run
curl -s -X POST http://localhost:8080/trigger/post | python3 -m json.tool
```

Expected: Poster logs show "Using AI-generated copy" instead of fallback.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: cron-based AI pipeline complete — end-to-end verified"
git push origin master
```
