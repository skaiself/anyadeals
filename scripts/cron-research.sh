#!/usr/bin/env bash
# Cron job: fetch raw scraped codes, parse with Claude CLI, post results back.
# Runs on the host (not inside Docker). Logs to /var/log/anyadeals/cron-research.log.
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

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
