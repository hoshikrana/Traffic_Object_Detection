"""Test fixtures for the FastAPI backend."""

import asyncio
import os
import sys
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Override env BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["UPLOAD_DIR"] = "./test_uploads"
os.environ["OUTPUT_DIR"] = "./test_outputs"
os.environ["MODEL_PATH"] = "./test_artifacts"
os.environ["REDIS_URL"] = ""

# Add backend dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.models import Base
from db.session import get_db
from main import app

# Test database using SQLite for isolation
TEST_DB_URL = "sqlite+aiosqlite:///./test.db"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    """Create tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def create_test_dirs():
    os.makedirs("./test_uploads", exist_ok=True)
    os.makedirs("./test_outputs", exist_ok=True)
    os.makedirs("./test_artifacts", exist_ok=True)
    yield
