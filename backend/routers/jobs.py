"""Job management endpoints — upload, status, list, history, summary."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Incident, Job, TrafficSnapshot
from db.schemas import (
    HistoryPoint,
    IncidentResponse,
    JobResponse,
    JobUploadResponse,
)
from db.session import get_db
from ws.manager import manager

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = str(Path(os.getenv("UPLOAD_DIR", "./uploads")).resolve())
OUTPUT_DIR = str(Path(os.getenv("OUTPUT_DIR", "./outputs")).resolve())
MODEL_PATH = str(Path(os.getenv("MODEL_PATH", "./artifacts/best_openvino_model/")).resolve())

# Max upload size: 500MB
MAX_UPLOAD_SIZE = 500 * 1024 * 1024


async def run_inference_job(job_id: str, input_path: str, db: AsyncSession) -> None:
    """Background task: update job status and spawn inference subprocess."""
    from db.session import async_session_factory

    async with async_session_factory() as session:
        # Update job to processing
        result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if not job:
            return

        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

    # Broadcast status update
    await manager.broadcast_to_job(job_id, {"event": "status", "status": "processing"})

    # Build subprocess command
    output_path = str(Path(OUTPUT_DIR) / f"{job_id}_annotated.mp4")
    cmd = [
        sys.executable, "-m", "inference.engine",
        "--model", MODEL_PATH,
        "--video", input_path,
        "--output", output_path,
        "--job-id", job_id,
        "--api-url", "http://127.0.0.1:8000",
    ]

    logger.info("Spawning inference subprocess with command: %s", " ".join(cmd))
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).resolve().parent.parent.parent),  # project root
        )

        captured_errors = []

        async def read_stdout(stream):
            async for line in stream:
                decoded = line.decode().strip()
                if decoded:
                    logger.info("[INF-OUT] %s", decoded)

        async def read_stderr(stream):
            async for line in stream:
                decoded = line.decode().strip()
                if decoded:
                    logger.warning("[INF-ERR] %s", decoded)
                    captured_errors.append(decoded)

        # Run stdout and stderr streaming concurrently
        await asyncio.gather(
            read_stdout(process.stdout),
            read_stderr(process.stderr),
        )

        await process.wait()
        logger.info("Inference subprocess exited with return code: %d", process.returncode)

        if process.returncode != 0:
            error_msg = "\n".join(captured_errors) or "Subprocess exited with non-zero return code"
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Job).where(Job.id == uuid.UUID(job_id))
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_message = error_msg[:2000]
                    await session.commit()

            await manager.broadcast_to_job(
                job_id, {"event": "error", "message": "Inference failed", "error": error_msg[:200]}
            )

    except Exception as exc:
        logger.exception("Failed to run inference job subprocess")
        async with async_session_factory() as session:
            result = await session.execute(
                select(Job).where(Job.id == uuid.UUID(job_id))
            )
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error_message = f"Subprocess spawning error: {exc}"[:2000]
                await session.commit()


@router.post("/jobs/upload", response_model=JobUploadResponse)
async def upload_video(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload a video file for processing."""
    # Validate content type
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only video files are accepted.",
        )

    # Generate unique filename
    file_id = uuid.uuid4()
    original_name = (file.filename or "upload.mp4").replace(" ", "_")
    save_name = f"{file_id}_{original_name}"
    save_path = Path(UPLOAD_DIR) / save_name
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Save file
    total_size = 0
    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                save_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail="File too large. Maximum size is 500MB."
                )
            f.write(chunk)

    # Create job record
    job = Job(
        id=file_id,
        status="queued",
        original_filename=original_name,
        input_path=str(save_path),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Trigger background processing
    background_tasks.add_task(run_inference_job, str(file_id), str(save_path), db)

    return {
        "job_id": str(file_id),
        "status": "queued",
        "filename": original_name,
    }


@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """List all jobs ordered by creation date."""
    result = await db.execute(select(Job).order_by(desc(Job.created_at)))
    jobs = result.scalars().all()

    response = []
    for job in jobs:
        # Get latest snapshot for congestion level
        snap_result = await db.execute(
            select(TrafficSnapshot)
            .where(TrafficSnapshot.job_id == job.id)
            .order_by(desc(TrafficSnapshot.frame_number))
            .limit(1)
        )
        latest_snap = snap_result.scalar_one_or_none()

        job_data = JobResponse.model_validate(job)
        if latest_snap:
            job_data.congestion_level = latest_snap.congestion_level
        response.append(job_data.model_dump(mode="json"))

    return response


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get a single job by ID."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(select(Job).where(Job.id == uid))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get latest snapshot
    snap_result = await db.execute(
        select(TrafficSnapshot)
        .where(TrafficSnapshot.job_id == uid)
        .order_by(desc(TrafficSnapshot.frame_number))
        .limit(1)
    )
    latest_snap = snap_result.scalar_one_or_none()

    job_data = JobResponse.model_validate(job)
    if latest_snap:
        job_data.congestion_level = latest_snap.congestion_level

    return job_data.model_dump(mode="json")


@router.get("/jobs/{job_id}/history")
async def get_history(
    job_id: str, limit: int = 300, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get traffic snapshot history for charts."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        return []

    result = await db.execute(
        select(
            TrafficSnapshot.frame_number,
            TrafficSnapshot.total_vehicles,
            TrafficSnapshot.avg_speed_kmh,
            TrafficSnapshot.congestion_level,
            TrafficSnapshot.timestamp,
        )
        .where(TrafficSnapshot.job_id == uid)
        .order_by(TrafficSnapshot.frame_number)
        .limit(limit)
    )
    rows = result.all()
    return [
        HistoryPoint(
            frame_number=r.frame_number,
            total_vehicles=r.total_vehicles,
            avg_speed_kmh=r.avg_speed_kmh,
            congestion_level=r.congestion_level,
            timestamp=r.timestamp,
        ).model_dump(mode="json")
        for r in rows
    ]


@router.get("/jobs/{job_id}/incidents")
async def get_incidents(
    job_id: str, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all incidents for a job."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        return []

    result = await db.execute(
        select(Incident)
        .where(Incident.job_id == uid)
        .order_by(Incident.detected_at)
    )
    incidents = result.scalars().all()
    return [IncidentResponse.model_validate(i).model_dump(mode="json") for i in incidents]


@router.get("/jobs/{job_id}/summary")
async def get_summary(
    job_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get aggregate summary stats for a completed job."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(select(Job).where(Job.id == uid))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Aggregate queries
    peak_result = await db.execute(
        select(func.max(TrafficSnapshot.total_vehicles))
        .where(TrafficSnapshot.job_id == uid)
    )
    peak_vehicles = peak_result.scalar() or 0

    avg_speed_result = await db.execute(
        select(func.avg(TrafficSnapshot.avg_speed_kmh))
        .where(TrafficSnapshot.job_id == uid)
    )
    avg_speed = avg_speed_result.scalar() or 0.0

    incident_count_result = await db.execute(
        select(func.count(Incident.id)).where(Incident.job_id == uid)
    )
    total_incidents = incident_count_result.scalar() or 0

    # Congestion breakdown
    congestion_result = await db.execute(
        select(
            TrafficSnapshot.congestion_level,
            func.count(TrafficSnapshot.id),
        )
        .where(TrafficSnapshot.job_id == uid)
        .group_by(TrafficSnapshot.congestion_level)
    )
    congestion_breakdown = {row[0]: row[1] for row in congestion_result.all()}

    # Duration
    duration_seconds = 0.0
    if job.started_at and job.completed_at:
        duration_seconds = (job.completed_at - job.started_at).total_seconds()

    # Latest crossing counts
    latest_snap_result = await db.execute(
        select(TrafficSnapshot)
        .where(TrafficSnapshot.job_id == uid)
        .order_by(desc(TrafficSnapshot.frame_number))
        .limit(1)
    )
    latest_snap = latest_snap_result.scalar_one_or_none()

    return {
        "job_id": str(uid),
        "status": job.status,
        "original_filename": job.original_filename,
        "peak_vehicle_count": peak_vehicles,
        "avg_speed_kmh": round(float(avg_speed), 1),
        "total_incidents": total_incidents,
        "total_crossings": latest_snap.crossing_total if latest_snap else 0,
        "duration_seconds": round(duration_seconds, 1),
        "congestion_breakdown": congestion_breakdown,
        "total_frames": job.total_frames,
        "processed_frames": job.processed_frames,
    }
