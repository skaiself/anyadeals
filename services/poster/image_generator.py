"""Generate branded images using NanoBanana 2 API with Pillow fallback."""

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("poster")

NANOBANANA_URL = "https://api.nanobanana.com/v1/generate"

CREAM = "#FAF8F5"
INK = "#0F0D0B"
SIGNAL = "#EA580C"
GOLD = "#D97706"


async def _nanobanana_generate(prompt: str, output_path: str) -> str:
    """Generate an image via NanoBanana 2 free API."""
    api_key = os.environ.get("NANOBANANA_API_KEY", "")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            NANOBANANA_URL,
            json={"prompt": prompt, "model": "gemini-3.1-flash", "size": "1080x1080"},
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
    return output_path


def _fallback_image(coupon: dict, output_dir: str = "/data/posts") -> str:
    """Create a simple branded image using Pillow."""
    os.makedirs(output_dir, exist_ok=True)
    code = coupon.get("code", "CODE")
    discount = coupon.get("discount", "")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"{code}_{timestamp}.png")

    img = Image.new("RGB", (1080, 1080), CREAM)
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large

    draw.rectangle([(0, 0), (1080, 120)], fill=SIGNAL)
    draw.text((540, 60), "anyadeals.com", fill=CREAM, font=font_medium, anchor="mm")
    draw.text((540, 400), code, fill=INK, font=font_large, anchor="mm")
    draw.text((540, 520), discount, fill=GOLD, font=font_medium, anchor="mm")
    draw.text((540, 680), "Verified by Anya", fill=SIGNAL, font=font_small, anchor="mm")
    draw.rectangle([(0, 960), (1080, 1080)], fill=INK)
    draw.text((540, 1020), "Stack with OFR0296 for extra savings", fill=CREAM, font=font_small, anchor="mm")

    img.save(output_path, "PNG")
    logger.info("Fallback image created: %s", output_path)
    return output_path


async def generate_image(coupon: dict, output_dir: str = "/data/posts") -> str | None:
    """Generate a branded image for social media. NanoBanana 2 -> Pillow fallback."""
    code = coupon.get("code", "")
    discount = coupon.get("discount", "")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"{code}_{timestamp}.png")

    try:
        prompt = (
            f"Clean, modern promotional image for iHerb coupon code {code}. "
            f"Discount: {discount}. Cream background with orange accents. "
            f"Minimalist design with the code prominently displayed. "
            f"Brand: anyadeals.com"
        )
        path = await _nanobanana_generate(prompt, output_path)
        logger.info("NanoBanana image generated: %s", path)
        return path
    except Exception as e:
        logger.warning("NanoBanana failed, using Pillow fallback: %s", e)
        return _fallback_image(coupon, output_dir=output_dir)
