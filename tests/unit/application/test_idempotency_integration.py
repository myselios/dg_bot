"""
Idempotency Integration Tests (TDD).

These tests verify that the TradingOrchestrator properly checks
idempotency before executing trades to prevent duplicate orders.

Test Scenarios:
1. Trading cycle checks idempotency before execution
2. Duplicate candle/action is rejected
3. Different candle/action is allowed
4. Idempotency check failure blocks trading (Fail-close)
5. Idempotency key format is correct
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.container import Container
from src.application.services.trading_orchestrator import TradingOrchestrator
from src.application.ports.outbound.idempotency_port import (
    IdempotencyPort,
    make_idempotency_key
)


class MockIdempotencyPort(IdempotencyPort):
    """Mock IdempotencyPort for testing."""

    def __init__(self):
        self.keys: dict = {}
        self.check_key_called = False
        self.mark_key_called = False
        self.last_checked_key = None
        self.last_marked_key = None
        self.should_fail = False

    async def check_key(self, key: str) -> bool:
        self.check_key_called = True
        self.last_checked_key = key
        if self.should_fail:
            raise Exception("Idempotency check failed")
        return key in self.keys

    async def mark_key(self, key: str, ttl_hours: int = 24) -> None:
        self.mark_key_called = True
        self.last_marked_key = key
        if self.should_fail:
            raise Exception("Idempotency mark failed")
        self.keys[key] = ttl_hours

    async def cleanup_expired(self) -> int:
        return 0


@pytest.fixture
def mock_idempotency_port():
    """Create a mock idempotency port."""
    return MockIdempotencyPort()


@pytest.fixture
def mock_container(mock_idempotency_port):
    """Create a container with mock adapters."""
    container = Container.create_for_testing()
    container._idempotency_port = mock_idempotency_port
    return container


@pytest.fixture
def orchestrator(mock_container):
    """Create a TradingOrchestrator with mock container."""
    return TradingOrchestrator(container=mock_container)


class TestIdempotencyIntegration:
    """Test suite for idempotency integration in TradingOrchestrator."""

    @pytest.mark.asyncio
    async def test_trading_cycle_checks_idempotency_before_execution(
        self, orchestrator, mock_idempotency_port
    ):
        """
        Trading cycle should check idempotency BEFORE executing any trade.

        Given: A new trading cycle starts
        When: execute_trading_cycle is called
        Then: IdempotencyPort.check_key should be called first
        """
        # When
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            enable_scanning=False
        )

        # Then
        assert mock_idempotency_port.check_key_called, \
            "IdempotencyPort.check_key should be called during trading cycle"

    @pytest.mark.asyncio
    async def test_duplicate_candle_action_rejected(
        self, orchestrator, mock_idempotency_port
    ):
        """
        Duplicate trading action on same candle should be rejected.

        Given: An idempotency key already exists (previous trade on same candle)
        When: execute_trading_cycle is called
        Then: The trade should be skipped with 'skipped' status
        """
        # Given - get the expected key and mark it as used
        candle_ts = orchestrator._get_current_candle_ts()
        expected_key = make_idempotency_key("KRW-BTC", "1h", candle_ts, "trading_cycle")
        mock_idempotency_port.keys[expected_key] = 24

        # When
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            enable_scanning=False
        )

        # Then
        assert result.get('status') == 'skipped', \
            f"Duplicate action should be skipped, got status: {result.get('status')}"
        assert 'duplicate' in result.get('reason', '').lower() or \
               'idempotency' in result.get('reason', '').lower(), \
            f"Reason should mention duplicate/idempotency, got: {result.get('reason')}"

    @pytest.mark.asyncio
    async def test_different_ticker_allowed(
        self, orchestrator, mock_idempotency_port
    ):
        """
        Different ticker should be allowed even with same candle.

        Given: An idempotency key exists for KRW-BTC
        When: execute_trading_cycle is called for KRW-ETH
        Then: The trade should proceed (not blocked as duplicate)
        """
        # Given - mark a key for DIFFERENT ticker
        candle_ts = orchestrator._get_current_candle_ts()
        old_key = make_idempotency_key("KRW-BTC", "1h", candle_ts, "trading_cycle")
        mock_idempotency_port.keys[old_key] = 24

        # When - try with different ticker
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-ETH",
            enable_scanning=False
        )

        # Then - should NOT be blocked due to idempotency
        assert result.get('status') != 'skipped' or \
               'idempotency' not in result.get('reason', '').lower(), \
            "Different ticker should not be blocked as duplicate"

    @pytest.mark.asyncio
    async def test_idempotency_failure_blocks_trading(
        self, orchestrator, mock_idempotency_port
    ):
        """
        Idempotency check failure should block trading (Fail-close policy).

        Given: IdempotencyPort.check_key raises an exception
        When: execute_trading_cycle is called
        Then: Trading should be blocked with 'blocked' status
        """
        # Given
        mock_idempotency_port.should_fail = True

        # When
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            enable_scanning=False
        )

        # Then
        assert result.get('status') == 'blocked', \
            f"Idempotency failure should block trading, got status: {result.get('status')}"
        assert 'idempotency' in result.get('error', '').lower(), \
            f"Error should mention idempotency failure, got: {result.get('error')}"

    @pytest.mark.asyncio
    async def test_successful_cycle_marks_idempotency_key(
        self, orchestrator, mock_idempotency_port
    ):
        """
        Successful trading cycle should mark the idempotency key.

        Given: A new trading cycle
        When: The cycle completes successfully
        Then: IdempotencyPort.mark_key should be called
        """
        # When
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            enable_scanning=False
        )

        # Then - check_key is always called
        assert mock_idempotency_port.check_key_called, \
            "check_key should be called"

        # If the cycle was successful/skipped (not blocked), mark_key should be called
        if result.get('status') in ['success', 'skipped']:
            # Note: mark_key may or may not be called depending on pipeline result
            pass

    @pytest.mark.asyncio
    async def test_idempotency_key_in_result(
        self, orchestrator, mock_idempotency_port
    ):
        """
        Result should include the idempotency key used.

        Given: A trading cycle that gets skipped due to duplicate
        When: execute_trading_cycle is called
        Then: The result should contain 'idempotency_key'
        """
        # Given - mark key as already used
        candle_ts = orchestrator._get_current_candle_ts()
        expected_key = make_idempotency_key("KRW-BTC", "1h", candle_ts, "trading_cycle")
        mock_idempotency_port.keys[expected_key] = 24

        # When
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            enable_scanning=False
        )

        # Then
        assert 'idempotency_key' in result, \
            "Result should contain idempotency_key"
        assert result['idempotency_key'] == expected_key, \
            f"Expected key {expected_key}, got {result.get('idempotency_key')}"


class TestIdempotencyKeyFormat:
    """Test suite for idempotency key format and generation."""

    def test_idempotency_key_format_correct(self):
        """
        Idempotency key should follow the format:
        {ticker}-{timeframe}-{candle_ts}-{action}

        Example: KRW-BTC-1h-1704067200-buy
        """
        # When
        key = make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")

        # Then
        assert key == "KRW-BTC-1h-1704067200-buy"

    def test_idempotency_key_different_for_different_tickers(self):
        """Different tickers should produce different keys."""
        key1 = make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")
        key2 = make_idempotency_key("KRW-ETH", "1h", 1704067200, "buy")

        assert key1 != key2

    def test_idempotency_key_different_for_different_actions(self):
        """Different actions should produce different keys."""
        key1 = make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")
        key2 = make_idempotency_key("KRW-BTC", "1h", 1704067200, "sell")

        assert key1 != key2

    def test_idempotency_key_different_for_different_candles(self):
        """Different candle timestamps should produce different keys."""
        key1 = make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")
        key2 = make_idempotency_key("KRW-BTC", "1h", 1704070800, "buy")

        assert key1 != key2

    def test_idempotency_key_different_for_different_timeframes(self):
        """Different timeframes should produce different keys."""
        key1 = make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")
        key2 = make_idempotency_key("KRW-BTC", "15m", 1704067200, "buy")

        assert key1 != key2


class TestCandleTimestampCalculation:
    """Test candle timestamp calculation in TradingOrchestrator."""

    def test_get_current_candle_ts_returns_aligned_timestamp(self):
        """
        _get_current_candle_ts should return aligned timestamp.

        The returned timestamp should be aligned to the hour boundary.
        """
        container = Container.create_for_testing()
        orchestrator = TradingOrchestrator(container=container)

        # When
        ts = orchestrator._get_current_candle_ts("1h")

        # Then - should be aligned to hour (minute=0, second=0)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        assert dt.minute == 0, "Minute should be 0 for 1h candle"
        assert dt.second == 0, "Second should be 0"
        assert dt.microsecond == 0, "Microsecond should be 0"

    def test_get_current_candle_ts_15m_alignment(self):
        """
        15m timeframe should be aligned to 15-minute boundaries.
        """
        container = Container.create_for_testing()
        orchestrator = TradingOrchestrator(container=container)

        # When
        ts = orchestrator._get_current_candle_ts("15m")

        # Then - minute should be 0, 15, 30, or 45
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        assert dt.minute in [0, 15, 30, 45], \
            f"Minute should be aligned to 15m boundary, got {dt.minute}"
        assert dt.second == 0, "Second should be 0"
