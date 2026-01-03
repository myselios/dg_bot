"""
IdempotencyPort - Interface for idempotency key management.

This port defines the contract for preventing duplicate operations
(e.g., duplicate orders on the same candle).

Key format: {ticker}-{timeframe}-{candle_ts}-{action}
Example: KRW-BTC-1h-1704067200-buy
"""
from abc import ABC, abstractmethod
from typing import Optional


def make_idempotency_key(
    ticker: str,
    timeframe: str,
    candle_ts: int,
    action: str
) -> str:
    """
    Generate an idempotency key for a trading action.

    Args:
        ticker: Trading pair (e.g., "KRW-BTC")
        timeframe: Candle timeframe (e.g., "1h", "15m")
        candle_ts: Candle timestamp (Unix timestamp)
        action: Action type (e.g., "buy", "sell")

    Returns:
        Idempotency key string

    Example:
        >>> make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")
        'KRW-BTC-1h-1704067200-buy'
    """
    return f"{ticker}-{timeframe}-{candle_ts}-{action}"


class IdempotencyPort(ABC):
    """
    Port interface for idempotency key management.

    This interface defines operations for checking and marking
    idempotency keys to prevent duplicate operations.

    Usage:
        # Before executing an order
        key = make_idempotency_key(ticker, timeframe, candle_ts, action)
        if await idempotency_port.check_key(key):
            logger.info(f"Skipping duplicate: {key}")
            return

        # Execute order...

        # After successful order
        await idempotency_port.mark_key(key)
    """

    @abstractmethod
    async def check_key(self, key: str) -> bool:
        """
        Check if an idempotency key exists and is not expired.

        Args:
            key: Idempotency key to check

        Returns:
            True if key exists and is valid (operation already done)
            False if key doesn't exist or is expired (operation can proceed)
        """
        pass

    @abstractmethod
    async def mark_key(self, key: str, ttl_hours: int = 24) -> None:
        """
        Mark an idempotency key as used.

        Args:
            key: Idempotency key to mark
            ttl_hours: Time-to-live in hours (default: 24)

        Raises:
            PersistenceError: If marking fails
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """
        Remove expired idempotency keys.

        Returns:
            Number of keys removed

        Note:
            This should be called periodically (e.g., daily)
            to prevent table bloat.
        """
        pass

    async def check_and_mark(self, key: str, ttl_hours: int = 24) -> bool:
        """
        Atomically check if key exists and mark it if not.

        This is a convenience method that combines check_key and mark_key
        in a single operation.

        Args:
            key: Idempotency key
            ttl_hours: Time-to-live in hours

        Returns:
            True if key already existed (operation should be skipped)
            False if key was newly marked (operation can proceed)
        """
        if await self.check_key(key):
            return True  # Already exists, skip
        await self.mark_key(key, ttl_hours)
        return False  # Newly marked, proceed
