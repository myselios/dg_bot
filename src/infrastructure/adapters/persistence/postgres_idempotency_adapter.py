"""
PostgresIdempotencyAdapter - PostgreSQL implementation of IdempotencyPort.

Uses the idempotency_keys table to store and check idempotency keys.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.application.ports.outbound.idempotency_port import IdempotencyPort
from backend.app.models.idempotency_key import IdempotencyKey

logger = logging.getLogger(__name__)


class PostgresIdempotencyAdapter(IdempotencyPort):
    """
    PostgreSQL-based idempotency adapter.

    Stores idempotency keys in the idempotency_keys table with
    automatic expiration support.
    """

    def __init__(self, session_factory):
        """
        Initialize the adapter.

        Args:
            session_factory: Async session factory (e.g., async_sessionmaker)
        """
        self._session_factory = session_factory

    async def _get_session(self) -> AsyncSession:
        """Get a new database session."""
        return self._session_factory()

    async def check_key(self, key: str) -> bool:
        """
        Check if an idempotency key exists and is not expired.

        Args:
            key: Idempotency key to check

        Returns:
            True if key exists and is valid
            False if key doesn't exist or is expired
        """
        async with await self._get_session() as session:
            try:
                result = await session.execute(
                    select(IdempotencyKey).where(
                        IdempotencyKey.key == key,
                        IdempotencyKey.expires_at > datetime.now()
                    )
                )
                record = result.scalar_one_or_none()
                return record is not None
            except Exception as e:
                logger.error(f"Idempotency check_key failed: {e}")
                # Fail open: if we can't check, allow the operation
                return False

    async def mark_key(self, key: str, ttl_hours: int = 24) -> None:
        """
        Mark an idempotency key as used.

        Args:
            key: Idempotency key to mark
            ttl_hours: Time-to-live in hours (default: 24)

        Raises:
            PersistenceError: If marking fails (except for duplicate key)
        """
        async with await self._get_session() as session:
            try:
                expires_at = datetime.now() + timedelta(hours=ttl_hours)
                record = IdempotencyKey(
                    key=key,
                    created_at=datetime.now(),
                    expires_at=expires_at
                )
                session.add(record)
                await session.commit()
                logger.debug(f"Idempotency key marked: {key}")
            except IntegrityError:
                # Key already exists (race condition), which is fine
                await session.rollback()
                logger.debug(f"Idempotency key already exists: {key}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Idempotency mark_key failed: {e}")
                raise

    async def cleanup_expired(self) -> int:
        """
        Remove expired idempotency keys.

        Returns:
            Number of keys removed
        """
        async with await self._get_session() as session:
            try:
                result = await session.execute(
                    delete(IdempotencyKey).where(
                        IdempotencyKey.expires_at <= datetime.now()
                    )
                )
                await session.commit()
                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired idempotency keys")
                return deleted_count
            except Exception as e:
                await session.rollback()
                logger.error(f"Idempotency cleanup failed: {e}")
                return 0
