# AI Cost Reduction Design

**Date:** 2026-03-30
**Status:** Approved

## Problem

Both `researcher` and `poster` services call Claude CLI with `--model opus --effort max` — the most expensive configuration. `--effort max` triggers extended thinking, multiplying token usage. For the actual tasks (JSON extraction and tweet writing), this is extreme overkill.

**Current call volume:** ~5 Claude opus calls/day (2 research parses + 3 Twitter + ~0.3 Reddit).

## Solution

Replace `--model opus --effort max` with `--model haiku` (no effort flag) in all 4 call sites. No logic changes.

## Files Changed

| File | Change |
|---|---|
| `services/researcher/claude_parser.py` | `"--model", "opus", "--effort", "max"` → `"--model", "haiku"` |
| `services/poster/copy_generator.py` | same |
| `scripts/claude-research.sh` | `--model opus --effort max` → `--model haiku` |
| `scripts/claude-social.sh` | same |

## Why haiku is sufficient

- **Research parser:** structured JSON extraction from raw scraped text — no reasoning required
- **Copy generator:** write a ≤250-char tweet from a coupon code + discount string — trivial for any model

Both services already have working fallbacks (regex parser, template copy) if the Claude call fails, so there is no risk of breakage.

## Expected savings

~95% reduction in Claude API token cost. Haiku is ~20× cheaper per token than Opus, and removing `--effort max` eliminates extended thinking overhead.
