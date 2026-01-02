"""
OpenAIAdapter - OpenAI implementation of AIPort.

This adapter wraps OpenAI API calls for AI-based trading analysis.
"""
import json
import os
from decimal import Decimal
from typing import Optional
from datetime import datetime

from src.application.ports.outbound.ai_port import AIPort
from src.application.dto.analysis import (
    AnalysisRequest,
    TradingDecision,
    DecisionType,
)
from src.config.settings import AIConfig


class OpenAIAdapter(AIPort):
    """
    OpenAI adapter implementing AIPort.

    Uses OpenAI API for trading analysis and decision making.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key (uses env OPENAI_API_KEY if not provided)
            model: Model to use (uses AIConfig.MODEL if not provided)
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._model = model or AIConfig.MODEL
        self._client = None

    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError("openai package is required for OpenAIAdapter")
        return self._client

    async def analyze(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze market data and return a trading decision."""
        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(request)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=AIConfig.TEMPERATURE,
                max_tokens=AIConfig.MAX_TOKENS,
            )

            # Parse response
            raw_response = response.choices[0].message.content
            return self._parse_decision(raw_response, request.ticker)

        except Exception as e:
            # Return HOLD on error
            return TradingDecision(
                decision=DecisionType.HOLD,
                confidence=Decimal("0"),
                reasoning=f"Analysis failed: {str(e)}",
                raw_response=str(e),
            )

    async def analyze_entry(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze whether to enter a new position."""
        # Add entry-specific context
        request_with_context = AnalysisRequest(
            ticker=request.ticker,
            current_price=request.current_price,
            market_data=request.market_data,
            indicators=request.indicators,
            position_info=None,  # No existing position
            additional_context={"analysis_type": "entry"},
        )
        return await self.analyze(request_with_context)

    async def analyze_exit(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze whether to exit an existing position."""
        # Add exit-specific context
        if request.additional_context:
            context = dict(request.additional_context)
        else:
            context = {}
        context["analysis_type"] = "exit"

        request_with_context = AnalysisRequest(
            ticker=request.ticker,
            current_price=request.current_price,
            market_data=request.market_data,
            indicators=request.indicators,
            position_info=request.position_info,
            additional_context=context,
        )
        return await self.analyze(request_with_context)

    async def get_market_sentiment(
        self,
        ticker: str,
        news_context: Optional[str] = None,
    ) -> str:
        """Get overall market sentiment analysis."""
        try:
            prompt = f"Analyze the current market sentiment for {ticker}."
            if news_context:
                prompt += f"\n\nRecent news context:\n{news_context}"
            prompt += "\n\nRespond with only one word: bullish, bearish, or neutral."

            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=10,
            )

            sentiment = response.choices[0].message.content.strip().lower()
            if sentiment in ["bullish", "bearish", "neutral"]:
                return sentiment
            return "neutral"

        except Exception:
            return "neutral"

    async def validate_signal(
        self,
        request: AnalysisRequest,
        proposed_action: str,
    ) -> bool:
        """Validate a proposed trading signal."""
        try:
            decision = await self.analyze(request)

            if proposed_action.lower() == "buy":
                return decision.decision == DecisionType.BUY
            elif proposed_action.lower() == "sell":
                return decision.decision == DecisionType.SELL

            return False
        except Exception:
            return False

    async def is_available(self) -> bool:
        """Check if AI service is available."""
        try:
            # Test with a simple request
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return response is not None
        except Exception:
            return False

    async def get_remaining_quota(self) -> Optional[int]:
        """Get remaining API quota/tokens."""
        # OpenAI doesn't provide a direct quota check
        return None

    def _get_system_prompt(self) -> str:
        """Get system prompt for trading analysis."""
        return """You are an expert cryptocurrency trading analyst.
Analyze the provided market data and technical indicators to make trading decisions.
Always respond in JSON format with the following structure:
{
    "decision": "buy" | "sell" | "hold",
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "key_factors": ["factor1", "factor2"],
    "risk_assessment": "low" | "medium" | "high"
}
Be conservative and prioritize risk management."""

    def _build_analysis_prompt(self, request: AnalysisRequest) -> str:
        """Build analysis prompt from request."""
        parts = [
            f"Ticker: {request.ticker}",
            f"Current Price: {request.current_price}",
        ]

        if request.indicators:
            parts.append("\nTechnical Indicators:")
            if request.indicators.rsi:
                parts.append(f"- RSI: {request.indicators.rsi}")
            if request.indicators.macd:
                parts.append(f"- MACD: {request.indicators.macd}")
            if request.indicators.bb_upper:
                parts.append(
                    f"- Bollinger Bands: {request.indicators.bb_lower} - "
                    f"{request.indicators.bb_middle} - {request.indicators.bb_upper}"
                )

        if request.position_info:
            parts.append("\nCurrent Position:")
            parts.append(f"- Entry Price: {request.position_info.get('avg_buy_price')}")
            parts.append(f"- Current P/L: {request.position_info.get('profit_rate')}%")

        if request.additional_context:
            analysis_type = request.additional_context.get("analysis_type", "general")
            parts.append(f"\nAnalysis Type: {analysis_type}")

        parts.append("\nProvide your trading recommendation in JSON format.")

        return "\n".join(parts)

    def _parse_decision(self, raw_response: str, ticker: str) -> TradingDecision:
        """Parse AI response into TradingDecision."""
        try:
            # Try to extract JSON from response
            json_start = raw_response.find("{")
            json_end = raw_response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = raw_response[json_start:json_end]
                data = json.loads(json_str)

                decision_str = data.get("decision", "hold").lower()
                decision_map = {
                    "buy": DecisionType.BUY,
                    "sell": DecisionType.SELL,
                    "hold": DecisionType.HOLD,
                }
                decision = decision_map.get(decision_str, DecisionType.HOLD)

                return TradingDecision(
                    decision=decision,
                    confidence=Decimal(str(data.get("confidence", 0.5))),
                    reasoning=data.get("reasoning", ""),
                    risk_assessment=data.get("risk_assessment", "medium"),
                    key_factors=data.get("key_factors", []),
                    raw_response=raw_response,
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        # Fallback: simple keyword detection
        lower_response = raw_response.lower()
        if "buy" in lower_response and "don't buy" not in lower_response:
            decision = DecisionType.BUY
        elif "sell" in lower_response:
            decision = DecisionType.SELL
        else:
            decision = DecisionType.HOLD

        return TradingDecision(
            decision=decision,
            confidence=Decimal("0.5"),
            reasoning=raw_response[:500],
            raw_response=raw_response,
        )
