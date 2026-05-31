"""Media endpoints — serve annotated videos and thumbnails."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Job
from db.session import get_db

router = APIRouter()


@router.get("/jobs/{job_id}/video")
async def get_video(
    job_id: str, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    """Stream the annotated video file."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(select(Job).where(Job.id == uid))
    job = result.scalar_one_or_none()
    if not job or not job.output_path:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(job.output_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"annotated_{job_id}.mp4",
        headers={
            "Content-Disposition": f'inline; filename="annotated_{job_id}.mp4"',
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/jobs/{job_id}/thumbnail")
async def get_thumbnail(
    job_id: str, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """Extract and serve the first frame of the annotated video as JPEG."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(select(Job).where(Job.id == uid))
    job = result.scalar_one_or_none()
    if not job or not job.output_path:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = Path(job.output_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    # Extract first frame
    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise HTTPException(status_code=500, detail="Could not extract frame")

    # Encode to JPEG
    success, jpeg_data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise HTTPException(status_code=500, detail="Could not encode JPEG")

    return StreamingResponse(
        io.BytesIO(jpeg_data.tobytes()),
        media_type="image/jpeg",
        headers={"Cache-Control": "max-age=3600"},
    )
