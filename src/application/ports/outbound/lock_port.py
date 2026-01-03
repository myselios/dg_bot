"""
LockPort - Interface for distributed locking.

This port defines the contract for acquiring and releasing locks
to prevent concurrent execution of critical sections.

Lock IDs:
- trading_cycle: 1001 - Main trading job lock
- position_management: 1002 - Position management job lock
"""
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# PostgreSQL Advisory Lock IDs
# Must be unique across the application
LOCK_IDS = {
    "trading_cycle": 1001,
    "position_management": 1002,
}


class LockPort(ABC):
    """
    Port interface for distributed locking.

    This interface defines operations for acquiring and releasing
    locks to ensure mutual exclusion of critical sections.

    Usage:
        # Using context manager (recommended)
        async with lock_port.lock("trading_cycle"):
            # Critical section
            await execute_trading_cycle()

        # Manual acquire/release
        if await lock_port.acquire("trading_cycle"):
            try:
                await execute_trading_cycle()
            finally:
                await lock_port.release("trading_cycle")
    """

    @abstractmethod
    async def acquire(
        self,
        lock_name: str,
        timeout_seconds: int = 300,
        blocking: bool = False
    ) -> bool:
        """
        Attempt to acquire a lock.

        Args:
            lock_name: Name of the lock (e.g., "trading_cycle")
            timeout_seconds: Maximum time to hold the lock (for safety)
            blocking: If True, wait until lock is available

        Returns:
            True if lock was acquired
            False if lock is held by another process
        """
        pass

    @abstractmethod
    async def release(self, lock_name: str) -> None:
        """
        Release a held lock.

        Args:
            lock_name: Name of the lock to release

        Note:
            Releasing a lock not held by this session is a no-op.
        """
        pass

    @abstractmethod
    async def is_locked(self, lock_name: str) -> bool:
        """
        Check if a lock is currently held.

        Args:
            lock_name: Name of the lock to check

        Returns:
            True if lock is held (by any process)
            False if lock is available
        """
        pass

    @asynccontextmanager
    async def lock(
        self,
        lock_name: str,
        timeout_seconds: int = 300,
        raise_on_failure: bool = False
    ) -> AsyncGenerator[bool, None]:
        """
        Context manager for lock acquisition and release.

        Args:
            lock_name: Name of the lock
            timeout_seconds: Maximum time to hold the lock
            raise_on_failure: If True, raise exception when lock unavailable

        Yields:
            True if lock was acquired, False otherwise

        Raises:
            LockAcquisitionError: If raise_on_failure=True and lock unavailable

        Example:
            async with lock_port.lock("trading_cycle") as acquired:
                if acquired:
                    await execute_trading_cycle()
                else:
                    logger.warning("Could not acquire lock, skipping")
        """
        acquired = await self.acquire(lock_name, timeout_seconds)

        if not acquired and raise_on_failure:
            raise LockAcquisitionError(f"Could not acquire lock: {lock_name}")

        try:
            yield acquired
        finally:
            if acquired:
                await self.release(lock_name)


class LockAcquisitionError(Exception):
    """Raised when lock cannot be acquired."""
    pass
