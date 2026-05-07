import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RoiDetection
from app.core.detector import BoundingBox


# Simple in-memory cache to avoid repeated session existence checks
_verified_sessions: set[uuid.UUID] = set()

async def save_detection(
    db: AsyncSession,
    session_id: uuid.UUID,
    frame_id: int,
    box: BoundingBox,
) -> None:
    """Insert one ROI detection record, ensuring the session exists first."""
    
    # Ensure session exists (with local cache optimization)
    if session_id not in _verified_sessions:
        stmt = sa.select(sa.func.count()).select_from(sa.Table("sessions", sa.MetaData(), autoload_with=db.bind)).where(sa.column("id") == session_id)
        # Actually easier to just try insert and ignore if exists or just always check
        # Let's do a simple check and insert
        from app.db.models import Session
        result = await db.execute(sa.select(Session).where(Session.id == session_id))
        if not result.scalar_one_or_none():
            db.add(Session(id=session_id, source_label="live-stream"))
            await db.commit()
        _verified_sessions.add(session_id)

    record = RoiDetection(
        session_id=session_id,
        frame_id=frame_id,
        x=box.x,
        y=box.y,
        width=box.width,
        height=box.height,
        confidence=box.confidence,
    )
    db.add(record)
    await db.commit()


async def list_detections(
    db: AsyncSession,
    session_id: uuid.UUID | None,
    limit: int,
    since: datetime | None,
) -> list[RoiDetection]:
    """Query detections with optional filters. Uses ORM — no string-formatted SQL."""
    stmt = sa.select(RoiDetection).order_by(RoiDetection.timestamp.desc()).limit(limit)

    if session_id is not None:
        stmt = stmt.where(RoiDetection.session_id == session_id)

    if since is not None:
        stmt = stmt.where(RoiDetection.timestamp > since)

    result = await db.execute(stmt)
    return list(result.scalars().all())
