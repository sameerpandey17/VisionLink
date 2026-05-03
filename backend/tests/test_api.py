import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.core.detector import BoundingBox


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _jpeg_bytes(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes() -> bytes:
    img = Image.new("RGB", (50, 50), color=(100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── POST /ingest ──────────────────────────────────────────────────────────────

class TestIngest:
    def test_valid_jpeg_no_face(self, client):
        """A clean grey frame with no face → 200, detected=False."""
        with patch("app.api.ingest.detect_face", return_value=None), \
             patch("app.api.ingest.manager.broadcast_bytes", new_callable=AsyncMock):
            resp = client.post(
                "/ingest",
                files={"frame": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["detected"] is False
        assert body["box"] is None

    def test_valid_jpeg_with_face(self, client):
        """Frame with a detected face → 200, detected=True, box populated."""
        fake_box = BoundingBox(x=10, y=10, width=40, height=50, confidence=0.9, image_width=100, image_height=100)
        with patch("app.api.ingest.detect_face", return_value=fake_box), \
             patch("app.api.ingest.draw_roi", return_value=_jpeg_bytes()), \
             patch("app.api.ingest.manager.broadcast_bytes", new_callable=AsyncMock), \
             patch("app.api.ingest.save_detection", new_callable=AsyncMock):
            resp = client.post(
                "/ingest",
                files={"frame": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["detected"] is True
        assert body["box"]["x"] == 10

    def test_wrong_content_type_rejected(self, client):
        """A GIF file (wrong magic bytes) → 415."""
        gif_bytes = b"GIF89a" + b"\x00" * 100
        resp = client.post(
            "/ingest",
            files={"frame": ("frame.gif", gif_bytes, "image/gif")},
        )
        assert resp.status_code == 415

    def test_oversized_file_rejected(self, client):
        """A frame exceeding 10 MB → 413."""
        big = b"\xff\xd8\xff" + b"\x00" * (10 * 1024 * 1024 + 1)
        resp = client.post(
            "/ingest",
            files={"frame": ("big.jpg", big, "image/jpeg")},
        )
        assert resp.status_code == 413

    def test_valid_png_accepted(self, client):
        """PNG magic bytes → accepted (200)."""
        with patch("app.api.ingest.detect_face", return_value=None), \
             patch("app.api.ingest.manager.broadcast_bytes", new_callable=AsyncMock):
            resp = client.post(
                "/ingest",
                files={"frame": ("frame.png", _png_bytes(), "image/png")},
            )
        assert resp.status_code == 200


# ── GET /api/roi ───────────────────────────────────────────────────────────────

class TestRoi:
    def test_roi_returns_list(self, client):
        """GET /api/roi without params → 200, detections key present."""
        with patch("app.api.roi.list_detections", new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/roi")
        assert resp.status_code == 200
        assert "detections" in resp.json()

    def test_roi_limit_out_of_range(self, client):
        """limit > 1000 → 422 validation error."""
        resp = client.get("/api/roi?limit=9999")
        assert resp.status_code == 422

    def test_roi_session_id_filter(self, client):
        """Valid UUID session_id → 200."""
        sid = uuid.uuid4()
        with patch("app.api.roi.list_detections", new_callable=AsyncMock, return_value=[]):
            resp = client.get(f"/api/roi?session_id={sid}")
        assert resp.status_code == 200
