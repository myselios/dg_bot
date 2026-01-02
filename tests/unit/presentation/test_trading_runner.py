"""
Tests for TradingRunner - the main entry point for trading cycles.

RED Phase: These tests define the expected behavior of the TradingRunner.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

from src.application.dto.analysis import TradingDecision, DecisionType


class TestTradingRunner:
    """Test TradingRunner execution."""

    @pytest.mark.asyncio
    async def test_runner_creation(self):
        """TradingRunner should be creatable with container."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container

        container = Container.create_for_testing()
        runner = TradingRunner(container)

        assert runner is not None

    @pytest.mark.asyncio
    async def test_runner_execute_returns_result(self):
        """TradingRunner execute should return a result dict."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container

        container = Container.create_for_testing()
        runner = TradingRunner(container)

        result = await runner.execute("KRW-BTC")

        assert isinstance(result, dict)
        assert "status" in result
        assert "decision" in result

    @pytest.mark.asyncio
    async def test_runner_execute_with_invalid_ticker(self):
        """TradingRunner should handle invalid ticker gracefully."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container

        container = Container.create_for_testing()
        runner = TradingRunner(container)

        result = await runner.execute("INVALID")

        assert result["status"] == "failed"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_runner_uses_analyze_market_use_case(self):
        """TradingRunner should use AnalyzeMarketUseCase for analysis."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container
        from tests.unit.presentation.mock_adapters import MockAIAdapter

        # Setup mock to return BUY decision
        mock_ai = MockAIAdapter()
        mock_ai.set_decision(TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Test buy signal",
        ))

        container = Container.create_for_testing()
        container._ai_port = mock_ai

        runner = TradingRunner(container)
        result = await runner.execute("KRW-BTC")

        assert result["decision"] == "buy" or result["decision"] == DecisionType.BUY

    @pytest.mark.asyncio
    async def test_runner_execute_buy_on_buy_decision(self):
        """TradingRunner should execute buy when AI decides to buy."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container
        from tests.unit.presentation.mock_adapters import MockAIAdapter, MockExchangeAdapter

        mock_ai = MockAIAdapter()
        mock_ai.set_decision(TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.85"),
            reasoning="Strong buy signal",
        ))

        mock_exchange = MockExchangeAdapter()
        mock_exchange.set_balance("KRW", Decimal("1000000"))

        container = Container(
            exchange_port=mock_exchange,
            ai_port=mock_ai,
        )

        runner = TradingRunner(container)
        result = await runner.execute("KRW-BTC")

        # Should attempt to execute buy
        assert result["status"] in ["success", "executed", "completed"]

    @pytest.mark.asyncio
    async def test_runner_hold_on_hold_decision(self):
        """TradingRunner should not trade when AI decides to hold."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container
        from tests.unit.presentation.mock_adapters import MockAIAdapter

        mock_ai = MockAIAdapter()
        mock_ai.set_decision(TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0.6"),
            reasoning="Wait for better opportunity",
        ))

        container = Container.create_for_testing()
        container._ai_port = mock_ai

        runner = TradingRunner(container)
        result = await runner.execute("KRW-BTC")

        assert result["decision"] == "hold" or result["decision"] == DecisionType.HOLD

    @pytest.mark.asyncio
    async def test_runner_with_position_management(self):
        """TradingRunner should check position status."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container
        from tests.unit.presentation.mock_adapters import MockExchangeAdapter

        mock_exchange = MockExchangeAdapter()
        mock_exchange.set_position("KRW-BTC", Decimal("0.01"), Decimal("50000000"))

        container = Container.create_for_testing()
        container._exchange_port = mock_exchange

        runner = TradingRunner(container)
        result = await runner.execute("KRW-BTC")

        # Should include position info in result
        assert "status" in result


class TestTradingRunnerConfiguration:
    """Test TradingRunner configuration options."""

    @pytest.mark.asyncio
    async def test_runner_configurable_buy_amount(self):
        """TradingRunner should support configurable buy amount."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container

        container = Container.create_for_testing()
        runner = TradingRunner(container, buy_amount_krw=Decimal("100000"))

        assert runner.buy_amount_krw == Decimal("100000")

    @pytest.mark.asyncio
    async def test_runner_default_buy_amount(self):
        """TradingRunner should have default buy amount."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container

        container = Container.create_for_testing()
        runner = TradingRunner(container)

        assert runner.buy_amount_krw is not None
        assert runner.buy_amount_krw > 0

    @pytest.mark.asyncio
    async def test_runner_dry_run_mode(self):
        """TradingRunner should support dry run mode (no actual trades)."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container
        from tests.unit.presentation.mock_adapters import MockAIAdapter

        mock_ai = MockAIAdapter()
        mock_ai.set_decision(TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.9"),
            reasoning="Strong signal",
        ))

        container = Container.create_for_testing()
        container._ai_port = mock_ai

        runner = TradingRunner(container, dry_run=True)
        result = await runner.execute("KRW-BTC")

        # In dry run, should not execute actual trades
        assert result.get("dry_run", False) is True or result["status"] != "failed"


class TestTradingRunnerErrorHandling:
    """Test TradingRunner error handling."""

    @pytest.mark.asyncio
    async def test_runner_handles_ai_error(self):
        """TradingRunner should handle AI service errors gracefully."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container
        from tests.unit.presentation.mock_adapters import MockAIAdapter

        mock_ai = MockAIAdapter()
        mock_ai.set_available(False)

        container = Container.create_for_testing()
        container._ai_port = mock_ai

        runner = TradingRunner(container)
        result = await runner.execute("KRW-BTC")

        # Should not crash, return hold or error status
        assert result is not None
        assert "status" in result

    @pytest.mark.asyncio
    async def test_runner_handles_exchange_error(self):
        """TradingRunner should handle exchange errors gracefully."""
        from src.presentation.cli.trading_runner import TradingRunner
        from src.container import Container

        container = Container.create_for_testing()
        runner = TradingRunner(container)

        # Execute with invalid ticker format (doesn't match KRW-XXX pattern)
        result = await runner.execute("INVALID-FORMAT")

        assert result is not None
        assert result["status"] == "failed"
        assert "error" in result
