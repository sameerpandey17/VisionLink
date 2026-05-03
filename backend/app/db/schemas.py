import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BoundingBoxOut(BaseModel):
    x: int
    y: int
    w: int
    h: int


class IngestResponse(BaseModel):
    detected: bool
    box: BoundingBoxOut | None


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

    class Config:
        from_attributes = True


class RoiListResponse(BaseModel):
    detections: list[DetectionRecord]


class RoiQueryParams(BaseModel):
    session_id: uuid.UUID | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    since: datetime | None = None
