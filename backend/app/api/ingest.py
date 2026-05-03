import asyncio
import itertools
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.broadcaster import manager
from app.core.detector import detect_face
from app.core.renderer import draw_roi
from app.db.crud import save_detection
from app.db.schemas import BoundingBoxOut, IngestResponse
from app.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

# Magic bytes used to verify file type (Content-Type is trivially spoofed)
MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n": "image/png",
}

# Monotonic frame counter per session (simplified — single-process only)
_frame_counter = itertools.count(1)

# Default session ID for this server run (one session per process start)
DEFAULT_SESSION_ID = uuid.uuid4()


def _check_magic(data: bytes) -> str:
    """Return MIME type if data starts with a known magic sequence, else raise."""
    for magic, mime in MAGIC_BYTES.items():
        if data[: len(magic)] == magic:
            return mime
    raise HTTPException(status_code=415, detail="Unsupported file type. Only JPEG and PNG are accepted.")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_frame(
    frame: UploadFile,
    db: AsyncSession = Depends(get_session),
) -> IngestResponse:
    """
    Receive a raw video frame, detect faces, broadcast the rendered frame, and
    persist detection metadata.

    Steps:
      1. Validate file size (< 10 MB) and magic bytes (JPEG / PNG).
      2. Run MediaPipe face detection.
      3. Draw ROI with Pillow if a face was found; otherwise use original bytes.
      4. Fire-and-forget DB write (doesn't block the response).
      5. Broadcast rendered frame to all WebSocket subscribers.
      6. Return detection result.
    """
    raw = await frame.read()

    # 1. Size check — reject before any decoding
    if len(raw) > settings.max_frame_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Frame too large. Maximum allowed size is {settings.max_frame_size_bytes} bytes.",
        )

    # 1b. Magic-byte file-type check
    _check_magic(raw)

    # 2. Face detection (returns None on no-face — not an error)
    try:
        box = detect_face(raw)
    except Exception as exc:
        logger.exception("Unexpected error in face detector: %s", exc)
        raise HTTPException(status_code=500, detail="Internal detection error.") from exc

    # 3. Render
    try:
        rendered = draw_roi(raw, box) if box else raw
    except Exception:
        logger.warning("Pillow failed to decode frame; using original bytes.")
        rendered = raw

    # 4. DB write — fire and forget so the HTTP response isn't blocked
    if box is not None:
        frame_id = next(_frame_counter)
        asyncio.create_task(
            save_detection(db, DEFAULT_SESSION_ID, frame_id, box)
        )

    # 5. Broadcast (no clients = no-op, never errors)
    await manager.broadcast_bytes(rendered)

    # 6. Response
    box_out = BoundingBoxOut(x=box.x, y=box.y, w=box.width, h=box.height) if box else None
    return IngestResponse(detected=box is not None, box=box_out)
