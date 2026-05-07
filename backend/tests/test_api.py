"""
API integration tests.

Covers:
  - POST /ingest: auth, file type, file size, face detection paths
  - GET /api/roi: list, validation, session filter, cursor pagination
"""

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


# ── POST /ingest — Auth ───────────────────────────────────────────────────────

class TestIngestAuth:
    """
    Verify the X-API-Key authentication added in v2.

    IDENTIFIED ISSUE: /ingest had no authentication.
    FIX: require_api_key dependency; 401 when API_KEY is set and key is wrong/missing.
    """

    def test_no_key_when_auth_disabled(self, client):
        """When API_KEY env var is empty, requests without X-API-Key still succeed."""
        # auth_enabled is False by default (API_KEY = "")
        with patch("app.api.ingest.detect_face", return_value=None), \
             patch("app.core.broadcaster.broadcaster.publish", new_callable=AsyncMock):
            resp = client.post(
                "/ingest",
                files={"frame": ("f.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        assert resp.status_code == 200

    def test_wrong_key_returns_401(self, client):
        """When auth is enabled, a wrong X-API-Key returns 401."""
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.auth_enabled = True
            mock_settings.api_key = "correct-key"
            resp = client.post(
                "/ingest",
                headers={"X-API-Key": "wrong-key"},
                files={"frame": ("f.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        assert resp.status_code == 401

    def test_missing_key_returns_401(self, client):
        """When auth is enabled, a missing X-API-Key header returns 401."""
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.auth_enabled = True
            mock_settings.api_key = "correct-key"
            resp = client.post(
                "/ingest",
                files={"frame": ("f.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        assert resp.status_code == 401

    def test_correct_key_returns_200(self, client):
        """When auth is enabled and the correct key is supplied, request succeeds."""
        with patch("app.api.deps.settings") as mock_settings, \
             patch("app.api.ingest.detect_face", return_value=None), \
             patch("app.core.broadcaster.broadcaster.publish", new_callable=AsyncMock):
            mock_settings.auth_enabled = True
            mock_settings.api_key = "correct-key"
            resp = client.post(
                "/ingest",
                headers={"X-API-Key": "correct-key"},
                files={"frame": ("f.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        assert resp.status_code == 200


# ── POST /ingest — Frame Processing ──────────────────────────────────────────

class TestIngest:
    def test_valid_jpeg_no_face(self, client):
        """A clean grey frame with no face → 200, detected=False."""
        with patch("app.api.ingest.detect_face", return_value=None), \
             patch("app.core.broadcaster.broadcaster.publish", new_callable=AsyncMock):
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
        fake_box = BoundingBox(
            x=10, y=10, width=40, height=50, confidence=0.9,
            image_width=100, image_height=100,
        )
        with patch("app.api.ingest.detect_face", return_value=fake_box), \
             patch("app.api.ingest.draw_roi", return_value=_jpeg_bytes()), \
             patch("app.core.broadcaster.broadcaster.publish", new_callable=AsyncMock), \
             patch("app.api.ingest.get_next_frame_id", new_callable=AsyncMock, return_value=42), \
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
             patch("app.core.broadcaster.broadcaster.publish", new_callable=AsyncMock):
            resp = client.post(
                "/ingest",
                files={"frame": ("frame.png", _png_bytes(), "image/png")},
            )
        assert resp.status_code == 200

    def test_db_write_failure_does_not_fail_response(self, client):
        """
        A DB write failure in the background task must not cause a 5xx response.

        IDENTIFIED ISSUE: asyncio.create_task without callback — silent data loss.
        FIX: _on_save_done callback logs the error; the HTTP response is unaffected.

        This test verifies the handler returns 200 even when save_detection raises.
        """
        fake_box = BoundingBox(
            x=5, y=5, width=30, height=30, confidence=0.8,
            image_width=100, image_height=100,
        )

        async def _failing_save(*args, **kwargs):
            raise RuntimeError("Simulated DB failure")

        with patch("app.api.ingest.detect_face", return_value=fake_box), \
             patch("app.api.ingest.draw_roi", return_value=_jpeg_bytes()), \
             patch("app.core.broadcaster.broadcaster.publish", new_callable=AsyncMock), \
             patch("app.api.ingest.get_next_frame_id", new_callable=AsyncMock, return_value=1), \
             patch("app.api.ingest.save_detection", side_effect=_failing_save):
            resp = client.post(
                "/ingest",
                files={"frame": ("frame.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        # The HTTP response must still be 200 — the background failure is logged only
        assert resp.status_code == 200


# ── GET /api/roi ───────────────────────────────────────────────────────────────

class TestRoi:
    def test_roi_returns_list(self, client):
        """GET /api/roi without params → 200, detections key present."""
        with patch("app.api.roi.list_detections", new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/roi")
        assert resp.status_code == 200
        body = resp.json()
        assert "detections" in body
        assert "next_cursor" in body  # new field in v2

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

    def test_roi_cursor_pagination(self, client):
        """
        IDENTIFIED ISSUE: No cursor pagination — only simple LIMIT.
        FIX: `after` query param + `next_cursor` in response.

        Verify that passing `after=<uuid>` is accepted and returns 200.
        Verify that next_cursor is null when fewer rows than limit are returned.
        """
        cursor = uuid.uuid4()
        with patch("app.api.roi.list_detections", new_callable=AsyncMock, return_value=[]):
            resp = client.get(f"/api/roi?limit=10&after={cursor}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["next_cursor"] is None  # empty result → no more pages

    def test_roi_invalid_after_uuid(self, client):
        """after param must be a valid UUID → 422 if not."""
        resp = client.get("/api/roi?after=not-a-uuid")
        assert resp.status_code == 422

    def test_next_cursor_set_when_full_page_returned(self, client):
        """
        next_cursor must be the UUID of the last row when a full page is returned.
        This signals to the client that more rows may exist.
        """
        last_id = uuid.uuid4()
        mock_rows = []
        for i in range(5):
            row = MagicMock()
            row.id = uuid.uuid4() if i < 4 else last_id
            row.timestamp = MagicMock()
            row.session_id = uuid.uuid4()
            row.x = row.y = row.width = row.height = 10
            row.confidence = 0.9
            row.frame_id = i
            mock_rows.append(row)

        # When limit==5 and we get exactly 5 rows, next_cursor should be set
        with patch("app.api.roi.list_detections", new_callable=AsyncMock, return_value=mock_rows):
            resp = client.get("/api/roi?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["next_cursor"] == str(last_id)
