import io

import pytest
from PIL import Image

from app.core.detector import BoundingBox, detect_face, init_detector


@pytest.fixture(scope="module", autouse=True)
def initialise():
    init_detector()


def _make_blank_jpeg(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_detect_face_no_face_blank_frame():
    """A plain grey frame should return None, not raise."""
    result = detect_face(_make_blank_jpeg())
    assert result is None


def test_detect_face_corrupted_bytes():
    """Corrupted/non-image bytes should return None gracefully."""
    result = detect_face(b"not an image")
    assert result is None


def test_detect_face_returns_bounding_box_type():
    """If a face is detected the return type must be BoundingBox."""
    # We can't guarantee a face is in a synthesised frame, so we patch
    # the internal result to verify the output type contract.
    import mediapipe as mp
    import numpy as np
    from unittest.mock import MagicMock, patch

    mock_detection = MagicMock()
    mock_detection.score = [0.95]
    rel_bb = MagicMock()
    rel_bb.xmin = 0.1
    rel_bb.ymin = 0.1
    rel_bb.width = 0.3
    rel_bb.height = 0.4
    mock_detection.location_data.relative_bounding_box = rel_bb

    mock_results = MagicMock()
    mock_results.detections = [mock_detection]

    frame = _make_blank_jpeg(200, 200)

    import app.core.detector as detector_module
    with patch.object(detector_module._detector, "process", return_value=mock_results):
        result = detect_face(frame)

    assert isinstance(result, BoundingBox)
    assert result.confidence == pytest.approx(0.95)
    assert result.x >= 0
    assert result.y >= 0
    assert result.width > 0
    assert result.height > 0


def test_bounding_box_clamped_to_frame():
    """Box coordinates must never exceed image dimensions."""
    import app.core.detector as detector_module
    from unittest.mock import MagicMock, patch

    mock_detection = MagicMock()
    mock_detection.score = [0.8]
    rel_bb = MagicMock()
    # Intentionally outside bounds (> 1.0)
    rel_bb.xmin = 0.9
    rel_bb.ymin = 0.9
    rel_bb.width = 0.5  # would go past right edge
    rel_bb.height = 0.5  # would go past bottom
    mock_detection.location_data.relative_bounding_box = rel_bb

    mock_results = MagicMock()
    mock_results.detections = [mock_detection]

    frame = _make_blank_jpeg(100, 100)

    with patch.object(detector_module._detector, "process", return_value=mock_results):
        result = detect_face(frame)

    assert result is not None
    assert result.x + result.width <= result.image_width
    assert result.y + result.height <= result.image_height
