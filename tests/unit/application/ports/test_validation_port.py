"""
ValidationPort Interface Tests

TDD - 검증 Port 인터페이스 정의
"""
import pytest
from abc import ABC
from typing import Dict, Any, Tuple

from src.application.ports.outbound.validation_port import ValidationPort, ValidationResult
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType


class MockValidationAdapter(ValidationPort):
    """테스트용 Mock 어댑터"""

    async def validate_response(self, raw_response: Dict[str, Any]) -> ValidationResult:
        if "decision" in raw_response and "confidence" in raw_response:
            return ValidationResult(valid=True, message="Valid response")
        return ValidationResult(valid=False, message="Missing required fields")

    async def validate_decision(
        self,
        decision: AIDecisionResult,
        market_context: Dict[str, Any],
    ) -> ValidationResult:
        # RSI 모순 체크
        rsi = market_context.get("rsi", 50)
        if decision.decision == DecisionType.ALLOW and rsi > 70:
            return ValidationResult(
                valid=False,
                message="RSI overbought contradicts ALLOW decision",
                override_decision=DecisionType.BLOCK,
            )
        return ValidationResult(valid=True, message="Decision validated")

    async def validate_json_schema(
        self,
        data: Dict[str, Any],
        schema_name: str,
    ) -> ValidationResult:
        return ValidationResult(valid=True, message="Schema valid")


class TestValidationPortInterface:
    """ValidationPort 인터페이스 테스트"""

    def test_is_abstract(self):
        """Given: ValidationPort When: 인스턴스화 시도 Then: TypeError"""
        with pytest.raises(TypeError):
            ValidationPort()

    def test_inherits_abc(self):
        """Given: ValidationPort When: 부모 클래스 확인 Then: ABC"""
        assert issubclass(ValidationPort, ABC)


class TestValidationResult:
    """ValidationResult 테스트"""

    def test_valid_result(self):
        """Given: 유효한 결과 When: 생성 Then: valid=True"""
        result = ValidationResult(valid=True, message="OK")
        assert result.valid is True
        assert result.override_decision is None

    def test_invalid_result_with_override(self):
        """Given: 무효 결과 + 오버라이드 When: 생성 Then: override 포함"""
        result = ValidationResult(
            valid=False,
            message="Risk detected",
            override_decision=DecisionType.BLOCK,
        )
        assert result.valid is False
        assert result.override_decision == DecisionType.BLOCK


class TestValidationPortMethods:
    """ValidationPort 메서드 테스트 (Mock 사용)"""

    @pytest.fixture
    def adapter(self):
        return MockValidationAdapter()

    @pytest.mark.asyncio
    async def test_validate_response_valid(self, adapter):
        """Given: 유효한 응답 When: validate_response Then: 유효"""
        response = {"decision": "allow", "confidence": 85, "reason": "Good"}
        result = await adapter.validate_response(response)

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_response_invalid(self, adapter):
        """Given: 무효 응답 When: validate_response Then: 무효"""
        response = {"some_field": "value"}  # decision/confidence 없음
        result = await adapter.validate_response(response)

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_validate_decision_pass(self, adapter):
        """Given: 유효한 판단 When: validate_decision Then: 통과"""
        decision = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        context = {"rsi": 55}

        result = await adapter.validate_decision(decision, context)

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_decision_override(self, adapter):
        """Given: 모순된 판단 When: validate_decision Then: 오버라이드"""
        decision = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        context = {"rsi": 78}  # 과매수인데 ALLOW

        result = await adapter.validate_decision(decision, context)

        assert result.valid is False
        assert result.override_decision == DecisionType.BLOCK

    @pytest.mark.asyncio
    async def test_validate_json_schema(self, adapter):
        """Given: 데이터 When: validate_json_schema Then: 스키마 검증"""
        data = {"decision": "allow", "confidence": 85}
        result = await adapter.validate_json_schema(data, "ai_response")

        assert result.valid is True
