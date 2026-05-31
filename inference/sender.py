"""Async HTTP sender — streams analytics to the FastAPI backend with retry logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .config import RETRY_BACKOFF_SECONDS

logger = logging.getLogger(__name__)


class AnalyticsSender:
    """Sends analytics payloads to the FastAPI backend via HTTP POST."""

    def __init__(self, job_id: str, api_base_url: str) -> None:
        self.job_id = job_id
        self.api_base_url = api_base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=5.0)
        self.failed_count: int = 0
        self.success_count: int = 0

    async def send_analytics(self, analytics: dict[str, Any], progress_pct: float) -> bool:
        """Send an analytics snapshot to the backend. Returns True on success."""
        payload = {
            **analytics,
            "job_id": self.job_id,
            "progress_pct": round(progress_pct, 1),
        }
        url = f"{self.api_base_url}/api/traffic-data"

        for attempt, backoff in enumerate(RETRY_BACKOFF_SECONDS):
            try:
                resp = await self.client.post(url, json=payload)
                if resp.status_code == 200:
                    self.success_count += 1
                    return True
                logger.warning(
                    "Analytics send attempt %d got status %d",
                    attempt + 1,
                    resp.status_code,
                )
                await asyncio.sleep(backoff)
            except Exception as exc:
                logger.warning("Analytics send attempt %d failed: %s", attempt + 1, exc)
                if attempt < len(RETRY_BACKOFF_SECONDS) - 1:
                    await asyncio.sleep(backoff)
                else:
                    self.failed_count += 1
                    logger.error("Analytics send failed after all retries.")
        return False

    async def send_complete(self, summary: dict[str, Any]) -> bool:
        """Notify the backend that inference is complete."""
        url = f"{self.api_base_url}/api/jobs/{self.job_id}/complete"
        try:
            resp = await self.client.post(url, json=summary)
            return resp.status_code == 200
        except Exception as exc:
            logger.error("Failed to send completion signal: %s", exc)
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
