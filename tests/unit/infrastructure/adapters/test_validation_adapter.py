"""
ValidationAdapter Tests

TDD - AI 응답 검증 어댑터 테스트
"""
import pytest
from decimal import Decimal
from typing import Dict, Any

from src.infrastructure.adapters.validation.validation_adapter import (
    ValidationAdapter,
)
from src.application.ports.outbound.validation_port import (
    ValidationPort,
    ValidationResult,
)
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType


class TestValidationAdapterInterface:
    """인터페이스 구현 테스트"""

    def test_implements_port(self):
        """Given: ValidationAdapter When: 타입 확인 Then: Port 구현"""
        adapter = ValidationAdapter()
        assert isinstance(adapter, ValidationPort)


class TestValidateResponse:
    """validate_response 메서드 테스트"""

    @pytest.fixture
    def adapter(self):
        return ValidationAdapter()

    @pytest.mark.asyncio
    async def test_valid_response(self, adapter):
        """Given: 유효한 응답 When: validate_response Then: valid=True"""
        response = {
            "decision": "allow",
            "confidence": 85,
            "reason": "Strong momentum detected",
        }

        result = await adapter.validate_response(response)

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_missing_decision(self, adapter):
        """Given: decision 없음 When: validate_response Then: valid=False"""
        response = {
            "confidence": 85,
            "reason": "No decision field",
        }

        result = await adapter.validate_response(response)

        assert result.valid is False
        assert "decision" in result.message.lower()

    @pytest.mark.asyncio
    async def test_missing_confidence(self, adapter):
        """Given: confidence 없음 When: validate_response Then: valid=False"""
        response = {
            "decision": "hold",
            "reason": "No confidence",
        }

        result = await adapter.validate_response(response)

        assert result.valid is False
        assert "confidence" in result.message.lower()

    @pytest.mark.asyncio
    async def test_invalid_decision_value(self, adapter):
        """Given: 잘못된 decision 값 When: validate_response Then: valid=False"""
        response = {
            "decision": "invalid_value",
            "confidence": 50,
            "reason": "Test",
        }

        result = await adapter.validate_response(response)

        assert result.valid is False
        assert "decision" in result.message.lower()

    @pytest.mark.asyncio
    async def test_confidence_out_of_range(self, adapter):
        """Given: 범위 초과 confidence When: validate_response Then: valid=False"""
        response = {
            "decision": "allow",
            "confidence": 150,  # > 100
            "reason": "Test",
        }

        result = await adapter.validate_response(response)

        assert result.valid is False
        assert "confidence" in result.message.lower()

    @pytest.mark.asyncio
    async def test_negative_confidence(self, adapter):
        """Given: 음수 confidence When: validate_response Then: valid=False"""
        response = {
            "decision": "allow",
            "confidence": -10,
            "reason": "Test",
        }

        result = await adapter.validate_response(response)

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_empty_response(self, adapter):
        """Given: 빈 응답 When: validate_response Then: valid=False"""
        result = await adapter.validate_response({})

        assert result.valid is False


class TestValidateDecision:
    """validate_decision 메서드 테스트"""

    @pytest.fixture
    def adapter(self):
        return ValidationAdapter()

    @pytest.fixture
    def allow_decision(self):
        return AIDecisionResult.allow("KRW-BTC", 85, "Strong momentum")

    @pytest.fixture
    def block_decision(self):
        return AIDecisionResult.block("KRW-BTC", 80, "Weak momentum")

    @pytest.mark.asyncio
    async def test_allow_with_oversold_rsi(self, adapter, allow_decision):
        """Given: ALLOW + RSI < 30 When: validate_decision Then: valid=True"""
        context = {
            "rsi": 25,
            "macd_histogram": 0.5,
        }

        result = await adapter.validate_decision(allow_decision, context)

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_allow_with_overbought_rsi(self, adapter, allow_decision):
        """Given: ALLOW + RSI > 75 When: validate_decision Then: override to HOLD"""
        context = {
            "rsi": 80,  # Overbought
            "macd_histogram": 0.5,
        }

        result = await adapter.validate_decision(allow_decision, context)

        assert result.valid is False
        assert result.override_decision == DecisionType.HOLD
        assert "overbought" in result.message.lower()

    @pytest.mark.asyncio
    async def test_allow_with_negative_macd(self, adapter, allow_decision):
        """Given: ALLOW + 강한 음수 MACD When: validate_decision Then: warning"""
        context = {
            "rsi": 50,
            "macd_histogram": -2.0,  # Strong negative
        }

        result = await adapter.validate_decision(allow_decision, context)

        # Warning but still valid (soft check)
        assert result.valid is True
        assert result.details is not None
        assert "warning" in result.details.get("level", "")

    @pytest.mark.asyncio
    async def test_block_decision_always_valid(self, adapter, block_decision):
        """Given: BLOCK 결정 When: validate_decision Then: 항상 valid"""
        context = {
            "rsi": 20,  # Oversold - would be good for entry
            "macd_histogram": 1.0,
        }

        result = await adapter.validate_decision(block_decision, context)

        # BLOCK은 항상 안전하므로 valid
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_missing_indicators(self, adapter, allow_decision):
        """Given: 지표 없음 When: validate_decision Then: valid with warning"""
        context = {}  # No indicators

        result = await adapter.validate_decision(allow_decision, context)

        # 지표 없으면 검증 불가 - warning 처리
        assert result.valid is True
        assert result.details is not None


class TestValidateJsonSchema:
    """validate_json_schema 메서드 테스트"""

    @pytest.fixture
    def adapter(self):
        return ValidationAdapter()

    @pytest.mark.asyncio
    async def test_valid_decision_schema(self, adapter):
        """Given: 유효한 decision 데이터 When: validate_json_schema Then: valid"""
        data = {
            "decision": "allow",
            "confidence": 85,
            "reason": "Test reason",
        }

        result = await adapter.validate_json_schema(data, "decision")

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_invalid_decision_schema(self, adapter):
        """Given: 잘못된 데이터 When: validate_json_schema Then: invalid"""
        data = {
            "decision": 123,  # Should be string
            "confidence": "high",  # Should be number
        }

        result = await adapter.validate_json_schema(data, "decision")

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_unknown_schema(self, adapter):
        """Given: 알 수 없는 스키마 When: validate_json_schema Then: invalid"""
        data = {"foo": "bar"}

        result = await adapter.validate_json_schema(data, "unknown_schema")

        assert result.valid is False
        assert "unknown" in result.message.lower()


class TestValidationAdapterCustomRules:
    """커스텀 검증 규칙 테스트"""

    @pytest.fixture
    def adapter(self):
        return ValidationAdapter(
            rsi_overbought_threshold=70,  # 기본 75보다 엄격
            min_confidence=70,  # 최소 신뢰도 70
        )

    @pytest.mark.asyncio
    async def test_custom_rsi_threshold(self, adapter):
        """Given: 커스텀 RSI 임계값 When: validate_decision Then: 적용됨"""
        decision = AIDecisionResult.allow("KRW-BTC", 85, "Test")
        context = {"rsi": 72}  # 70 < 72 < 75

        result = await adapter.validate_decision(decision, context)

        # 커스텀 임계값 70 적용됨
        assert result.valid is False

    @pytest.mark.asyncio
    async def test_low_confidence_blocked(self, adapter):
        """Given: 낮은 신뢰도 When: validate_response Then: invalid"""
        response = {
            "decision": "allow",
            "confidence": 60,  # < 70 threshold
            "reason": "Low confidence",
        }

        result = await adapter.validate_response(response)

        assert result.valid is False
        assert "confidence" in result.message.lower()
