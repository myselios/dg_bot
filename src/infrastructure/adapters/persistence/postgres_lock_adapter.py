"""
PostgresAdvisoryLockAdapter - PostgreSQL Advisory Lock implementation of LockPort.

Uses PostgreSQL's pg_advisory_lock/pg_advisory_unlock for distributed locking.
Advisory locks are session-based and automatically released when the session ends.
"""
import logging
from typing import Optional, Set

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.outbound.lock_port import LockPort, LOCK_IDS

logger = logging.getLogger(__name__)


class PostgresAdvisoryLockAdapter(LockPort):
    """
    PostgreSQL Advisory Lock adapter.

    Uses pg_try_advisory_lock for non-blocking lock acquisition
    and pg_advisory_unlock for release.

    Lock IDs are mapped from string names to integers using LOCK_IDS.
    """

    def __init__(self, session_factory):
        """
        Initialize the adapter.

        Args:
            session_factory: Async session factory (e.g., async_sessionmaker)
        """
        self._session_factory = session_factory
        self._held_locks: Set[str] = set()  # Track locks held by this adapter
        self._session: Optional[AsyncSession] = None

    async def _get_session(self) -> AsyncSession:
        """
        Get or create a persistent session for lock operations.

        Advisory locks are session-based, so we need to maintain
        the same session throughout the lock lifecycle.
        """
        if self._session is None or not self._session.is_active:
            self._session = self._session_factory()
        return self._session

    def _get_lock_id(self, lock_name: str) -> int:
        """
        Get the integer lock ID for a lock name.

        Args:
            lock_name: Lock name (e.g., "trading_cycle")

        Returns:
            Integer lock ID

        Raises:
            ValueError: If lock name is not defined
        """
        if lock_name not in LOCK_IDS:
            raise ValueError(f"Unknown lock name: {lock_name}. Available: {list(LOCK_IDS.keys())}")
        return LOCK_IDS[lock_name]

    async def acquire(
        self,
        lock_name: str,
        timeout_seconds: int = 300,
        blocking: bool = False
    ) -> bool:
        """
        Attempt to acquire a PostgreSQL advisory lock.

        Uses pg_try_advisory_lock for non-blocking acquisition.

        Args:
            lock_name: Name of the lock
            timeout_seconds: Ignored (advisory locks don't have timeout)
            blocking: If True, use pg_advisory_lock (blocking)

        Returns:
            True if lock was acquired
            False if lock is held by another session
        """
        lock_id = self._get_lock_id(lock_name)
        session = await self._get_session()

        try:
            if blocking:
                # Blocking lock - waits until available
                await session.execute(
                    text("SELECT pg_advisory_lock(:lock_id)"),
                    {"lock_id": lock_id}
                )
                acquired = True
            else:
                # Non-blocking lock - returns immediately
                result = await session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": lock_id}
                )
                acquired = result.scalar()

            if acquired:
                self._held_locks.add(lock_name)
                logger.debug(f"Lock acquired: {lock_name} (id={lock_id})")
            else:
                logger.debug(f"Lock not available: {lock_name} (id={lock_id})")

            return acquired

        except Exception as e:
            logger.error(f"Lock acquisition failed for {lock_name}: {e}")
            return False

    async def release(self, lock_name: str) -> None:
        """
        Release a PostgreSQL advisory lock.

        Uses pg_advisory_unlock to release the lock.

        Args:
            lock_name: Name of the lock to release
        """
        if lock_name not in self._held_locks:
            logger.debug(f"Lock not held, skipping release: {lock_name}")
            return

        lock_id = self._get_lock_id(lock_name)
        session = await self._get_session()

        try:
            await session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": lock_id}
            )
            self._held_locks.discard(lock_name)
            logger.debug(f"Lock released: {lock_name} (id={lock_id})")

        except Exception as e:
            logger.error(f"Lock release failed for {lock_name}: {e}")
            # Still remove from held locks to prevent inconsistency
            self._held_locks.discard(lock_name)

    async def is_locked(self, lock_name: str) -> bool:
        """
        Check if a lock is currently held by any session.

        Uses pg_locks system view to check lock status.

        Args:
            lock_name: Name of the lock to check

        Returns:
            True if lock is held
            False if lock is available
        """
        lock_id = self._get_lock_id(lock_name)
        session = await self._get_session()

        try:
            result = await session.execute(
                text("""
                    SELECT COUNT(*) > 0
                    FROM pg_locks
                    WHERE locktype = 'advisory'
                    AND objid = :lock_id
                    AND granted = true
                """),
                {"lock_id": lock_id}
            )
            return result.scalar()

        except Exception as e:
            logger.error(f"Lock status check failed for {lock_name}: {e}")
            return False

    async def release_all(self) -> None:
        """
        Release all locks held by this adapter.

        Useful for cleanup on shutdown.
        """
        for lock_name in list(self._held_locks):
            await self.release(lock_name)

    async def close(self) -> None:
        """
        Close the session and release all locks.

        Should be called when the adapter is no longer needed.
        """
        await self.release_all()
        if self._session is not None:
            await self._session.close()
            self._session = None
