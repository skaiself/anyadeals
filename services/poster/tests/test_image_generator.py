import os
import pytest
from unittest.mock import AsyncMock, patch
from image_generator import generate_image, _fallback_image


def test_fallback_image_creates_file(tmp_path):
    coupon = {"code": "GOLD60", "discount": "20% off over $60"}
    output_dir = str(tmp_path)
    path = _fallback_image(coupon, output_dir=output_dir)
    assert os.path.exists(path)
    assert path.endswith(".png")


@pytest.mark.asyncio
async def test_generate_image_uses_fallback(tmp_path):
    coupon = {"code": "TEST5", "discount": "5% off"}
    with patch("image_generator._nanobanana_generate", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("API unavailable")
        path = await generate_image(coupon, output_dir=str(tmp_path))
    assert path is not None
    assert os.path.exists(path)
