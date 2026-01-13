"""
ValidationPort 설정 오버라이드 시나리오 테스트

ValidationAdapter의 임계값 설정이 올바르게 적용되는지 검증합니다.

문제점 (AI-4):
- RSI 임계값 등 ValidationAdapter 하드코딩 (validation_adapter.py:44-46)
- 기본값: rsi_overbought_threshold=75.0, rsi_oversold_threshold=30.0

검증 항목:
- 커스텀 임계값이 적용되는지
- Container가 ValidationPort를 제공하는지
- ValidationResult가 올바르게 반환되는지
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.infrastructure.adapters.validation.validation_adapter import ValidationAdapter
from src.application.ports.outbound.validation_port import ValidationResult
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType


@pytest.mark.scenario
class TestValidationPortConfig:
    """ValidationPort 설정 오버라이드 시나리오"""

    def test_default_rsi_thresholds(self):
        """기본 RSI 임계값이 설정되어 있는지 확인"""
        # When: 기본 ValidationAdapter 생성
        adapter = ValidationAdapter()

        # Then: 기본 임계값이 설정됨
        assert adapter.rsi_overbought_threshold == 75.0, \
            "기본 overbought 임계값은 75.0이어야 함"
        assert adapter.rsi_oversold_threshold == 30.0, \
            "기본 oversold 임계값은 30.0이어야 함"

    def test_custom_rsi_thresholds_are_applied(self):
        """커스텀 RSI 임계값이 적용되는지 확인"""
        # Given: 커스텀 임계값
        custom_overbought = 70.0
        custom_oversold = 35.0

        # When: 커스텀 값으로 생성
        adapter = ValidationAdapter(
            rsi_overbought_threshold=custom_overbought,
            rsi_oversold_threshold=custom_oversold,
        )

        # Then: 커스텀 값이 적용됨
        assert adapter.rsi_overbought_threshold == custom_overbought
        assert adapter.rsi_oversold_threshold == custom_oversold

    @pytest.mark.asyncio
    async def test_overbought_threshold_triggers_override(self):
        """과매수 임계값 초과 시 HOLD로 오버라이드되는지 확인"""
        # Given: 낮은 overbought 임계값
        adapter = ValidationAdapter(rsi_overbought_threshold=65.0)

        # RSI 70인 상황 (65 초과)
        decision = AIDecisionResult(
            decision=DecisionType.ALLOW,
            confidence=80,
            reason="Test",
            ticker="KRW-BTC",
        )
        market_context = {"rsi": 70.0}

        # When: 검증
        result = await adapter.validate_decision(decision, market_context)

        # Then: HOLD로 오버라이드
        assert result.valid is False
        assert result.override_decision == DecisionType.HOLD
        assert "overbought" in result.message.lower()

    @pytest.mark.asyncio
    async def test_below_threshold_passes_validation(self):
        """임계값 미만일 때 검증 통과하는지 확인"""
        # Given: 기본 임계값 (75)
        adapter = ValidationAdapter()

        # RSI 60인 상황 (75 미만)
        decision = AIDecisionResult(
            decision=DecisionType.ALLOW,
            confidence=80,
            reason="Test",
            ticker="KRW-BTC",
        )
        market_context = {"rsi": 60.0}

        # When: 검증
        result = await adapter.validate_decision(decision, market_context)

        # Then: 통과
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_block_decision_always_passes(self):
        """BLOCK 결정은 항상 통과하는지 확인"""
        # Given: 어떤 임계값이든
        adapter = ValidationAdapter()

        # 과매수 상황에서 BLOCK 결정
        decision = AIDecisionResult(
            decision=DecisionType.BLOCK,
            confidence=90,
            reason="Test",
            ticker="KRW-BTC",
        )
        market_context = {"rsi": 90.0}  # 매우 높은 RSI

        # When: 검증
        result = await adapter.validate_decision(decision, market_context)

        # Then: BLOCK은 항상 통과
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_hold_decision_always_passes(self):
        """HOLD 결정은 항상 통과하는지 확인"""
        # Given: 어떤 임계값이든
        adapter = ValidationAdapter()

        decision = AIDecisionResult(
            decision=DecisionType.HOLD,
            confidence=50,
            reason="Test",
            ticker="KRW-BTC",
        )
        market_context = {"rsi": 90.0}

        # When: 검증
        result = await adapter.validate_decision(decision, market_context)

        # Then: HOLD는 항상 통과
        assert result.valid is True

    def test_min_confidence_threshold(self):
        """최소 신뢰도 임계값이 적용되는지 확인"""
        # Given: 최소 신뢰도 50
        adapter = ValidationAdapter(min_confidence=50)

        # Then: 설정이 적용됨
        assert adapter.min_confidence == 50

    @pytest.mark.asyncio
    async def test_min_confidence_rejects_low_confidence(self):
        """최소 신뢰도 미달 시 거부되는지 확인"""
        # Given: 최소 신뢰도 60
        adapter = ValidationAdapter(min_confidence=60)

        # 낮은 신뢰도 응답
        raw_response = {
            "decision": "buy",
            "confidence": 50,  # 60 미만
            "reason": "Test"
        }

        # When: 검증
        result = await adapter.validate_response(raw_response)

        # Then: 거부됨
        assert result.valid is False
        assert "confidence" in result.message.lower()

    @pytest.mark.asyncio
    async def test_min_confidence_accepts_high_confidence(self):
        """최소 신뢰도 이상일 때 통과하는지 확인"""
        # Given: 최소 신뢰도 60
        adapter = ValidationAdapter(min_confidence=60)

        raw_response = {
            "decision": "buy",
            "confidence": 70,  # 60 이상
            "reason": "Test"
        }

        # When: 검증
        result = await adapter.validate_response(raw_response)

        # Then: 통과
        assert result.valid is True


@pytest.mark.scenario
class TestValidationPortViaContainer:
    """Container를 통한 ValidationPort 접근 테스트"""

    def test_container_provides_validation_port(self):
        """Container가 ValidationPort를 제공하는지 확인"""
        from src.container import Container

        # When: Container에서 ValidationPort 획득
        container = Container()
        validation_port = container.get_validation_port()

        # Then: ValidationPort가 반환됨
        assert validation_port is not None
        # ValidationAdapter 인스턴스여야 함
        assert isinstance(validation_port, ValidationAdapter)

    def test_container_reuses_validation_port(self):
        """Container가 ValidationPort를 재사용하는지 확인"""
        from src.container import Container

        container = Container()

        # When: 두 번 호출
        port1 = container.get_validation_port()
        port2 = container.get_validation_port()

        # Then: 같은 인스턴스 반환 (캐싱)
        assert port1 is port2

    def test_custom_validation_port_can_be_injected(self):
        """커스텀 ValidationPort를 주입할 수 있는지 확인"""
        from src.container import Container

        # Given: 커스텀 ValidationAdapter
        custom_adapter = ValidationAdapter(
            rsi_overbought_threshold=60.0,
            min_confidence=70,
        )

        # When: Container에 주입
        container = Container(validation_port=custom_adapter)

        # Then: 주입된 어댑터 반환
        assert container.get_validation_port() is custom_adapter
        assert container.get_validation_port().rsi_overbought_threshold == 60.0


@pytest.mark.scenario
class TestValidationResponseFormat:
    """ValidationResult 응답 형식 테스트"""

    @pytest.mark.asyncio
    async def test_valid_response_format(self):
        """유효한 응답 형식 검증"""
        adapter = ValidationAdapter()

        raw_response = {
            "decision": "buy",
            "confidence": 80,
            "reason": "Strong signal"
        }

        result = await adapter.validate_response(raw_response)

        # ValidationResult 구조 확인
        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'valid')
        assert hasattr(result, 'message')
        assert hasattr(result, 'override_decision')
        assert hasattr(result, 'details')

    @pytest.mark.asyncio
    async def test_missing_decision_field(self):
        """decision 필드 누락 시 오류 확인"""
        adapter = ValidationAdapter()

        raw_response = {
            "confidence": 80,
            "reason": "Test"
        }

        result = await adapter.validate_response(raw_response)

        assert result.valid is False
        assert "decision" in result.message.lower()

    @pytest.mark.asyncio
    async def test_missing_confidence_field(self):
        """confidence 필드 누락 시 오류 확인"""
        adapter = ValidationAdapter()

        raw_response = {
            "decision": "buy",
            "reason": "Test"
        }

        result = await adapter.validate_response(raw_response)

        assert result.valid is False
        assert "confidence" in result.message.lower()

    @pytest.mark.asyncio
    async def test_invalid_decision_value(self):
        """잘못된 decision 값 시 오류 확인"""
        adapter = ValidationAdapter()

        raw_response = {
            "decision": "invalid_action",
            "confidence": 80,
        }

        result = await adapter.validate_response(raw_response)

        assert result.valid is False
        assert "invalid" in result.message.lower()

    @pytest.mark.asyncio
    async def test_confidence_out_of_range(self):
        """confidence 범위 초과 시 오류 확인"""
        adapter = ValidationAdapter()

        # 100 초과
        raw_response = {
            "decision": "buy",
            "confidence": 150,
        }

        result = await adapter.validate_response(raw_response)

        assert result.valid is False

        # 0 미만
        raw_response["confidence"] = -10

        result = await adapter.validate_response(raw_response)

        assert result.valid is False
