"""
AnalyzeMarketUseCase - Business logic for market analysis.

This use case coordinates between market data collection and AI analysis
to produce trading decisions.
"""
from decimal import Decimal
from typing import Optional, Dict, Any
import re

from src.application.ports.outbound.market_data_port import MarketDataPort
from src.application.ports.outbound.ai_port import AIPort
from src.application.dto.analysis import (
    AnalysisRequest,
    TradingDecision,
    DecisionType,
    TechnicalIndicators,
)


# Valid intervals for market data
VALID_INTERVALS = {
    "minute1", "minute3", "minute5", "minute10", "minute15",
    "minute30", "minute60", "minute240", "day", "week", "month"
}

# Ticker format pattern
TICKER_PATTERN = re.compile(r"^KRW-[A-Z]{2,10}$")


class AnalyzeMarketUseCase:
    """
    Use case for market analysis.

    Coordinates market data collection and AI analysis to produce
    trading decisions for entry and exit.
    """

    def __init__(
        self,
        market_data: MarketDataPort,
        ai: AIPort,
    ):
        """
        Initialize with required ports.

        Args:
            market_data: Port for market data collection
            ai: Port for AI analysis
        """
        self.market_data = market_data
        self.ai = ai

    async def analyze(
        self,
        ticker: str,
        interval: str = "minute60",
    ) -> TradingDecision:
        """
        Perform full market analysis.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")
            interval: Time interval for analysis

        Returns:
            TradingDecision with analysis result
        """
        # Validate inputs
        if not self._validate_ticker(ticker):
            return self._error_decision("Invalid ticker format")

        if interval not in VALID_INTERVALS:
            return self._error_decision(f"Invalid interval: {interval}")

        try:
            # Collect market data
            market_data = await self.market_data.get_ohlcv(
                ticker=ticker,
                interval=interval,
                count=200,
            )

            if not market_data:
                return self._error_decision("No market data available")

            # Get current price
            current_price = await self.market_data.get_current_price(ticker)

            # Calculate technical indicators
            indicators = await self.market_data.calculate_indicators(market_data)

            # Build analysis request
            request = AnalysisRequest(
                ticker=ticker,
                current_price=current_price,
                market_data=market_data,
                indicators=indicators,
            )

            # Get AI analysis
            decision = await self.ai.analyze(request)
            return decision

        except Exception as e:
            return self._error_decision(f"Analysis failed: {str(e)}")

    async def analyze_entry(
        self,
        ticker: str,
        interval: str = "minute60",
    ) -> TradingDecision:
        """
        Analyze whether to enter a new position.

        Args:
            ticker: Trading pair
            interval: Time interval for analysis

        Returns:
            TradingDecision for entry
        """
        # Validate inputs
        if not self._validate_ticker(ticker):
            return self._error_decision("Invalid ticker format")

        try:
            # Collect market data
            market_data = await self.market_data.get_ohlcv(
                ticker=ticker,
                interval=interval,
                count=200,
            )

            if not market_data:
                return self._error_decision("No market data available")

            # Get current price
            current_price = await self.market_data.get_current_price(ticker)

            # Calculate technical indicators
            indicators = await self.market_data.calculate_indicators(market_data)

            # Build analysis request
            request = AnalysisRequest(
                ticker=ticker,
                current_price=current_price,
                market_data=market_data,
                indicators=indicators,
                additional_context={"analysis_type": "entry"},
            )

            # Get AI entry analysis
            decision = await self.ai.analyze_entry(request)
            return decision

        except Exception as e:
            return self._error_decision(f"Entry analysis failed: {str(e)}")

    async def analyze_exit(
        self,
        ticker: str,
        position_info: Dict[str, Any],
        interval: str = "minute60",
    ) -> TradingDecision:
        """
        Analyze whether to exit an existing position.

        Args:
            ticker: Trading pair
            position_info: Information about current position
            interval: Time interval for analysis

        Returns:
            TradingDecision for exit
        """
        # Validate inputs
        if not self._validate_ticker(ticker):
            return self._error_decision("Invalid ticker format")

        try:
            # Collect market data
            market_data = await self.market_data.get_ohlcv(
                ticker=ticker,
                interval=interval,
                count=200,
            )

            if not market_data:
                return self._error_decision("No market data available")

            # Get current price
            current_price = await self.market_data.get_current_price(ticker)

            # Calculate technical indicators
            indicators = await self.market_data.calculate_indicators(market_data)

            # Build analysis request with position info
            request = AnalysisRequest(
                ticker=ticker,
                current_price=current_price,
                market_data=market_data,
                indicators=indicators,
                position_info=position_info,
                additional_context={"analysis_type": "exit"},
            )

            # Get AI exit analysis
            decision = await self.ai.analyze_exit(request)
            return decision

        except Exception as e:
            return self._error_decision(f"Exit analysis failed: {str(e)}")

    async def get_quick_indicators(
        self,
        ticker: str,
        interval: str = "minute60",
    ) -> Optional[TechnicalIndicators]:
        """
        Get technical indicators without full AI analysis.

        Args:
            ticker: Trading pair
            interval: Time interval

        Returns:
            TechnicalIndicators or None on error
        """
        if not self._validate_ticker(ticker):
            return None

        try:
            return await self.market_data.get_indicators(ticker, interval)
        except Exception:
            return None

    def _validate_ticker(self, ticker: str) -> bool:
        """Validate ticker format."""
        return bool(TICKER_PATTERN.match(ticker))

    def _error_decision(self, reason: str) -> TradingDecision:
        """Create an error/hold decision."""
        return TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0"),
            reasoning=reason,
        )
