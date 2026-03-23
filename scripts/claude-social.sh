#!/usr/bin/env bash
# Wrapper for Claude CLI social copy generation.
# Usage: ./claude-social.sh "GOLD60" "20% off orders over $60"
set -euo pipefail

CODE="${1:?Usage: claude-social.sh CODE DISCOUNT}"
DISCOUNT="${2:?Usage: claude-social.sh CODE DISCOUNT}"

claude -p "Write a short engaging social media post for iHerb coupon ${CODE} (${DISCOUNT}). Stack with OFR0296. Link: https://anyadeals.com/coupons/iherb/ Under 250 chars. Include #iHerb hashtag." \
    --dangerously-skip-permissions \
    --model opus \
    --effort max \
    --output-format text
