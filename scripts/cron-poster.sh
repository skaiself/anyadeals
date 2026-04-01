#!/usr/bin/env bash
# Cron job: fetch best coupon, generate copy with Claude CLI, post back.
# Runs on the host (not inside Docker). Logs to /var/log/anyadeals/cron-poster.log.
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

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
