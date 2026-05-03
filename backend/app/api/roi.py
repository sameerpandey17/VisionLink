import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import list_detections
from app.db.schemas import RoiListResponse, DetectionRecord
from app.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/roi", response_model=RoiListResponse)
async def get_roi(
    session_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    since: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_session),
) -> RoiListResponse:
    """
    Return raw ROI detection records — coordinates only, no image data.

    Query params:
      - session_id: filter to a specific streaming session
      - limit: max records returned (1–1000, default 100)
      - since: ISO timestamp — only return records newer than this
    """
    rows = await list_detections(db, session_id=session_id, limit=limit, since=since)
    return RoiListResponse(
        detections=[DetectionRecord.model_validate(r) for r in rows]
    )
