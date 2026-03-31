import os
from image_generator import generate_image


def test_generate_image_creates_file(tmp_path):
    coupon = {"code": "GOLD60", "discount": "20% off over $60"}
    path = generate_image(coupon, output_dir=str(tmp_path))
    assert os.path.exists(path)
    assert path.endswith(".png")
