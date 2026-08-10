"""Pytest fixtures with isolated SQLite database for auth integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Ensure test settings before app import
os.environ["APP_ENV"] = "test"
os.environ["AI_PROVIDER"] = "fake"
os.environ["EMAIL_PROVIDER"] = "fake"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-32b"
os.environ["CSRF_SECRET"] = "test-csrf-secret-not-for-production-32b"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["GOOGLE_OAUTH_ENABLED"] = "false"
os.environ["ALLOWED_UPLOAD_CONTENT_TYPES"] = (
    "application/pdf,"
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
    "text/plain,text/markdown,text/csv,text/x-bibtex,application/x-bibtex,"
    "application/x-research-info-systems,application/json,image/png,image/jpeg"
)


@pytest_asyncio.fixture
async def db_engine():
    import app.models  # noqa: F401
    from app.core.config import clear_settings_cache
    from app.db.base import Base

    clear_settings_cache()
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    from app.core.config import clear_settings_cache
    from app.db.session import get_db_session
    from app.main import create_app
    from app.services.email import reset_fake_email_provider

    clear_settings_cache()
    reset_fake_email_provider()
    from app.services.storage import clear_memory_store

    clear_memory_store()
    app = create_app()

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
