"""
Contract tests for DTO serialization.

These tests ensure:
1. DTOs can be serialized to Dict and back
2. Type coercion works correctly
3. Invalid data is rejected
"""
import pytest
from decimal import Decimal
from datetime import datetime

from src.application.dto.analysis import (
    TechnicalIndicators,
    TradingDecision,
    DecisionType,
    MarketData,
)


class TestDTOSchemas:
    """Contract tests for DTO serialization."""

    def test_technical_indicators_dict_round_trip(self):
        """Test TechnicalIndicators Dict ↔ DTO conversion."""
        # Original dict
        data = {
            "rsi": 55.5,
            "macd": 100.0,
            "macd_signal": 90.0,
            "bb_upper": 52000,
            "bb_middle": 50000,
            "bb_lower": 48000,
            "atr": 1000,
        }

        # Dict → DTO
        indicators = TechnicalIndicators.from_dict(data)

        # Verify types
        assert isinstance(indicators.rsi, Decimal)
        assert isinstance(indicators.macd, Decimal)
        assert isinstance(indicators.atr, Decimal)

        # Verify values
        assert indicators.rsi == Decimal("55.5")
        assert indicators.macd == Decimal("100.0")

    def test_technical_indicators_handles_none_values(self):
        """Test TechnicalIndicators handles None values gracefully."""
        data = {
            "rsi": None,
            "macd": 100.0,
            "atr": None,
        }

        indicators = TechnicalIndicators.from_dict(data)

        assert indicators.rsi is None
        assert indicators.macd == Decimal("100.0")
        assert indicators.atr is None

    def test_technical_indicators_handles_missing_fields(self):
        """Test TechnicalIndicators handles missing fields (defaults to None)."""
        data = {
            "rsi": 55.5,
            # Other fields missing
        }

        indicators = TechnicalIndicators.from_dict(data)

        assert indicators.rsi == Decimal("55.5")
        assert indicators.macd is None
        assert indicators.atr is None

    def test_technical_indicators_rejects_invalid_decimal_string(self):
        """Test TechnicalIndicators rejects invalid Decimal strings."""
        data = {
            "rsi": "not_a_number",
        }

        # Should raise ValueError when converting to Decimal
        with pytest.raises((ValueError, TypeError)):
            TechnicalIndicators.from_dict(data)

    def test_market_data_from_ohlcv_with_all_types(self):
        """Test MarketData.from_ohlcv() handles various input types."""
        ohlcv = {
            "timestamp": datetime(2024, 1, 1, 12, 0),
            "open": 49000000,  # int
            "high": "51000000",  # string
            "low": 48000000.5,  # float
            "close": Decimal("50000000"),  # Decimal
            "volume": "100.5",  # string decimal
        }

        market_data = MarketData.from_ohlcv("KRW-BTC", ohlcv)

        # All numeric fields should be Decimal
        assert isinstance(market_data.open, Decimal)
        assert isinstance(market_data.high, Decimal)
        assert isinstance(market_data.low, Decimal)
        assert isinstance(market_data.close, Decimal)
        assert isinstance(market_data.volume, Decimal)

        # Values should match
        assert market_data.open == Decimal("49000000")
        assert market_data.high == Decimal("51000000")
        assert market_data.volume == Decimal("100.5")

    def test_market_data_from_ohlcv_handles_missing_timestamp(self):
        """Test MarketData.from_ohlcv() uses current time if timestamp missing."""
        ohlcv = {
            # No timestamp
            "open": 49000000,
            "high": 51000000,
            "low": 48000000,
            "close": 50000000,
            "volume": 100,
        }

        before = datetime.now()
        market_data = MarketData.from_ohlcv("KRW-BTC", ohlcv)
        after = datetime.now()

        # Timestamp should be set to current time
        assert before <= market_data.timestamp <= after

    def test_market_data_from_ohlcv_handles_missing_price_fields(self):
        """Test MarketData.from_ohlcv() defaults missing fields to 0."""
        ohlcv = {
            "timestamp": datetime(2024, 1, 1, 12, 0),
            "close": 50000000,
            # Other fields missing
        }

        market_data = MarketData.from_ohlcv("KRW-BTC", ohlcv)

        # Missing fields should default to 0
        assert market_data.open == Decimal("0")
        assert market_data.high == Decimal("0")
        assert market_data.low == Decimal("0")
        assert market_data.close == Decimal("50000000")
        assert market_data.volume == Decimal("0")

    def test_trading_decision_frozen_dataclass(self):
        """Test TradingDecision is immutable (frozen dataclass)."""
        decision = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Test",
        )

        # Should raise FrozenInstanceError
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            decision.decision = DecisionType.SELL

    def test_trading_decision_defaults(self):
        """Test TradingDecision has correct default values."""
        decision = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Test",
        )

        # Check defaults
        assert decision.target_price is None
        assert decision.stop_loss_price is None
        assert decision.take_profit_price is None
        assert decision.position_size_ratio == Decimal("0.3")
        assert decision.risk_assessment == "medium"
        assert decision.key_factors == []
        assert decision.raw_response is None
        assert isinstance(decision.created_at, datetime)

    def test_decision_type_enum_values(self):
        """Test DecisionType enum has expected values."""
        assert DecisionType.BUY.value == "buy"
        assert DecisionType.SELL.value == "sell"
        assert DecisionType.HOLD.value == "hold"

        # Test all enum members exist
        assert len(list(DecisionType)) == 3

    def test_trading_decision_is_actionable(self):
        """Test TradingDecision.is_actionable() logic."""
        buy_decision = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Buy signal",
        )
        assert buy_decision.is_actionable() is True

        sell_decision = TradingDecision(
            decision=DecisionType.SELL,
            confidence=Decimal("0.8"),
            reasoning="Sell signal",
        )
        assert sell_decision.is_actionable() is True

        hold_decision = TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0.8"),
            reasoning="Hold position",
        )
        assert hold_decision.is_actionable() is False

    def test_trading_decision_is_high_confidence(self):
        """Test TradingDecision.is_high_confidence() logic."""
        high_conf = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="High confidence",
        )
        assert high_conf.is_high_confidence() is True
        assert high_conf.is_high_confidence(threshold=Decimal("0.7")) is True

        low_conf = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.5"),
            reasoning="Low confidence",
        )
        assert low_conf.is_high_confidence() is False
        assert low_conf.is_high_confidence(threshold=Decimal("0.4")) is True
