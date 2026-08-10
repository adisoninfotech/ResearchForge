"""Reset a SQLite database schema for Playwright (create_all, not Alembic)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path


async def main() -> None:
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./playwright-auth.db")
    os.environ.setdefault("AI_PROVIDER", "fake")
    os.environ.setdefault("EMAIL_PROVIDER", "fake")
    os.environ.setdefault("SECRET_KEY", "playwright-secret-key-not-for-production")
    os.environ.setdefault("CSRF_SECRET", "playwright-csrf-secret-not-for-production")

    # Remove stale file so schema matches current models.
    db_path = Path("playwright-auth.db")
    if db_path.exists():
        db_path.unlink()

    import app.models  # noqa: F401
    from app.core.config import clear_settings_cache
    from app.db.base import Base
    from sqlalchemy.ext.asyncio import create_async_engine

    clear_settings_cache()
    engine = create_async_engine(os.environ["DATABASE_URL"], future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("playwright db ready")


if __name__ == "__main__":
    asyncio.run(main())
