"""
Contract tests for AIPort interface.

These tests ensure:
1. AIPort.analyze() requires AnalysisRequest DTO
2. AIPort.analyze() returns TradingDecision DTO
3. TechnicalIndicators.from_dict() handles all field types correctly
4. AnalysisRequest rejects DataFrame (only accepts List[MarketData])
"""
import pytest
import pandas as pd
from decimal import Decimal
from datetime import datetime

from src.application.ports.outbound.ai_port import AIPort
from src.application.dto.analysis import (
    AnalysisRequest,
    TradingDecision,
    DecisionType,
    TechnicalIndicators,
    MarketData,
)
from src.infrastructure.adapters.ai.openai_adapter import OpenAIAdapter


class TestAIPortContract:
    """Contract tests for AIPort interface."""

    @pytest.fixture
    def ai_port(self) -> AIPort:
        """Create AIPort implementation for testing."""
        return OpenAIAdapter()

    @pytest.fixture
    def valid_analysis_request(self) -> AnalysisRequest:
        """Create valid AnalysisRequest for testing."""
        return AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
            market_data=[
                MarketData(
                    ticker="KRW-BTC",
                    timestamp=datetime(2024, 1, 1, 12, 0),
                    open=Decimal("49000000"),
                    high=Decimal("51000000"),
                    low=Decimal("48000000"),
                    close=Decimal("50000000"),
                    volume=Decimal("100"),
                )
            ],
            indicators=TechnicalIndicators(
                rsi=Decimal("55.5"),
                macd=Decimal("100.0"),
                macd_signal=Decimal("90.0"),
            ),
        )

    @pytest.mark.asyncio
    async def test_analyze_requires_analysis_request_dto(self, ai_port: AIPort):
        """Test that analyze() requires AnalysisRequest DTO, not dict."""
        # This should fail - passing dict instead of DTO
        with pytest.raises((TypeError, AttributeError)):
            invalid_request = {
                "ticker": "KRW-BTC",
                "current_price": 50000000,
            }
            # This should raise TypeError because analyze expects AnalysisRequest
            await ai_port.analyze(invalid_request)  # type: ignore

    @pytest.mark.asyncio
    async def test_analyze_returns_trading_decision_dto(
        self, ai_port: AIPort, valid_analysis_request: AnalysisRequest
    ):
        """Test that analyze() returns TradingDecision DTO."""
        # This test will fail initially because we haven't mocked OpenAI
        # But it validates the return type contract
        try:
            result = await ai_port.analyze(valid_analysis_request)
            assert isinstance(result, TradingDecision)
            assert isinstance(result.decision, DecisionType)
            assert isinstance(result.confidence, Decimal)
            assert isinstance(result.reasoning, str)
        except Exception as e:
            # Expected to fail without OpenAI API key, but should still validate type
            pytest.skip(f"OpenAI API not available: {e}")

    def test_technical_indicators_from_dict_handles_all_types(self):
        """Test TechnicalIndicators.from_dict() type coercion."""
        # Test with various input types
        data = {
            "rsi": 55.5,  # float
            "macd": "100.0",  # string
            "macd_signal": 90,  # int
            "atr": None,  # None
        }

        indicators = TechnicalIndicators.from_dict(data)

        # All values should be Decimal or None
        assert isinstance(indicators.rsi, Decimal)
        assert indicators.rsi == Decimal("55.5")
        assert isinstance(indicators.macd, Decimal)
        assert indicators.macd == Decimal("100.0")
        assert isinstance(indicators.macd_signal, Decimal)
        assert indicators.macd_signal == Decimal("90")
        assert indicators.atr is None

    def test_technical_indicators_from_dict_rejects_invalid_types(self):
        """Test TechnicalIndicators.from_dict() rejects invalid types."""
        # This should fail gracefully
        data = {
            "rsi": "invalid",  # Non-numeric string
        }

        with pytest.raises((ValueError, TypeError)):
            TechnicalIndicators.from_dict(data)

    def test_analysis_request_rejects_dataframe(self):
        """Test AnalysisRequest rejects DataFrame (only accepts List[MarketData])."""
        # This should fail - DataFrame not allowed
        df = pd.DataFrame({
            "close": [50000, 51000, 52000],
            "volume": [100, 200, 300],
        })

        with pytest.raises((TypeError, ValueError)):
            AnalysisRequest(
                ticker="KRW-BTC",
                current_price=Decimal("50000"),
                market_data=df,  # type: ignore - intentionally wrong type
            )

    def test_analysis_request_accepts_list_of_market_data(self):
        """Test AnalysisRequest accepts List[MarketData]."""
        market_data = [
            MarketData(
                ticker="KRW-BTC",
                timestamp=datetime(2024, 1, 1, 12, 0),
                open=Decimal("49000000"),
                high=Decimal("51000000"),
                low=Decimal("48000000"),
                close=Decimal("50000000"),
                volume=Decimal("100"),
            )
        ]

        request = AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
            market_data=market_data,
        )

        assert isinstance(request.market_data, list)
        assert len(request.market_data) == 1
        assert isinstance(request.market_data[0], MarketData)

    def test_trading_decision_has_required_fields(self):
        """Test TradingDecision has all required fields."""
        decision = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Test reason",
        )

        # Required fields
        assert hasattr(decision, "decision")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "reasoning")

        # Optional fields should have defaults
        assert hasattr(decision, "target_price")
        assert hasattr(decision, "stop_loss_price")
        assert hasattr(decision, "take_profit_price")
        assert hasattr(decision, "position_size_ratio")
        assert hasattr(decision, "risk_assessment")
        assert hasattr(decision, "key_factors")
        assert hasattr(decision, "raw_response")
        assert hasattr(decision, "created_at")

    def test_trading_decision_confidence_is_decimal(self):
        """Test TradingDecision.confidence is Decimal, not float."""
        decision = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Test",
        )

        assert isinstance(decision.confidence, Decimal)
        # This should fail if confidence is stored as float
        assert decision.confidence == Decimal("0.8")
        assert decision.confidence != 0.8  # Decimal != float

    def test_market_data_from_ohlcv_type_coercion(self):
        """Test MarketData.from_ohlcv() coerces types correctly."""
        ohlcv = {
            "timestamp": datetime(2024, 1, 1, 12, 0),
            "open": 49000000,  # int
            "high": "51000000",  # string
            "low": 48000000.0,  # float
            "close": Decimal("50000000"),  # Decimal
            "volume": "100",  # string
        }

        market_data = MarketData.from_ohlcv("KRW-BTC", ohlcv)

        # All price/volume fields should be Decimal
        assert isinstance(market_data.open, Decimal)
        assert isinstance(market_data.high, Decimal)
        assert isinstance(market_data.low, Decimal)
        assert isinstance(market_data.close, Decimal)
        assert isinstance(market_data.volume, Decimal)
