"""API endpoint tests."""

import io
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /health returns 200 and status ok or degraded."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_upload_video_no_file(client: AsyncClient):
    """POST /api/jobs/upload with no file returns 422."""
    resp = await client.post("/api/jobs/upload")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_video_wrong_type(client: AsyncClient):
    """POST with a .txt file returns 400."""
    file_content = b"not a video"
    resp = await client.post(
        "/api/jobs/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_traffic_data_valid(client: AsyncClient):
    """POST /api/traffic-data with valid payload returns 200."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from db.models import Job
    from tests.conftest import test_session_factory

    job_id = uuid.uuid4()
    async with test_session_factory() as session:
        job = Job(
            id=job_id,
            status="processing",
            original_filename="test.mp4",
            input_path="/tmp/test.mp4",
        )
        session.add(job)
        await session.commit()

    payload = {
        "job_id": str(job_id),
        "frame_number": 100,
        "progress_pct": 50.0,
        "total_vehicles": 5,
        "categories": {"cars": 3, "vans": 1, "trucks": 1, "buses": 0, "others": 0},
        "avg_speed_kmh": 45.0,
        "max_speed_kmh": 62.0,
        "congestion_level": "LOW",
        "active_incidents": [],
        "crossing_counts": {"up": 2, "down": 3, "total": 5},
    }
    resp = await client.post("/api/traffic-data", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_post_traffic_data_missing_fields(client: AsyncClient):
    """POST with missing job_id returns 422."""
    payload = {"frame_number": 1}  # missing job_id
    resp = await client.post("/api/traffic-data", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_jobs_empty(client: AsyncClient):
    """GET /api/jobs returns 200 and empty list."""
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient):
    """GET /api/jobs/nonexistent returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/jobs/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_history_empty(client: AsyncClient):
    """GET /api/jobs/fake-id/history returns 200 and []."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/jobs/{fake_id}/history")
    assert resp.status_code == 200
    assert resp.json() == []
