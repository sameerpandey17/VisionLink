import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.config import settings
from app.core.broadcaster import broadcaster
from app.core.detector import detect_face
from app.core.renderer import draw_roi
from app.db.crud import get_next_frame_id, save_detection
from app.db.schemas import BoundingBoxOut, IngestResponse
from app.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

# Magic bytes used to verify file type (Content-Type is trivially spoofed)
MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n": "image/png",
}

# Default session ID for this server run (one session per process start).
# Production improvement: accept session_id as a request parameter so callers
# can group related frames into named sessions.
DEFAULT_SESSION_ID = uuid.uuid4()


def _check_magic(data: bytes) -> str:
    """Return MIME type if data starts with a known magic sequence, else raise."""
    for magic, mime in MAGIC_BYTES.items():
        if data[: len(magic)] == magic:
            return mime
    raise HTTPException(
        status_code=415,
        detail="Unsupported file type. Only JPEG and PNG are accepted.",
    )


def _on_save_done(task: asyncio.Task) -> None:
    """
    Callback attached to background DB save tasks.

    IDENTIFIED ISSUE — Silent Data Loss
    -------------------------------------
    The original code used:

        asyncio.create_task(save_detection(...))

    With no callback, any exception raised inside save_detection() is
    silently swallowed. Python will emit a "Task exception was never
    retrieved" RuntimeWarning to stderr at GC time — but only if the
    process is shutting down. During normal operation: complete silence.

    FIX
    ---
    By attaching this callback via task.add_done_callback(), we guarantee:
      1. Any DB write failure is logged as ERROR (visible in docker logs).
      2. The failure does NOT crash the ingest handler or drop the frame
         from the broadcast — the client still sees the video.
      3. No retry logic (by design) — frames are high-frequency and
         retrying stale data has no value. The important thing is knowing
         the metadata was lost so you can investigate the DB connection.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(
            "Background DB save failed — detection metadata NOT persisted: %s",
            exc,
            exc_info=exc,
        )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(require_api_key)],
)
async def ingest_frame(
    frame: UploadFile,
    db: AsyncSession = Depends(get_session),
) -> IngestResponse:
    """
    Receive a raw video frame, detect faces, broadcast the rendered frame,
    and persist detection metadata.

    Authentication:
      Requires X-API-Key header when API_KEY env var is set.
      Returns 401 if the key is missing or wrong.

    Steps:
      1. Validate file size (< 10 MB) and magic bytes (JPEG / PNG).
      2. Run MediaPipe face detection.
      3. Draw ROI with Pillow if a face was found; otherwise use original bytes.
      4. Fire-and-forget DB write with error callback (doesn't block response).
      5. Publish rendered frame to Redis channel (broadcasts to all WebSocket clients).
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

    # 4. DB write — fire and forget with error logging callback
    if box is not None:
        frame_id = await get_next_frame_id(db)  # Atomic PG sequence — no duplicates
        task = asyncio.create_task(save_detection(db, DEFAULT_SESSION_ID, frame_id, box))
        task.add_done_callback(_on_save_done)  # Logs any failure; never raises

    # 5. Broadcast via Redis (reaches all workers, not just this process)
    await broadcaster.publish(rendered)

    # 6. Response
    box_out = BoundingBoxOut(x=box.x, y=box.y, w=box.width, h=box.height) if box else None
    return IngestResponse(detected=box is not None, box=box_out)
