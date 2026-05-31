"""Job runner service — manages inference subprocess lifecycle.

Note: The actual subprocess spawning is handled in routers/jobs.py
as a FastAPI background task. This module provides utility functions
for job management.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Job

logger = logging.getLogger(__name__)


async def mark_job_failed(
    session: AsyncSession, job_id: str, error_message: str
) -> None:
    """Mark a job as failed with an error message."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        logger.error("Invalid job_id: %s", job_id)
        return

    result = await session.execute(select(Job).where(Job.id == uid))
    job = result.scalar_one_or_none()
    if job:
        job.status = "failed"
        job.error_message = error_message[:2000]
        job.completed_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info("Job %s marked as failed", job_id)


async def mark_job_processing(
    session: AsyncSession, job_id: str
) -> None:
    """Mark a job as processing."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        return

    result = await session.execute(select(Job).where(Job.id == uid))
    job = result.scalar_one_or_none()
    if job:
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        await session.commit()
