"""
Tests for AnalyzeMarketUseCase.

Following TDD - RED phase: Write failing tests first.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.domain.value_objects.money import Money
from src.application.dto.analysis import (
    MarketData,
    TechnicalIndicators,
    AnalysisRequest,
    TradingDecision,
    DecisionType,
)


class TestAnalyzeMarketUseCase:
    """Tests for AnalyzeMarketUseCase."""

    @pytest.fixture
    def mock_market_data_port(self):
        """Create mock market data port."""
        mock = AsyncMock()
        mock.get_ohlcv = AsyncMock()
        mock.get_current_price = AsyncMock()
        mock.get_indicators = AsyncMock()
        mock.calculate_indicators = AsyncMock()
        return mock

    @pytest.fixture
    def mock_ai_port(self):
        """Create mock AI port."""
        mock = AsyncMock()
        mock.analyze = AsyncMock()
        mock.analyze_entry = AsyncMock()
        mock.analyze_exit = AsyncMock()
        return mock

    @pytest.fixture
    def use_case(self, mock_market_data_port, mock_ai_port):
        """Create use case with mock dependencies."""
        from src.application.use_cases.analyze_market import AnalyzeMarketUseCase
        return AnalyzeMarketUseCase(
            market_data=mock_market_data_port,
            ai=mock_ai_port,
        )

    @pytest.fixture
    def sample_market_data(self):
        """Create sample market data."""
        return [
            MarketData(
                ticker="KRW-BTC",
                timestamp=datetime.now(),
                open=Decimal("50000000"),
                high=Decimal("51000000"),
                low=Decimal("49000000"),
                close=Decimal("50500000"),
                volume=Decimal("100"),
            )
            for _ in range(10)
        ]

    @pytest.fixture
    def sample_indicators(self):
        """Create sample technical indicators."""
        return TechnicalIndicators(
            rsi=Decimal("45"),
            macd=Decimal("100"),
            macd_signal=Decimal("90"),
            bb_upper=Decimal("52000000"),
            bb_middle=Decimal("50000000"),
            bb_lower=Decimal("48000000"),
            sma_20=Decimal("50000000"),
        )

    # --- Entry Analysis Tests ---

    @pytest.mark.asyncio
    async def test_analyze_entry_returns_decision(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Analyze entry returns a trading decision."""
        # Given
        ticker = "KRW-BTC"

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = Decimal("50500000")
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze_entry.return_value = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.85"),
            reasoning="Strong bullish signals",
            risk_assessment="medium",
        )

        # When
        result = await use_case.analyze_entry(ticker)

        # Then
        assert isinstance(result, TradingDecision)
        assert result.decision == DecisionType.BUY
        assert result.confidence == Decimal("0.85")

    @pytest.mark.asyncio
    async def test_analyze_entry_collects_market_data(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Entry analysis collects market data before AI analysis."""
        # Given
        ticker = "KRW-BTC"

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = Decimal("50500000")
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze_entry.return_value = TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0.5"),
            reasoning="Neutral market",
        )

        # When
        await use_case.analyze_entry(ticker)

        # Then
        mock_market_data_port.get_ohlcv.assert_called()
        mock_market_data_port.get_current_price.assert_called_with(ticker)

    @pytest.mark.asyncio
    async def test_analyze_entry_passes_data_to_ai(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Entry analysis passes collected data to AI port."""
        # Given
        ticker = "KRW-BTC"
        current_price = Decimal("50500000")

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = current_price
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze_entry.return_value = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Buy signal",
        )

        # When
        await use_case.analyze_entry(ticker)

        # Then
        mock_ai_port.analyze_entry.assert_called_once()
        call_args = mock_ai_port.analyze_entry.call_args[0][0]
        assert isinstance(call_args, AnalysisRequest)
        assert call_args.ticker == ticker
        assert call_args.current_price == current_price

    # --- Exit Analysis Tests ---

    @pytest.mark.asyncio
    async def test_analyze_exit_with_position(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Analyze exit considers current position."""
        # Given
        ticker = "KRW-BTC"
        position_info = {
            "avg_buy_price": Decimal("48000000"),
            "volume": Decimal("0.1"),
            "profit_rate": Decimal("5.2"),
        }

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = Decimal("50500000")
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze_exit.return_value = TradingDecision(
            decision=DecisionType.SELL,
            confidence=Decimal("0.75"),
            reasoning="Take profit target reached",
        )

        # When
        result = await use_case.analyze_exit(ticker, position_info)

        # Then
        assert result.decision == DecisionType.SELL
        mock_ai_port.analyze_exit.assert_called_once()
        call_args = mock_ai_port.analyze_exit.call_args[0][0]
        assert call_args.position_info == position_info

    @pytest.mark.asyncio
    async def test_analyze_exit_returns_hold_when_no_clear_signal(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Exit analysis returns HOLD when no clear exit signal."""
        # Given
        ticker = "KRW-BTC"
        position_info = {"avg_buy_price": Decimal("50000000"), "volume": Decimal("0.1")}

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = Decimal("50100000")
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze_exit.return_value = TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0.6"),
            reasoning="No clear exit signal",
        )

        # When
        result = await use_case.analyze_exit(ticker, position_info)

        # Then
        assert result.decision == DecisionType.HOLD

    # --- Error Handling Tests ---

    @pytest.mark.asyncio
    async def test_returns_hold_on_market_data_error(self, use_case, mock_market_data_port, mock_ai_port):
        """Return HOLD decision when market data collection fails."""
        # Given
        ticker = "KRW-BTC"
        mock_market_data_port.get_ohlcv.return_value = []  # Empty data

        # When
        result = await use_case.analyze_entry(ticker)

        # Then
        assert result.decision == DecisionType.HOLD
        assert result.confidence == Decimal("0")

    @pytest.mark.asyncio
    async def test_returns_hold_on_ai_error(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Return HOLD decision when AI analysis fails."""
        # Given
        ticker = "KRW-BTC"

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = Decimal("50500000")
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze_entry.side_effect = Exception("AI service unavailable")

        # When
        result = await use_case.analyze_entry(ticker)

        # Then
        assert result.decision == DecisionType.HOLD
        assert "error" in result.reasoning.lower() or "failed" in result.reasoning.lower()

    # --- Full Analysis Tests ---

    @pytest.mark.asyncio
    async def test_full_analysis_includes_indicators(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Full analysis includes technical indicators."""
        # Given
        ticker = "KRW-BTC"

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = Decimal("50500000")
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze.return_value = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Analysis complete",
        )

        # When
        await use_case.analyze(ticker)

        # Then
        call_args = mock_ai_port.analyze.call_args[0][0]
        assert call_args.indicators == sample_indicators

    @pytest.mark.asyncio
    async def test_analysis_with_custom_interval(
        self, use_case, mock_market_data_port, mock_ai_port, sample_market_data, sample_indicators
    ):
        """Analysis can use custom time interval."""
        # Given
        ticker = "KRW-BTC"
        interval = "minute15"

        mock_market_data_port.get_ohlcv.return_value = sample_market_data
        mock_market_data_port.get_current_price.return_value = Decimal("50500000")
        mock_market_data_port.calculate_indicators.return_value = sample_indicators
        mock_ai_port.analyze.return_value = TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0.5"),
            reasoning="Neutral",
        )

        # When
        await use_case.analyze(ticker, interval=interval)

        # Then
        mock_market_data_port.get_ohlcv.assert_called_once()
        call_kwargs = mock_market_data_port.get_ohlcv.call_args
        assert call_kwargs[1].get("interval") == interval or call_kwargs[0][1] == interval


