"""
InMemoryLockAdapter - In-memory implementation of LockPort.

This adapter provides an in-memory lock storage for testing purposes.
Only works within a single process.
"""
import asyncio
from typing import Dict, Set

from src.application.ports.outbound.lock_port import LockPort


class InMemoryLockAdapter(LockPort):
    """
    In-memory lock adapter for testing.

    Uses a simple set to track held locks.
    Thread-safe within a single asyncio event loop.
    """

    def __init__(self):
        """Initialize empty lock set."""
        self._locks: Set[str] = set()
        self._lock = asyncio.Lock()  # Async lock for thread safety

    def clear(self):
        """Clear all held locks. Useful for test cleanup."""
        self._locks.clear()

    async def acquire(
        self,
        lock_name: str,
        timeout_seconds: int = 300,
        blocking: bool = False
    ) -> bool:
        """
        Attempt to acquire a lock.

        Args:
            lock_name: Name of the lock
            timeout_seconds: Ignored in memory adapter
            blocking: If True, wait until lock is available

        Returns:
            True if lock was acquired
            False if lock is held
        """
        async with self._lock:
            if lock_name in self._locks:
                if not blocking:
                    return False
                # For blocking mode, we'd need to wait
                # In-memory adapter doesn't support true blocking
                return False

            self._locks.add(lock_name)
            return True

    async def release(self, lock_name: str) -> None:
        """
        Release a held lock.

        Args:
            lock_name: Name of the lock to release
        """
        async with self._lock:
            self._locks.discard(lock_name)

    async def is_locked(self, lock_name: str) -> bool:
        """
        Check if a lock is currently held.

        Args:
            lock_name: Name of the lock to check

        Returns:
            True if lock is held
            False if lock is available
        """
        return lock_name in self._locks

    @property
    def held_locks(self) -> Set[str]:
        """Get set of currently held locks (for testing)."""
        return self._locks.copy()
