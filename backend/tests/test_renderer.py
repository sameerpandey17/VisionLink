import io

import pytest
from PIL import Image

from app.core.detector import BoundingBox
from app.core.renderer import draw_roi


def _make_jpeg(width: int = 200, height: int = 200) -> bytes:
    img = Image.new("RGB", (width, height), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_box(x=10, y=10, w=50, h=60, iw=200, ih=200) -> BoundingBox:
    return BoundingBox(x=x, y=y, width=w, height=h, confidence=0.9, image_width=iw, image_height=ih)


def test_draw_roi_returns_valid_jpeg():
    """Output must be parseable as a JPEG image."""
    result = draw_roi(_make_jpeg(), _make_box())
    img = Image.open(io.BytesIO(result))
    assert img.format == "JPEG"


def test_draw_roi_rectangle_within_bounds():
    """The drawn rectangle must not exceed image dimensions."""
    frame = _make_jpeg(200, 200)
    box = _make_box(x=150, y=150, w=30, h=30, iw=200, ih=200)
    result = draw_roi(frame, box)
    img = Image.open(io.BytesIO(result))
    w, h = img.size
    assert box.x + box.width <= w
    assert box.y + box.height <= h


def test_draw_roi_custom_colour():
    """Custom outline colour must be accepted without error."""
    result = draw_roi(_make_jpeg(), _make_box(), outline=(255, 0, 0))
    img = Image.open(io.BytesIO(result))
    assert img.format == "JPEG"


def test_draw_roi_minimum_size_box():
    """A 1×1 box at origin should not crash."""
    box = BoundingBox(x=0, y=0, width=1, height=1, confidence=0.5, image_width=200, image_height=200)
    result = draw_roi(_make_jpeg(), box)
    assert len(result) > 0
