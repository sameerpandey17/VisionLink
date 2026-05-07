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
from app.db.session import async_session_factory, get_session

logger = logging.getLogger(__name__)
router = APIRouter()

# Magic bytes used to verify file type (Content-Type is trivially spoofed)
MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n": "image/png",
}

# Default session ID for this server run (one session per process start).
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


async def _background_save(session_id: uuid.UUID, frame_id: int, box) -> None:
    """Independent wrapper for DB persistence in background."""
    async with async_session_factory() as db:
        await save_detection(db, session_id, frame_id, box)


def _on_save_done(task: asyncio.Task) -> None:
    """Callback attached to background DB save tasks to log failures."""
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
    "/api/ingest",
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
    """
    raw = await frame.read()

    # 1. Size and Type check
    if len(raw) > settings.max_frame_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Frame too large. Maximum allowed size is {settings.max_frame_size_bytes} bytes.",
        )
    _check_magic(raw)

    # 2. Face detection
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

    # 4. DB write — uses isolated background task to prevent pool exhaustion
    if box is not None:
        frame_id = await get_next_frame_id(db) 
        task = asyncio.create_task(_background_save(DEFAULT_SESSION_ID, frame_id, box))
        task.add_done_callback(_on_save_done)

    # 5. Broadcast via Redis
    await broadcaster.publish(rendered)

    # 6. Response
    box_out = BoundingBoxOut(
        x=box.x, 
        y=box.y, 
        w=box.width, 
        h=box.height,
        expression=box.expression,
        emoji=box.emoji,
        message=box.message
    ) if box else None
    
    return IngestResponse(
        detected=box is not None, 
        box=box_out,
        expression=box.expression if box else None,
        emoji=box.emoji if box else None,
        message=box.message if box else None
    )
