"""
AIPort - Interface for AI analysis operations.

This port defines the contract for AI-based trading analysis.
Adapters implementing this interface handle communication with AI services.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.application.dto.analysis import (
    AnalysisRequest,
    TradingDecision,
)


class AIPort(ABC):
    """
    Port interface for AI trading analysis.

    This interface defines operations for AI-powered market analysis
    and trading decision making. Implementations can use different
    AI providers (OpenAI, Anthropic, local models, etc.).
    """

    @abstractmethod
    async def analyze(self, request: AnalysisRequest) -> TradingDecision:
        """
        Analyze market data and return a trading decision.

        Args:
            request: Analysis request with market data and indicators

        Returns:
            TradingDecision with recommendation and reasoning

        Raises:
            AIServiceError: If AI analysis fails
            RateLimitError: If rate limit is exceeded
        """
        pass

    @abstractmethod
    async def analyze_entry(self, request: AnalysisRequest) -> TradingDecision:
        """
        Analyze whether to enter a new position.

        Args:
            request: Analysis request for entry decision

        Returns:
            TradingDecision focused on entry opportunity
        """
        pass

    @abstractmethod
    async def analyze_exit(self, request: AnalysisRequest) -> TradingDecision:
        """
        Analyze whether to exit an existing position.

        Args:
            request: Analysis request with current position info

        Returns:
            TradingDecision focused on exit timing
        """
        pass

    @abstractmethod
    async def get_market_sentiment(
        self,
        ticker: str,
        news_context: Optional[str] = None,
    ) -> str:
        """
        Get overall market sentiment analysis.

        Args:
            ticker: Trading pair to analyze
            news_context: Optional news or context to consider

        Returns:
            Sentiment assessment (bullish, bearish, neutral)
        """
        pass

    @abstractmethod
    async def validate_signal(
        self,
        request: AnalysisRequest,
        proposed_action: str,
    ) -> bool:
        """
        Validate a proposed trading signal.

        Args:
            request: Analysis request with market context
            proposed_action: Proposed action to validate (buy/sell)

        Returns:
            True if the signal is validated
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if AI service is available.

        Returns:
            True if service is operational
        """
        pass

    @abstractmethod
    async def get_remaining_quota(self) -> Optional[int]:
        """
        Get remaining API quota/tokens.

        Returns:
            Remaining quota or None if unlimited/unknown
        """
        pass
