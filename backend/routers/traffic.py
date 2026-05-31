"""Traffic data ingestion — receives analytics from the inference engine."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Incident, Job, TrafficSnapshot
from db.schemas import JobSummaryPayload, TrafficDataPayload
from db.session import get_db
from ws.manager import manager

router = APIRouter()


@router.post("/traffic-data")
async def receive_traffic_data(
    payload: TrafficDataPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Receive a traffic analytics snapshot from the inference engine."""
    try:
        job_uuid = uuid.UUID(payload.job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    categories = payload.categories

    # 1. Write traffic snapshot
    snapshot = TrafficSnapshot(
        job_id=job_uuid,
        frame_number=payload.frame_number,
        total_vehicles=payload.total_vehicles,
        cars=categories.get("cars", 0),
        vans=categories.get("vans", 0),
        trucks=categories.get("trucks", 0),
        buses=categories.get("buses", 0),
        others=categories.get("others", 0),
        avg_speed_kmh=payload.avg_speed_kmh,
        max_speed_kmh=payload.max_speed_kmh,
        congestion_level=payload.congestion_level,
        crossing_total=payload.crossing_counts.get("total", 0),
        active_incidents_count=len(payload.active_incidents),
    )
    db.add(snapshot)

    # 2. Write new incidents
    for inc_data in payload.active_incidents:
        track_id = inc_data.get("track_id")
        if track_id is not None:
            # Check if incident already exists for this track in this job
            existing = await db.execute(
                select(Incident).where(
                    Incident.job_id == job_uuid,
                    Incident.track_id == track_id,
                )
            )
            if existing.scalar_one_or_none() is None:
                incident = Incident(
                    job_id=job_uuid,
                    track_id=track_id,
                    incident_type=inc_data.get("type", "stopped_vehicle"),
                    frame_number=inc_data.get("started_frame", payload.frame_number),
                    x=float(inc_data.get("cx", 0)),
                    y=float(inc_data.get("cy", 0)),
                )
                db.add(incident)

    # 3. Update job progress
    result = await db.execute(select(Job).where(Job.id == job_uuid))
    job = result.scalar_one_or_none()
    if job:
        job.progress_pct = payload.progress_pct
        job.processed_frames = payload.frame_number

    await db.commit()

    # 4. Broadcast to WebSocket
    await manager.broadcast_to_job(
        payload.job_id,
        {"event": "analytics", "data": payload.model_dump()},
    )

    return {"status": "ok"}


@router.post("/jobs/{job_id}/complete")
async def job_complete(
    job_id: str,
    payload: JobSummaryPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark a job as complete with final summary stats."""
    from datetime import datetime, timezone

    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(select(Job).where(Job.id == uid))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    job.output_path = payload.output_video_path
    job.total_frames = payload.total_frames_processed
    job.progress_pct = 100.0
    await db.commit()

    # Broadcast completion
    await manager.broadcast_to_job(
        job_id,
        {"event": "complete", "summary": payload.model_dump()},
    )

    return {"status": "ok"}
