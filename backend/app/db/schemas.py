import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BoundingBoxOut(BaseModel):
    x: int
    y: int
    w: int
    h: int
    expression: str | None = None
    emoji: str | None = None
    message: str | None = None


class IngestResponse(BaseModel):
    detected: bool
    box: BoundingBoxOut | None
    expression: str | None = None
    emoji: str | None = None
    message: str | None = None


class DetectionRecord(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    session_id: uuid.UUID
    x: int
    y: int
    width: int
    height: int
    confidence: float
    frame_id: int
    expression: str | None = None
    emoji: str | None = None

    class Config:
        from_attributes = True


class RoiListResponse(BaseModel):
    detections: list[DetectionRecord]

    # IDENTIFIED ISSUE: No pagination — simple LIMIT only.
    # FIX: Cursor-based pagination. When next_cursor is not None, the client
    # can fetch the next page with GET /api/roi?after=<next_cursor>.
    # next_cursor is the UUID of the last row in this response.
    # It is None when fewer rows were returned than the requested limit,
    # meaning there are no more pages.
    next_cursor: uuid.UUID | None = None


class RoiQueryParams(BaseModel):
    session_id: uuid.UUID | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    since: datetime | None = None
    after: uuid.UUID | None = None  # cursor for pagination
