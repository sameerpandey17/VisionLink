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
    after: uuid.UUID | None = Query(
        default=None,
        description=(
            "Cursor for pagination. Pass the `next_cursor` value from the previous "
            "response to retrieve the next page. Omit for the first page."
        ),
    ),
    db: AsyncSession = Depends(get_session),
) -> RoiListResponse:
    """
    Return raw ROI detection records — coordinates only, no image data.

    IDENTIFIED ISSUE: Simple LIMIT-only pagination
    ------------------------------------------------
    The original endpoint only accepted `limit`. To walk through large
    result sets, callers would need OFFSET — which scans all preceding
    rows on every request (O(n) cost, getting slower as data grows).

    FIX: Cursor-based (keyset) pagination
    ----------------------------------------
    The response now includes `next_cursor` — the UUID of the last row
    in the current page. Pass it as `after=<uuid>` in the next request.

    Example walkthrough:
        # Page 1
        GET /api/roi?limit=100
        → { "detections": [...100 items...], "next_cursor": "abc-uuid" }

        # Page 2
        GET /api/roi?limit=100&after=abc-uuid
        → { "detections": [...next 100...], "next_cursor": "def-uuid" }

        # Last page (fewer than 100 items returned)
        GET /api/roi?limit=100&after=def-uuid
        → { "detections": [...12 items...], "next_cursor": null }

    This is O(log n) via the primary key index — page speed is constant
    regardless of how many total records exist.

    Query params:
      - session_id: filter to a specific streaming session
      - limit:      max records returned (1–1000, default 100)
      - since:      ISO timestamp — only return records newer than this
      - after:      cursor UUID for pagination (last row of previous page)
    """
    rows = await list_detections(
        db, session_id=session_id, limit=limit, since=since, after=after
    )

    # next_cursor is set only when a full page was returned — implies more data exists.
    next_cursor = rows[-1].id if len(rows) == limit else None

    return RoiListResponse(
        detections=[DetectionRecord.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )
