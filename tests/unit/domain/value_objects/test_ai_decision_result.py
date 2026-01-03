"""
AIDecisionResult Value Object Tests

TDD - Red: 테스트 먼저 작성
AI 판단 결과를 ALLOW/BLOCK/HOLD로 단순화
"""
import pytest
from decimal import Decimal
from datetime import datetime

from src.domain.value_objects.ai_decision_result import (
    AIDecisionResult,
    DecisionType,
    DecisionConfidence,
)


class TestDecisionType:
    """판단 유형 열거형 테스트"""

    def test_decision_type_values(self):
        """Given: 판단 유형 열거형 When: 값 확인 Then: 정의된 유형 반환"""
        assert DecisionType.ALLOW.value == "allow"
        assert DecisionType.BLOCK.value == "block"
        assert DecisionType.HOLD.value == "hold"

    def test_is_actionable(self):
        """Given: 판단 유형 When: is_actionable Then: 실행 가능 여부"""
        assert DecisionType.ALLOW.is_actionable is True
        assert DecisionType.BLOCK.is_actionable is False
        assert DecisionType.HOLD.is_actionable is False


class TestDecisionConfidence:
    """판단 신뢰도 테스트"""

    def test_confidence_creation(self):
        """Given: 신뢰도 값 When: 생성 Then: 올바른 값"""
        conf = DecisionConfidence(85)
        assert conf.value == 85

    def test_confidence_validation(self):
        """Given: 범위 밖 값 When: 생성 Then: ValueError"""
        with pytest.raises(ValueError):
            DecisionConfidence(-1)

        with pytest.raises(ValueError):
            DecisionConfidence(101)

    def test_confidence_levels(self):
        """Given: 신뢰도 값 When: level 확인 Then: 수준 반환"""
        assert DecisionConfidence(90).level == "very_high"
        assert DecisionConfidence(75).level == "high"
        assert DecisionConfidence(55).level == "medium"
        assert DecisionConfidence(35).level == "low"
        assert DecisionConfidence(10).level == "very_low"

    def test_confidence_is_sufficient(self):
        """Given: 신뢰도 값 When: is_sufficient Then: 충분 여부"""
        assert DecisionConfidence(70).is_sufficient() is True
        assert DecisionConfidence(50).is_sufficient() is False
        assert DecisionConfidence(60).is_sufficient(threshold=60) is True


class TestAIDecisionResultCreation:
    """AIDecisionResult 생성 테스트"""

    def test_create_allow_decision(self):
        """Given: ALLOW 판단 When: 생성 Then: 올바른 값"""
        result = AIDecisionResult(
            decision=DecisionType.ALLOW,
            confidence=DecisionConfidence(85),
            reason="Strong breakout with volume confirmation",
            ticker="KRW-BTC",
        )

        assert result.decision == DecisionType.ALLOW
        assert result.confidence.value == 85
        assert "breakout" in result.reason.lower()
        assert result.ticker == "KRW-BTC"

    def test_create_block_decision(self):
        """Given: BLOCK 판단 When: 생성 Then: 올바른 값"""
        result = AIDecisionResult(
            decision=DecisionType.BLOCK,
            confidence=DecisionConfidence(90),
            reason="RSI overbought, high fakeout risk",
            ticker="KRW-ETH",
        )

        assert result.decision == DecisionType.BLOCK
        assert result.confidence.value == 90

    def test_create_hold_decision(self):
        """Given: HOLD 판단 When: 생성 Then: 올바른 값"""
        result = AIDecisionResult(
            decision=DecisionType.HOLD,
            confidence=DecisionConfidence(50),
            reason="Insufficient data for decision",
            ticker="KRW-XRP",
        )

        assert result.decision == DecisionType.HOLD

    def test_immutable(self):
        """Given: 생성된 객체 When: 수정 시도 Then: FrozenInstanceError"""
        result = AIDecisionResult(
            decision=DecisionType.ALLOW,
            confidence=DecisionConfidence(85),
            reason="Test",
            ticker="KRW-BTC",
        )

        with pytest.raises(Exception):
            result.decision = DecisionType.BLOCK


class TestAIDecisionResultFactoryMethods:
    """AIDecisionResult 팩토리 메서드 테스트"""

    def test_allow_factory(self):
        """Given: allow 팩토리 When: 호출 Then: ALLOW 결과"""
        result = AIDecisionResult.allow(
            ticker="KRW-BTC",
            confidence=85,
            reason="Strong signal",
        )

        assert result.decision == DecisionType.ALLOW
        assert result.confidence.value == 85
        assert result.ticker == "KRW-BTC"

    def test_block_factory(self):
        """Given: block 팩토리 When: 호출 Then: BLOCK 결과"""
        result = AIDecisionResult.block(
            ticker="KRW-BTC",
            confidence=90,
            reason="High risk detected",
        )

        assert result.decision == DecisionType.BLOCK
        assert result.confidence.value == 90

    def test_hold_factory(self):
        """Given: hold 팩토리 When: 호출 Then: HOLD 결과"""
        result = AIDecisionResult.hold(
            ticker="KRW-BTC",
            reason="Uncertain market conditions",
        )

        assert result.decision == DecisionType.HOLD
        assert result.confidence.value == 50  # 기본값

    def test_from_ai_response(self):
        """Given: AI JSON 응답 When: from_ai_response Then: 파싱된 결과"""
        ai_response = {
            "decision": "allow",
            "confidence": 85,
            "reason": "Good entry point",
        }

        result = AIDecisionResult.from_ai_response(
            response=ai_response,
            ticker="KRW-BTC",
        )

        assert result.decision == DecisionType.ALLOW
        assert result.confidence.value == 85
        assert result.reason == "Good entry point"

    def test_from_ai_response_invalid_decision(self):
        """Given: 잘못된 판단 값 When: from_ai_response Then: HOLD 반환"""
        ai_response = {
            "decision": "invalid_value",
            "confidence": 85,
            "reason": "Some reason",
        }

        result = AIDecisionResult.from_ai_response(
            response=ai_response,
            ticker="KRW-BTC",
        )

        # 잘못된 값은 HOLD로 처리 (안전 fallback)
        assert result.decision == DecisionType.HOLD

    def test_fallback(self):
        """Given: fallback 호출 When: 에러 상황 Then: HOLD 결과"""
        result = AIDecisionResult.fallback(
            ticker="KRW-BTC",
            error="API timeout",
        )

        assert result.decision == DecisionType.HOLD
        assert result.confidence.value == 0
        assert "timeout" in result.reason.lower()


