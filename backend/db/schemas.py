"""Pydantic v2 schemas for request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


# --- Inbound payloads from inference engine ---


class TrafficDataPayload(BaseModel):
    """Received from the inference engine every N frames."""

    job_id: str
    frame_number: int
    progress_pct: float = 0.0
    total_vehicles: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    avg_speed_kmh: float = 0.0
    max_speed_kmh: float = 0.0
    congestion_level: str = "LOW"
    active_incidents: list[dict[str, Any]] = Field(default_factory=list)
    crossing_counts: dict[str, int] = Field(default_factory=dict)


class JobSummaryPayload(BaseModel):
    """Received when inference is complete."""

    total_frames_processed: int = 0
    total_unique_vehicles: int = 0
    peak_vehicle_count: int = 0
    total_incidents: int = 0
    total_crossings: int = 0
    avg_speed_overall: float = 0.0
    output_video_path: str = ""
    crossing_counts: dict[str, int] = Field(default_factory=dict)


# --- Outbound responses ---

_CONGESTION_COLORS = {
    "LOW": "#22c55e",
    "MODERATE": "#f59e0b",
    "HIGH": "#f97316",
    "CRITICAL": "#ef4444",
}


class JobResponse(BaseModel):
    """Full job record returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    original_filename: str
    input_path: str
    output_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_frames: int | None = None
    processed_frames: int | None = None
    progress_pct: float = 0.0
    error_message: str | None = None
    congestion_level: str | None = None  # from latest snapshot

    @computed_field
    @property
    def congestion_color(self) -> str:
        return _CONGESTION_COLORS.get(self.congestion_level or "LOW", "#22c55e")


class HistoryPoint(BaseModel):
    """Single data point for charts."""

    model_config = ConfigDict(from_attributes=True)

    frame_number: int
    total_vehicles: int
    avg_speed_kmh: float
    congestion_level: str
    timestamp: datetime


class IncidentResponse(BaseModel):
    """Incident record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    track_id: int
    incident_type: str
    frame_number: int
    x: float
    y: float
    detected_at: datetime
    resolved: bool


class JobUploadResponse(BaseModel):
    """Response after a successful video upload."""

    job_id: str
    status: str
    filename: str
