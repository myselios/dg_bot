"""
EnhancedOpenAIAdapter Tests

TDD - rate limit, circuit breaker, HOLD fallback 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import time

from src.infrastructure.adapters.ai.enhanced_openai_adapter import (
    EnhancedOpenAIAdapter,
    RateLimiter,
    CircuitBreaker,
    CircuitState,
)
from src.application.dto.analysis import AnalysisRequest, TradingDecision, DecisionType


class TestRateLimiter:
    """RateLimiter 테스트"""

    def test_create_rate_limiter(self):
        """Given: 설정 When: 생성 Then: 올바른 초기화"""
        limiter = RateLimiter(max_calls=10, period_seconds=60)

        assert limiter.max_calls == 10
        assert limiter.period_seconds == 60

    def test_allow_within_limit(self):
        """Given: 한도 이내 When: acquire Then: 허용"""
        limiter = RateLimiter(max_calls=3, period_seconds=60)

        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is True

    def test_block_over_limit(self):
        """Given: 한도 초과 When: acquire Then: 차단"""
        limiter = RateLimiter(max_calls=2, period_seconds=60)

        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is False  # 3번째 차단

    def test_reset_after_period(self):
        """Given: 기간 경과 When: acquire Then: 리셋되어 허용"""
        limiter = RateLimiter(max_calls=1, period_seconds=0.1)  # 100ms

        assert limiter.acquire() is True
        assert limiter.acquire() is False

        time.sleep(0.15)  # 150ms 대기

        assert limiter.acquire() is True  # 리셋됨

    def test_remaining_calls(self):
        """Given: 일부 사용 When: remaining Then: 남은 횟수"""
        limiter = RateLimiter(max_calls=5, period_seconds=60)

        limiter.acquire()
        limiter.acquire()

        assert limiter.remaining == 3


class TestCircuitBreaker:
    """CircuitBreaker 테스트"""

    def test_create_circuit_breaker(self):
        """Given: 설정 When: 생성 Then: CLOSED 상태"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_record_success(self):
        """Given: 성공 When: record_success Then: 실패 카운트 리셋"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        cb.failure_count = 2

        cb.record_success()

        assert cb.failure_count == 0

    def test_record_failure_below_threshold(self):
        """Given: 임계값 미만 실패 When: record_failure Then: CLOSED 유지"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

        cb.record_failure()
        cb.record_failure()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2

    def test_record_failure_at_threshold(self):
        """Given: 임계값 도달 When: record_failure Then: OPEN"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

        cb.record_failure()
        cb.record_failure()
        cb.record_failure()  # 3번째

        assert cb.state == CircuitState.OPEN

    def test_allow_request_when_closed(self):
        """Given: CLOSED 상태 When: allow_request Then: 허용"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

        assert cb.allow_request() is True

    def test_block_request_when_open(self):
        """Given: OPEN 상태 When: allow_request Then: 차단"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30)
        cb.record_failure()  # OPEN으로 전환

        assert cb.allow_request() is False

    def test_half_open_after_timeout(self):
        """Given: OPEN + 타임아웃 경과 When: allow_request Then: HALF_OPEN"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)  # 100ms
        cb.record_failure()

        time.sleep(0.15)  # 타임아웃 경과

        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_close_after_success_in_half_open(self):
        """Given: HALF_OPEN + 성공 When: record_success Then: CLOSED"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # HALF_OPEN

        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_open_after_failure_in_half_open(self):
        """Given: HALF_OPEN + 실패 When: record_failure Then: OPEN"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # HALF_OPEN

        cb.record_failure()

        assert cb.state == CircuitState.OPEN


class TestEnhancedOpenAIAdapterCreation:
    """EnhancedOpenAIAdapter 생성 테스트"""

    def test_create_with_defaults(self):
        """Given: 기본값 When: 생성 Then: 기본 설정"""
        adapter = EnhancedOpenAIAdapter()

        assert adapter.rate_limiter is not None
        assert adapter.circuit_breaker is not None

    def test_create_with_custom_config(self):
        """Given: 커스텀 설정 When: 생성 Then: 설정 적용"""
        adapter = EnhancedOpenAIAdapter(
            rate_limit_per_minute=30,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=120,
        )

        assert adapter.rate_limiter.max_calls == 30
        assert adapter.circuit_breaker.failure_threshold == 5


class TestEnhancedOpenAIAdapterAnalyze:
    """analyze 메서드 테스트"""

    @pytest.fixture
    def adapter(self):
        return EnhancedOpenAIAdapter(
            rate_limit_per_minute=10,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=30,
        )

    @pytest.fixture
    def mock_request(self):
        return AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
        )

    @pytest.mark.asyncio
    async def test_hold_on_rate_limit(self, adapter, mock_request):
        """Given: rate limit 초과 When: analyze Then: HOLD 반환"""
        # rate limit 소진
        for _ in range(10):
            adapter.rate_limiter.acquire()

        result = await adapter.analyze(mock_request)

        assert result.decision == DecisionType.HOLD
        assert "rate limit" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_hold_on_circuit_open(self, adapter, mock_request):
        """Given: circuit 열림 When: analyze Then: HOLD 반환"""
        # circuit 열기
        for _ in range(3):
            adapter.circuit_breaker.record_failure()

        result = await adapter.analyze(mock_request)

        assert result.decision == DecisionType.HOLD
        assert "circuit" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_hold_on_api_error(self, adapter, mock_request):
        """Given: API 에러 When: analyze Then: HOLD 반환"""
        with patch.object(adapter, "_call_openai", side_effect=Exception("API Error")):
            result = await adapter.analyze(mock_request)

            assert result.decision == DecisionType.HOLD
            assert "error" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_success_records_success(self, adapter, mock_request):
        """Given: 성공 응답 When: analyze Then: circuit 성공 기록"""
        mock_response = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Good opportunity",
        )

        with patch.object(adapter, "_call_openai", return_value=mock_response):
            await adapter.analyze(mock_request)

            assert adapter.circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_records_failure(self, adapter, mock_request):
        """Given: 실패 응답 When: analyze Then: circuit 실패 기록"""
        with patch.object(adapter, "_call_openai", side_effect=Exception("Error")):
            await adapter.analyze(mock_request)

            assert adapter.circuit_breaker.failure_count == 1


class TestEnhancedOpenAIAdapterRetry:
    """재시도 로직 테스트"""

    @pytest.fixture
    def adapter(self):
        return EnhancedOpenAIAdapter(
            max_retries=3,
            retry_delay=0.01,  # 빠른 테스트
        )

    @pytest.fixture
    def mock_request(self):
        return AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
        )

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self, adapter, mock_request):
        """Given: 일시적 에러 When: analyze Then: 재시도 후 성공"""
        call_count = 0

        async def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return TradingDecision(
                decision=DecisionType.BUY,
                confidence=Decimal("0.8"),
                reasoning="Success",
            )

        with patch.object(adapter, "_call_openai", side_effect=mock_call):
            result = await adapter.analyze(mock_request)

            assert result.decision == DecisionType.BUY
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_hold_after_max_retries(self, adapter, mock_request):
        """Given: 모든 재시도 실패 When: analyze Then: HOLD"""
        with patch.object(adapter, "_call_openai", side_effect=Exception("Persistent error")):
            result = await adapter.analyze(mock_request)

            assert result.decision == DecisionType.HOLD
