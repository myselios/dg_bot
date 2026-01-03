"""
Integration Test Fixtures for Adapter Tests.

Provides database session fixtures for testing PostgresPersistenceAdapter.
"""
import pytest
from typing import Callable
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from contextlib import asynccontextmanager

from backend.app.core.config import settings


@pytest.fixture(scope="function")
def db_session() -> Callable:
    """
    Provide a database session factory for testing.

    Creates a fresh engine and session factory for each test function
    to avoid connection pooling issues between tests.
    """
    # Create a fresh engine for each test
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=5,
        pool_recycle=300,
    )

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    @asynccontextmanager
    async def session_context():
        """Create a session context manager."""
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return session_context
