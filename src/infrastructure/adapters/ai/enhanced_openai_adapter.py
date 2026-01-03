"""
EnhancedOpenAIAdapter - Rate limiting, Circuit Breaker, HOLD fallback.

AI 서비스 장애 시 안전한 HOLD 결정을 반환하는 강화된 어댑터.
"""
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from src.application.dto.analysis import AnalysisRequest, TradingDecision, DecisionType


class CircuitState(Enum):
    """Circuit breaker state."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RateLimiter:
    """
    Rate limiter using sliding window.

    Limits API calls to max_calls per period_seconds.
    """
    max_calls: int
    period_seconds: float
    _timestamps: List[float] = field(default_factory=list)

    def acquire(self) -> bool:
        """
        Try to acquire a slot.

        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()

        # Remove expired timestamps
        cutoff = now - self.period_seconds
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

        # Check limit
        if len(self._timestamps) >= self.max_calls:
            return False

        # Record this call
        self._timestamps.append(now)
        return True

    @property
    def remaining(self) -> int:
        """Get remaining calls in current window."""
        now = time.time()
        cutoff = now - self.period_seconds
        active = [ts for ts in self._timestamps if ts > cutoff]
        return max(0, self.max_calls - len(active))


@dataclass
class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by blocking requests after threshold failures.
    """
    failure_threshold: int
    recovery_timeout: float
    failure_count: int = 0
    _state: CircuitState = CircuitState.CLOSED
    _last_failure_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Get current state."""
        return self._state

    def record_success(self) -> None:
        """Record successful call."""
        self.failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Failure in half-open -> back to open
            self._state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """
        Check if request is allowed.

        Returns:
            True if allowed, False if blocked
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    return True
            return False

        # HALF_OPEN - allow one request
        return True


class EnhancedOpenAIAdapter:
    """
    Enhanced OpenAI adapter with resilience patterns.

    Features:
    - Rate limiting
    - Circuit breaker
    - Retry with backoff
    - Safe HOLD fallback on errors
    """

    def __init__(
        self,
        rate_limit_per_minute: int = 60,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize adapter.

        Args:
            rate_limit_per_minute: Max API calls per minute
            circuit_breaker_threshold: Failures before circuit opens
            circuit_breaker_timeout: Seconds before retry after open
            max_retries: Max retry attempts
            retry_delay: Base delay between retries
        """
        self.rate_limiter = RateLimiter(
            max_calls=rate_limit_per_minute,
            period_seconds=60.0,
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout,
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def analyze(self, request: AnalysisRequest) -> TradingDecision:
        """
        Analyze market with resilience patterns.

        Args:
            request: Analysis request

        Returns:
            TradingDecision - HOLD if any protection triggers
        """
        # Check rate limit
        if not self.rate_limiter.acquire():
            return self._hold_decision("Rate limit exceeded - holding position")

        # Check circuit breaker
        if not self.circuit_breaker.allow_request():
            return self._hold_decision("Circuit breaker open - holding position")

        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = await self._call_openai(request)
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await self._wait(self.retry_delay * (attempt + 1))

        # All retries failed
        self.circuit_breaker.record_failure()
        return self._hold_decision(f"API error after retries: {last_error}")

    async def _call_openai(self, request: AnalysisRequest) -> TradingDecision:
        """
        Call OpenAI API.

        Override in subclass for actual implementation.
        """
        raise NotImplementedError("Subclass must implement _call_openai")

    async def _wait(self, seconds: float) -> None:
        """Wait for specified seconds."""
        import asyncio
        await asyncio.sleep(seconds)

    def _hold_decision(self, reason: str) -> TradingDecision:
        """Create safe HOLD decision."""
        return TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0"),
            reasoning=reason,
        )
