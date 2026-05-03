import uuid

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    ended_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    source_label: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class RoiDetection(Base):
    __tablename__ = "roi_detections"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    frame_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    timestamp: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    y: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    width: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    height: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)

    __table_args__ = (
        sa.CheckConstraint("x >= 0 AND y >= 0 AND width > 0 AND height > 0", name="positive_coords"),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="valid_confidence"),
        sa.Index("idx_roi_session_ts", "session_id", sa.text("timestamp DESC")),
    )