class TestAnalyzeMarketUseCaseValidation:
    """Validation tests for AnalyzeMarketUseCase."""

    @pytest.fixture
    def mock_market_data_port(self):
        """Create mock market data port."""
        return AsyncMock()

    @pytest.fixture
    def mock_ai_port(self):
        """Create mock AI port."""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_market_data_port, mock_ai_port):
        """Create use case with mock dependencies."""
        from src.application.use_cases.analyze_market import AnalyzeMarketUseCase
        return AnalyzeMarketUseCase(
            market_data=mock_market_data_port,
            ai=mock_ai_port,
        )

    @pytest.mark.asyncio
    async def test_validates_ticker_format(self, use_case):
        """Validate ticker format."""
        # Given
        invalid_ticker = "INVALID"

        # When
        result = await use_case.analyze(invalid_ticker)

        # Then
        assert result.decision == DecisionType.HOLD
        assert result.confidence == Decimal("0")

    @pytest.mark.asyncio
    async def test_validates_interval_format(self, use_case, mock_market_data_port, mock_ai_port):
        """Validate interval format."""
        # Given
        ticker = "KRW-BTC"
        invalid_interval = "invalid_interval"

        mock_market_data_port.get_ohlcv.return_value = []

        # When
        result = await use_case.analyze(ticker, interval=invalid_interval)

        # Then
        assert result.decision == DecisionType.HOLD
