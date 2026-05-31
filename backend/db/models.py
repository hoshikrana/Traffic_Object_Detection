"""SQLAlchemy async ORM models for the traffic analytics system."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UUID,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    input_path: Mapped[str] = mapped_column(String(500))
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    snapshots: Mapped[list["TrafficSnapshot"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class TrafficSnapshot(Base):
    __tablename__ = "traffic_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    frame_number: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    total_vehicles: Mapped[int] = mapped_column(Integer, default=0)
    cars: Mapped[int] = mapped_column(Integer, default=0)
    vans: Mapped[int] = mapped_column(Integer, default=0)
    trucks: Mapped[int] = mapped_column(Integer, default=0)
    buses: Mapped[int] = mapped_column(Integer, default=0)
    others: Mapped[int] = mapped_column(Integer, default=0)
    avg_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    max_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    congestion_level: Mapped[str] = mapped_column(String(20), default="LOW")
    crossing_total: Mapped[int] = mapped_column(Integer, default=0)
    active_incidents_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    job: Mapped["Job"] = relationship(back_populates="snapshots")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(Integer)
    incident_type: Mapped[str] = mapped_column(String(50), default="stopped_vehicle")
    frame_number: Mapped[int] = mapped_column(Integer)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    job: Mapped["Job"] = relationship(back_populates="incidents")
