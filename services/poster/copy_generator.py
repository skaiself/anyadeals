"""Generate social media copy using Claude CLI or fallback templates."""

import asyncio
import json
import logging

logger = logging.getLogger("poster")

AFFILIATE_CODE = "OFR0296"
SITE_URL = "https://anyadeals.com/coupons/iherb/"

COPY_PROMPT_TEMPLATE = """Write a short, engaging social media post promoting this iHerb coupon code.

Coupon: {code}
Discount: {discount}
Referral code to stack: {affiliate_code}
Link: {site_url}

Requirements:
- Under 250 characters for Twitter
- Engaging, casual tone
- Include the coupon code prominently
- Mention stacking with referral code {affiliate_code}
- Include 2-3 relevant hashtags
- No emojis unless they add value
- Return ONLY the post text, nothing else"""


async def _run_claude_cli(prompt: str) -> str:
    """Run Claude CLI and return text response. Retries once after 5min on rate limit."""
    for attempt in range(2):
        cmd = [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
            "--model", "haiku",
            "--output-format", "text",
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
            raise RuntimeError(f"Claude CLI failed: {stderr_text}")
        break
    return stdout.decode("utf-8", errors="replace").strip()


def _fallback_copy(coupon: dict) -> str:
    """Template-based copy when Claude CLI is unavailable."""
    code = coupon.get("code", "")
    discount = coupon.get("discount", "")
    return (
        f"Verified: {code} — {discount} at iHerb\n\n"
        f"Stack with {AFFILIATE_CODE} for extra savings!\n\n"
        f"{SITE_URL}\n"
        f"#iHerb #supplements #deals"
    )


async def generate_copy(coupon: dict) -> str:
    """Generate social media copy with Claude CLI, fallback to template."""
    try:
        prompt = COPY_PROMPT_TEMPLATE.format(
            code=coupon.get("code", ""),
            discount=coupon.get("discount", ""),
            affiliate_code=AFFILIATE_CODE,
            site_url=SITE_URL,
        )
        result = await _run_claude_cli(prompt)
        logger.info("Claude CLI generated copy: %s", result[:50])
        return result
    except Exception as e:
        logger.warning("Claude CLI failed, using fallback copy: %s", e)
        return _fallback_copy(coupon)
