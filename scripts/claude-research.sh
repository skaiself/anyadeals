#!/usr/bin/env bash
# Wrapper for Claude CLI research parsing.
# Usage: cat raw_codes.json | ./claude-research.sh
set -euo pipefail

INPUT=$(cat)
claude -p "Parse these iHerb coupon codes and return structured JSON: $INPUT" \
    --dangerously-skip-permissions \
    --model opus \
    --effort max \
    --output-format json
