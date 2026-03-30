"""Parse and deduplicate raw scraped codes using Claude CLI or fallback regex."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger("researcher")

CLAUDE_PROMPT_TEMPLATE = """You are a coupon code analyst. Given these raw scraped entries from various coupon websites, extract and deduplicate valid iHerb promo codes.

Raw data:
{raw_data}

For each unique coupon code, return a JSON array with objects containing:
- code: the coupon code (uppercase)
- source: where it was found
- discovered_at: ISO timestamp (use current time)
- raw_description: cleaned description of the discount
- raw_context: original context text
- discount_type: "percentage" | "fixed" | "free_shipping" | "unknown"
- discount_value: numeric value (0 if unknown)
- regions: array of region codes like ["us", "de", "gb"] or ["us"] if unclear
- expiry_date: ISO date if mentioned, null otherwise
- confidence: "high" | "medium" | "low" based on source reliability
- validation_status: "pending"

Rules:
- Deduplicate: if same code appears from multiple sources, keep one entry with the best description
- Filter out obvious non-codes (HTML tags, common words)
- Only include codes that look like valid iHerb promo codes (typically 4-20 chars, alphanumeric)
- Return ONLY the JSON array, no other text"""


async def _run_claude_cli(prompt: str) -> list[dict]:
    """Run Claude CLI and parse JSON response. Retries once after 5min on rate limit."""
    for attempt in range(2):
        cmd = [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
            "--model", "haiku",
            "--output-format", "json",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stderr_text = stderr.decode()[:500]

        if proc.returncode != 0:
            if "rate" in stderr_text.lower() and attempt == 0:
                logger.warning("Claude CLI rate limited, retrying in 5 minutes")
                await asyncio.sleep(300)
                continue
            raise RuntimeError(f"Claude CLI failed (exit {proc.returncode}): {stderr_text}")
        break

    output = stdout.decode("utf-8", errors="replace").strip()

    # Claude --output-format json wraps response in {"result": "..."}
    try:
        wrapper = json.loads(output)
        if isinstance(wrapper, dict) and "result" in wrapper:
            content = wrapper["result"]
        else:
            content = output
    except json.JSONDecodeError:
        content = output

    # Extract JSON array from response
    if isinstance(content, str):
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON array found in Claude output: {content[:200]}")
    elif isinstance(content, list):
        return content
    else:
        raise ValueError(f"Unexpected Claude output type: {type(content)}")


def _fallback_parse(raw_codes: list[dict]) -> list[dict]:
    """Simple regex-based parser when Claude CLI is unavailable."""
    now = datetime.now(timezone.utc).isoformat()
    seen = set()
    results = []

    for entry in raw_codes:
        code = entry.get("code", "").upper().strip()
        if not code or code in seen:
            continue
        if len(code) < 4 or len(code) > 20:
            continue
        seen.add(code)

        desc = entry.get("raw_description", "") or entry.get("raw_context", "")
        discount_type = "unknown"
        discount_value = 0
        pct_match = re.search(r'(\d+)\s*%', desc)
        dollar_match = re.search(r'\$\s*(\d+)', desc)
        if pct_match:
            discount_type = "percentage"
            discount_value = int(pct_match.group(1))
        elif dollar_match:
            discount_type = "fixed"
            discount_value = int(dollar_match.group(1))

        results.append({
            "code": code,
            "source": entry.get("source", "unknown"),
            "discovered_at": now,
            "raw_description": entry.get("raw_description", ""),
            "raw_context": entry.get("raw_context", ""),
            "discount_type": discount_type,
            "discount_value": discount_value,
            "regions": ["us"],
            "expiry_date": None,
            "confidence": "low",
            "validation_status": "pending",
        })

    return results


async def parse_and_deduplicate(raw_codes: list[dict]) -> list[dict]:
    """Parse raw codes with Claude CLI, falling back to regex if CLI fails."""
    if not raw_codes:
        return []

    try:
        prompt = CLAUDE_PROMPT_TEMPLATE.format(raw_data=json.dumps(raw_codes[:50], indent=2))
        result = await _run_claude_cli(prompt)
        logger.info("Claude CLI parsed %d codes", len(result))
        return result
    except Exception as e:
        logger.warning("Claude CLI failed, using fallback parser: %s", e)
        return _fallback_parse(raw_codes)
