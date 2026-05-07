"""
Database CRUD operations.

Each function documents the issue it addresses and the design choice made.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RoiDetection, Session

# Simple in-memory cache to avoid repeated session existence checks.
# Safe because DEFAULT_SESSION_ID is fixed for the process lifetime.
_verified_sessions: set[uuid.UUID] = set()


async def get_next_frame_id(db: AsyncSession) -> int:
    """
    Fetch the next frame ID from a PostgreSQL SEQUENCE.

    IDENTIFIED ISSUE — In-Memory Frame Counter
    -------------------------------------------
    The original code used `itertools.count(1)` at module level:

        _frame_counter = itertools.count(1)
        frame_id = next(_frame_counter)

    Problems:
      1. Restart → resets to 1 → duplicate frame_ids with existing DB rows.
      2. Multiple workers → each worker has its own count → duplicates
         across workers in the same session.

    FIX
    ---
    SELECT nextval('frame_id_seq') is atomic and crash-safe. Postgres
    guarantees no two callers ever receive the same value, even under
    concurrent load or after a restart.

    The sequence is created by migration 0002_frame_id_sequence.py.
    """
    result = await db.execute(sa.text("SELECT nextval('frame_id_seq')"))
    return int(result.scalar_one())


async def save_detection(
    db: AsyncSession,
    session_id: uuid.UUID,
    frame_id: int,
    box,
) -> None:
    """Insert one ROI detection record, ensuring the session row exists first."""
    if session_id not in _verified_sessions:
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
        expression=box.expression,
        emoji=box.emoji,
    )
    db.add(record)
    await db.commit()


async def list_detections(
    db: AsyncSession,
    session_id: uuid.UUID | None,
    limit: int,
    since: datetime | None,
    after: uuid.UUID | None = None,
) -> list[RoiDetection]:
    """
    Query detections with optional filters and cursor-based pagination.

    IDENTIFIED ISSUE — Flat List with LIMIT Only
    --------------------------------------------
    The original implementation:

        stmt = sa.select(RoiDetection).order_by(...).limit(limit)

    A LIMIT-only approach works for small datasets but does not scale:
      - To page through 10,000 records, clients need OFFSET.
      - OFFSET N forces Postgres to scan and discard the first N rows
        on every request — O(n) per page, getting slower as data grows.

    FIX — Cursor-Based (Keyset) Pagination
    ----------------------------------------
    Use the last returned row's UUID as the next page cursor:

      GET /api/roi?limit=100                   → first page, returns next_cursor
      GET /api/roi?limit=100&after=<uuid>      → next page, O(log n) via PK index

    The `after` UUID identifies the row at the boundary. We filter with:
      timestamp < cursor_row.timestamp
      OR (timestamp == cursor_row.timestamp AND id < cursor_uuid)

    This is stable even if new rows are inserted between pages, and uses
    the existing composite index (session_id, timestamp DESC) efficiently.

    Backwards compatibility: not passing `after` returns the first page
    exactly as before, so existing callers are unaffected.
    """
    stmt = (
        sa.select(RoiDetection)
        .order_by(RoiDetection.timestamp.desc(), RoiDetection.id.desc())
        .limit(limit)
    )

    if session_id is not None:
        stmt = stmt.where(RoiDetection.session_id == session_id)

    if since is not None:
        stmt = stmt.where(RoiDetection.timestamp > since)

    if after is not None:
        # Get the timestamp of the cursor row as a scalar subquery —
        # this avoids a round-trip to Python and keeps the filter in SQL.
        cursor_ts = (
            sa.select(RoiDetection.timestamp)
            .where(RoiDetection.id == after)
            .scalar_subquery()
        )
        stmt = stmt.where(
            sa.or_(
                RoiDetection.timestamp < cursor_ts,
                sa.and_(
                    RoiDetection.timestamp == cursor_ts,
                    RoiDetection.id < after,
                ),
            )
        )

    result = await db.execute(stmt)
    return list(result.scalars().all())
