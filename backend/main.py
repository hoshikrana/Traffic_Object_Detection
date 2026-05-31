"""FastAPI application — Traffic Analytics API."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from db.session import engine, get_db
from routers import jobs, media, traffic
from ws.manager import manager

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Redis client (optional)
redis_client = None


async def init_redis() -> None:
    """Initialize Redis connection. Non-fatal if unavailable."""
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        await redis_client.ping()
        logger.info("Redis connected at %s", redis_url)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — continuing without cache", exc)
        redis_client = None


async def run_migrations() -> None:
    """Run database schema setup. Bypasses Alembic for SQLite."""
    database_url = os.getenv("DATABASE_URL", "")
    if "sqlite" in database_url:
        from db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite database tables created directly via SQLAlchemy")
        return

    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(Path(__file__).parent / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "alembic"))

        # Run in a thread to avoid blocking
        import functools
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, functools.partial(command.upgrade, alembic_cfg, "head")
        )
        logger.info("Database migrations applied successfully")
    except Exception as exc:
        logger.warning("Migration failed (tables may already exist): %s", exc)
        # Fallback: create tables directly
        from db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created directly via SQLAlchemy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    output_dir = os.getenv("OUTPUT_DIR", "./outputs")
    Path(upload_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    await run_migrations()
    await init_redis()

    model_path = os.getenv("MODEL_PATH", "./artifacts/best_openvino_model/")
    logger.info("Server ready — model path: %s", model_path)

    yield

    # Shutdown
    if redis_client:
        await redis_client.close()
    await engine.dispose()
    logger.info("Server shutdown complete")


# Create app
app = FastAPI(
    title="Traffic Analytics API",
    version="1.0.0",
    description="Real-time traffic analytics from video using YOLO + ByteTrack",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(traffic.router, prefix="/api", tags=["Traffic"])
app.include_router(media.router, prefix="/api", tags=["Media"])

# Prometheus instrumentation
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)
except ImportError:
    logger.warning("prometheus-fastapi-instrumentator not installed, skipping metrics")


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint — verifies DB and Redis connectivity."""
    health = {"status": "ok", "db": "unknown", "redis": "unknown"}

    # Check DB
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        health["db"] = "connected"
    except Exception as exc:
        health["db"] = f"error: {exc}"
        health["status"] = "degraded"

    # Check Redis
    if redis_client:
        try:
            await redis_client.ping()
            health["redis"] = "connected"
        except Exception:
            health["redis"] = "disconnected"
    else:
        health["redis"] = "not configured"

    # Check model path
    model_path = os.getenv("MODEL_PATH", "./artifacts/best_openvino_model/")
    health["model_loaded"] = Path(model_path).exists()

    return health


@app.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint for real-time job updates."""
    await manager.connect(websocket, job_id)

    # Send initial connection confirmation
    try:
        await websocket.send_json(
            {"event": "connected", "job_id": job_id, "status": "connected"}
        )
    except Exception:
        await manager.disconnect(websocket, job_id)
        return

    try:
        while True:
            # Keep alive: receive messages (client might send pings)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=20.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"event": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket, job_id)
