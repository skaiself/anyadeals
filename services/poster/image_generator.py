"""Generate branded social media images using Pillow."""

import logging
import os
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("poster")

CREAM = "#FAF8F5"
INK = "#0F0D0B"
SIGNAL = "#EA580C"
GOLD = "#D97706"


def generate_image(coupon: dict, output_dir: str = "/data/posts") -> str:
    """Create a branded image for social media using Pillow."""
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
    logger.info("Image created: %s", output_path)
    return output_path
