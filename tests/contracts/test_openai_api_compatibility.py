"""
Contract tests for OpenAI API compatibility.

These tests ensure:
1. OpenAIAdapter uses correct API parameters (max_completion_tokens, not max_tokens)
2. OpenAIAdapter handles API errors gracefully
3. API parameter changes are caught before production
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

from src.infrastructure.adapters.ai.openai_adapter import OpenAIAdapter
from src.application.dto.analysis import (
    AnalysisRequest,
    TradingDecision,
    DecisionType,
    TechnicalIndicators,
)
from src.config.settings import AIConfig


class TestOpenAIAPICompatibility:
    """Contract tests for OpenAI API compatibility."""

    @pytest.fixture
    def adapter(self) -> OpenAIAdapter:
        """Create OpenAIAdapter for testing."""
        return OpenAIAdapter()

    @pytest.fixture
    def valid_analysis_request(self) -> AnalysisRequest:
        """Create valid AnalysisRequest for testing."""
        return AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
            indicators=TechnicalIndicators(
                rsi=Decimal("55.5"),
            ),
        )

    @pytest.mark.asyncio
    async def test_uses_max_completion_tokens_not_max_tokens(
        self, adapter: OpenAIAdapter, valid_analysis_request: AnalysisRequest
    ):
        """Test OpenAIAdapter uses max_completion_tokens (GPT-5.2 requirement)."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"decision": "hold", "reason": "test", "confidence": "medium"}'))]
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        adapter._client = mock_client

        # Call analyze
        result = await adapter.analyze(valid_analysis_request)

        # Verify API call used max_completion_tokens, not max_tokens
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "max_completion_tokens" in call_kwargs
        assert call_kwargs["max_completion_tokens"] == AIConfig.MAX_TOKENS
        assert "max_tokens" not in call_kwargs  # Old parameter should not be used

    @pytest.mark.asyncio
    async def test_uses_correct_temperature(
        self, adapter: OpenAIAdapter, valid_analysis_request: AnalysisRequest
    ):
        """Test OpenAIAdapter uses correct temperature from config."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"decision": "hold", "reason": "test", "confidence": "medium"}'))]
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        adapter._client = mock_client

        await adapter.analyze(valid_analysis_request)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "temperature" in call_kwargs
        assert call_kwargs["temperature"] == AIConfig.TEMPERATURE

    @pytest.mark.asyncio
    async def test_handles_openai_api_error_gracefully(
        self, adapter: OpenAIAdapter, valid_analysis_request: AnalysisRequest
    ):
        """Test OpenAIAdapter returns HOLD on OpenAI API errors."""
        # Mock OpenAI client to raise error
        mock_client = Mock()
        mock_client.chat.completions.create = Mock(side_effect=Exception("API Error"))

        adapter._client = mock_client

        # Should not raise, should return HOLD
        result = await adapter.analyze(valid_analysis_request)

        assert isinstance(result, TradingDecision)
        assert result.decision == DecisionType.HOLD
        assert result.confidence == Decimal("0")
        assert "Analysis failed" in result.reasoning

    @pytest.mark.asyncio
    async def test_handles_json_decode_error(
        self, adapter: OpenAIAdapter, valid_analysis_request: AnalysisRequest
    ):
        """Test OpenAIAdapter handles invalid JSON response."""
        # Mock OpenAI to return invalid JSON
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is not JSON"))]
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        adapter._client = mock_client

        # Should fall back to keyword detection or return HOLD
        result = await adapter.analyze(valid_analysis_request)

        assert isinstance(result, TradingDecision)
        assert result.decision in [DecisionType.BUY, DecisionType.SELL, DecisionType.HOLD]

    @pytest.mark.asyncio
    async def test_parses_korean_json_response_correctly(
        self, adapter: OpenAIAdapter, valid_analysis_request: AnalysisRequest
    ):
        """Test OpenAIAdapter parses Korean JSON response."""
        korean_response = '''{
            "decision": "buy",
            "reason": "신규 진입 가능. RSI 55로 적정 수준.",
            "confidence": "high",
            "rejection_reasons": [],
            "safety_conditions_met": {"trend": true, "volume": true},
            "risk_conditions_detected": {"btc_risk": false},
            "key_indicators": ["RSI 적정", "거래량 충분"]
        }'''

        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=korean_response))]
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        adapter._client = mock_client

        result = await adapter.analyze(valid_analysis_request)

        assert isinstance(result, TradingDecision)
        assert result.decision == DecisionType.BUY
        assert result.confidence == Decimal("0.8")  # "high" mapped to 0.8
        assert "신규 진입 가능" in result.reasoning
        assert result.risk_assessment == "low"  # All safety met, no risks
        assert len(result.key_factors) == 2

    @pytest.mark.asyncio
    async def test_is_available_checks_api_connectivity(self, adapter: OpenAIAdapter):
        """Test is_available() checks API connectivity."""
        # Mock successful API call
        mock_client = Mock()
        mock_response = Mock()
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        adapter._client = mock_client

        result = await adapter.is_available()

        assert result is True
        # Verify it used minimal tokens for test
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_completion_tokens"] == 5

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_error(self, adapter: OpenAIAdapter):
        """Test is_available() returns False on API errors."""
        # Mock API error
        mock_client = Mock()
        mock_client.chat.completions.create = Mock(side_effect=Exception("API Down"))

        adapter._client = mock_client

        result = await adapter.is_available()

        assert result is False

    def test_confidence_string_to_decimal_mapping(self, adapter: OpenAIAdapter):
        """Test confidence string mapping (high/medium/low → Decimal)."""
        # Test _parse_decision with different confidence levels
        test_cases = [
            ('{"decision": "buy", "reason": "test", "confidence": "high"}', Decimal("0.8")),
            ('{"decision": "buy", "reason": "test", "confidence": "medium"}', Decimal("0.5")),
            ('{"decision": "buy", "reason": "test", "confidence": "low"}', Decimal("0.3")),
        ]

        for json_response, expected_confidence in test_cases:
            result = adapter._parse_decision(json_response, "KRW-BTC")
            assert result.confidence == expected_confidence
