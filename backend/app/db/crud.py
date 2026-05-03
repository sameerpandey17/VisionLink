import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RoiDetection
from app.core.detector import BoundingBox


async def save_detection(
    db: AsyncSession,
    session_id: uuid.UUID,
    frame_id: int,
    box: BoundingBox,
) -> None:
    """Insert one ROI detection record. All values are parameterised — no raw SQL."""
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
