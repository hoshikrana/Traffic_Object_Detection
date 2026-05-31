"""WebSocket connection manager — broadcasts real-time analytics per job."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by job_id."""

    def __init__(self) -> None:
        self.active: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, job_id: str) -> None:
        """Accept and register a WebSocket connection for a job."""
        await ws.accept()
        async with self._lock:
            self.active.setdefault(job_id, set()).add(ws)
        logger.info("WebSocket connected for job %s (total: %d)", job_id, len(self.active.get(job_id, set())))

    async def disconnect(self, ws: WebSocket, job_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if job_id in self.active:
                self.active[job_id].discard(ws)
                if not self.active[job_id]:
                    del self.active[job_id]
        logger.info("WebSocket disconnected for job %s", job_id)

    async def broadcast_to_job(self, job_id: str, data: dict[str, Any]) -> None:
        """Send data to all WebSocket connections for a specific job."""
        if job_id not in self.active:
            return

        dead: set[WebSocket] = set()
        for ws in self.active[job_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                if job_id in self.active:
                    self.active[job_id] -= dead
                    if not self.active[job_id]:
                        del self.active[job_id]


# Module-level singleton
manager = ConnectionManager()
