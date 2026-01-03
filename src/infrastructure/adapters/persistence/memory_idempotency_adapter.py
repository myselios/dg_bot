"""
InMemoryIdempotencyAdapter - In-memory implementation of IdempotencyPort.

This adapter provides an in-memory storage for testing purposes.
All data is lost when the adapter is destroyed.
"""
from datetime import datetime, timedelta
from typing import Dict

from src.application.ports.outbound.idempotency_port import IdempotencyPort


class InMemoryIdempotencyAdapter(IdempotencyPort):
    """
    In-memory idempotency adapter for testing.

    Stores keys with expiration times in a dictionary.
    """

    def __init__(self):
        """Initialize empty storage."""
        # Dict[key, expires_at]
        self._keys: Dict[str, datetime] = {}

    def clear(self):
        """Clear all stored keys. Useful for test cleanup."""
        self._keys.clear()

    async def check_key(self, key: str) -> bool:
        """
        Check if an idempotency key exists and is not expired.

        Args:
            key: Idempotency key to check

        Returns:
            True if key exists and is valid
            False if key doesn't exist or is expired
        """
        if key not in self._keys:
            return False

        expires_at = self._keys[key]
        if datetime.now() >= expires_at:
            # Key has expired, remove it
            del self._keys[key]
            return False

        return True

    async def mark_key(self, key: str, ttl_hours: int = 24) -> None:
        """
        Mark an idempotency key as used.

        Args:
            key: Idempotency key to mark
            ttl_hours: Time-to-live in hours (default: 24)
        """
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        self._keys[key] = expires_at

    async def cleanup_expired(self) -> int:
        """
        Remove expired idempotency keys.

        Returns:
            Number of keys removed
        """
        now = datetime.now()
        expired_keys = [
            key for key, expires_at in self._keys.items()
            if now >= expires_at
        ]

        for key in expired_keys:
            del self._keys[key]

        return len(expired_keys)

    @property
    def key_count(self) -> int:
        """Get total number of keys stored (for testing)."""
        return len(self._keys)
