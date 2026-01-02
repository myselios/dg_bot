"""
Analysis DTOs for AI and market analysis.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any


class DecisionType(Enum):
    """Trading decision types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class MarketData:
    """
    Market data for analysis.

    Attributes:
        ticker: Trading pair (e.g., "KRW-BTC")
        timestamp: Data timestamp
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume
    """
    ticker: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @classmethod
    def from_ohlcv(
        cls,
        ticker: str,
        ohlcv: Dict[str, Any],
    ) -> MarketData:
        """Create from OHLCV dictionary."""
        return cls(
            ticker=ticker,
            timestamp=ohlcv.get("timestamp", datetime.now()),
            open=Decimal(str(ohlcv.get("open", 0))),
            high=Decimal(str(ohlcv.get("high", 0))),
            low=Decimal(str(ohlcv.get("low", 0))),
            close=Decimal(str(ohlcv.get("close", 0))),
            volume=Decimal(str(ohlcv.get("volume", 0))),
        )


@dataclass(frozen=True)
class TechnicalIndicators:
    """
    Technical indicators for analysis.

    Attributes:
        rsi: Relative Strength Index (0-100)
        macd: MACD line value
        macd_signal: MACD signal line
        macd_histogram: MACD histogram
        bb_upper: Bollinger Band upper
        bb_middle: Bollinger Band middle (SMA)
        bb_lower: Bollinger Band lower
        sma_20: 20-period Simple Moving Average
        sma_50: 50-period Simple Moving Average
        ema_12: 12-period Exponential Moving Average
        ema_26: 26-period Exponential Moving Average
        atr: Average True Range
        volume_sma: Volume Simple Moving Average
    """
    rsi: Optional[Decimal] = None
    macd: Optional[Decimal] = None
    macd_signal: Optional[Decimal] = None
    macd_histogram: Optional[Decimal] = None
    bb_upper: Optional[Decimal] = None
    bb_middle: Optional[Decimal] = None
    bb_lower: Optional[Decimal] = None
    sma_20: Optional[Decimal] = None
    sma_50: Optional[Decimal] = None
    ema_12: Optional[Decimal] = None
    ema_26: Optional[Decimal] = None
    atr: Optional[Decimal] = None
    volume_sma: Optional[Decimal] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TechnicalIndicators:
        """Create from dictionary."""
        def to_decimal(value: Any) -> Optional[Decimal]:
            if value is None:
                return None
            return Decimal(str(value))

        return cls(
            rsi=to_decimal(data.get("rsi")),
            macd=to_decimal(data.get("macd")),
            macd_signal=to_decimal(data.get("macd_signal")),
            macd_histogram=to_decimal(data.get("macd_histogram")),
            bb_upper=to_decimal(data.get("bb_upper")),
            bb_middle=to_decimal(data.get("bb_middle")),
            bb_lower=to_decimal(data.get("bb_lower")),
            sma_20=to_decimal(data.get("sma_20")),
            sma_50=to_decimal(data.get("sma_50")),
            ema_12=to_decimal(data.get("ema_12")),
            ema_26=to_decimal(data.get("ema_26")),
            atr=to_decimal(data.get("atr")),
            volume_sma=to_decimal(data.get("volume_sma")),
        )


@dataclass(frozen=True)
class AnalysisRequest:
    """
    Request for AI analysis.

    Attributes:
        ticker: Trading pair
        current_price: Current market price
        market_data: List of historical market data (OHLCV)
        indicators: Technical indicators
        position_info: Current position information (if any)
        additional_context: Any additional context for AI
    """
    ticker: str
    current_price: Decimal
    market_data: List[MarketData] = field(default_factory=list)
    indicators: Optional[TechnicalIndicators] = None
    position_info: Optional[Dict[str, Any]] = None
    additional_context: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class TradingDecision:
    """
    AI trading decision result.

    Attributes:
        decision: Decision type (BUY, SELL, HOLD)
        confidence: Confidence score (0.0 to 1.0)
        reasoning: Explanation for the decision
        target_price: Target price for the trade (optional)
        stop_loss_price: Stop loss price (optional)
        take_profit_price: Take profit price (optional)
        position_size_ratio: Suggested position size as ratio (0.0 to 1.0)
        risk_assessment: Risk level assessment
        key_factors: Key factors influencing the decision
        raw_response: Raw AI response (for debugging)
        created_at: When the decision was made
    """
    decision: DecisionType
    confidence: Decimal
    reasoning: str
    target_price: Optional[Decimal] = None
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    position_size_ratio: Decimal = field(default_factory=lambda: Decimal("0.3"))
    risk_assessment: str = "medium"
    key_factors: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def is_actionable(self) -> bool:
        """Check if decision requires action (not HOLD)."""
        return self.decision != DecisionType.HOLD

    def is_high_confidence(self, threshold: Decimal = Decimal("0.7")) -> bool:
        """Check if decision has high confidence."""
        return self.confidence >= threshold