class TestAIDecisionResultMethods:
    """AIDecisionResult 메서드 테스트"""

    def test_should_execute(self):
        """Given: 판단 결과 When: should_execute Then: 실행 여부"""
        # ALLOW + 높은 신뢰도 = 실행
        allow_high = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        assert allow_high.should_execute() is True

        # ALLOW + 낮은 신뢰도 = 실행 안함
        allow_low = AIDecisionResult.allow("KRW-BTC", 40, "Weak")
        assert allow_low.should_execute() is False

        # BLOCK = 실행 안함
        block = AIDecisionResult.block("KRW-BTC", 90, "Risk")
        assert block.should_execute() is False

        # HOLD = 실행 안함
        hold = AIDecisionResult.hold("KRW-BTC", "Wait")
        assert hold.should_execute() is False

    def test_is_confident(self):
        """Given: 판단 결과 When: is_confident Then: 신뢰도 충분 여부"""
        high = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        assert high.is_confident() is True

        low = AIDecisionResult.allow("KRW-BTC", 40, "Weak")
        assert low.is_confident() is False

    def test_to_dict(self):
        """Given: 판단 결과 When: to_dict Then: 딕셔너리 변환"""
        result = AIDecisionResult.allow("KRW-BTC", 85, "Strong signal")
        d = result.to_dict()

        assert d["decision"] == "allow"
        assert d["confidence"] == 85
        assert d["reason"] == "Strong signal"
        assert d["ticker"] == "KRW-BTC"
        assert d["should_execute"] is True

    def test_to_log_entry(self):
        """Given: 판단 결과 When: to_log_entry Then: 로그용 문자열"""
        result = AIDecisionResult.allow("KRW-BTC", 85, "Strong signal")
        log = result.to_log_entry()

        assert "KRW-BTC" in log
        assert "ALLOW" in log
        assert "85" in log


class TestAIDecisionResultWithMetadata:
    """메타데이터 포함 테스트"""

    def test_with_prompt_version(self):
        """Given: 프롬프트 버전 When: 포함 Then: 메타데이터 저장"""
        result = AIDecisionResult.allow(
            ticker="KRW-BTC",
            confidence=85,
            reason="Strong",
            prompt_version="v2.0.0",
        )

        assert result.prompt_version == "v2.0.0"

    def test_with_model_info(self):
        """Given: 모델 정보 When: 포함 Then: 메타데이터 저장"""
        result = AIDecisionResult.allow(
            ticker="KRW-BTC",
            confidence=85,
            reason="Strong",
            model="gpt-4-turbo",
            temperature=0.2,
        )

        assert result.model == "gpt-4-turbo"
        assert result.temperature == 0.2

    def test_with_token_usage(self):
        """Given: 토큰 사용량 When: 포함 Then: 메타데이터 저장"""
        result = AIDecisionResult.allow(
            ticker="KRW-BTC",
            confidence=85,
            reason="Strong",
            input_tokens=500,
            output_tokens=100,
        )

        assert result.input_tokens == 500
        assert result.output_tokens == 100
        assert result.total_tokens == 600

    def test_metadata_in_dict(self):
        """Given: 메타데이터 포함 결과 When: to_dict Then: 메타데이터 포함"""
        result = AIDecisionResult.allow(
            ticker="KRW-BTC",
            confidence=85,
            reason="Strong",
            prompt_version="v2.0.0",
            model="gpt-4-turbo",
        )

        d = result.to_dict()

        assert d["metadata"]["prompt_version"] == "v2.0.0"
        assert d["metadata"]["model"] == "gpt-4-turbo"


class TestAIDecisionResultEquality:
    """동등성 테스트"""

    def test_equal_results(self):
        """Given: 동일한 값 When: 비교 Then: 핵심 필드 동등"""
        r1 = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        r2 = AIDecisionResult.allow("KRW-BTC", 85, "Strong")

        # created_at 제외 비교 (dataclass frozen이라 시간이 다를 수 있음)
        assert r1.decision == r2.decision
        assert r1.confidence == r2.confidence
        assert r1.ticker == r2.ticker
        assert r1.reason == r2.reason

    def test_unequal_results(self):
        """Given: 다른 값 When: 비교 Then: 비동등"""
        r1 = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        r2 = AIDecisionResult.block("KRW-BTC", 90, "Risk")

        assert r1.decision != r2.decision
