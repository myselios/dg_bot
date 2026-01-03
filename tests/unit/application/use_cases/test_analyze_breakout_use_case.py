"""
AnalyzeBreakoutUseCase Tests

TDD - 돌파 분석 유스케이스 테스트
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.use_cases.analyze_breakout import (
    AnalyzeBreakoutUseCase,
    BreakoutAnalysisRequest,
    BreakoutAnalysisResult,
)
from src.application.ports.outbound.prompt_port import PromptPort
from src.application.ports.outbound.validation_port import ValidationPort, ValidationResult
from src.application.ports.outbound.decision_record_port import DecisionRecordPort
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType
from src.domain.value_objects.prompt_version import PromptVersion, PromptType
from src.domain.value_objects.market_summary import MarketSummary, MarketRegime, BreakoutStrength


class TestAnalyzeBreakoutUseCaseCreation:
    """UseCase 생성 테스트"""

    def test_create_with_ports(self):
        """Given: 필수 Ports When: 생성 Then: 성공"""
        use_case = AnalyzeBreakoutUseCase(
            prompt_port=AsyncMock(spec=PromptPort),
            validation_port=AsyncMock(spec=ValidationPort),
            decision_record_port=AsyncMock(spec=DecisionRecordPort),
            ai_client=AsyncMock(),
        )

        assert use_case is not None


class TestAnalyzeBreakoutUseCaseExecute:
    """execute 메서드 테스트"""

    @pytest.fixture
    def mock_prompt_port(self):
        port = AsyncMock(spec=PromptPort)
        port.get_prompt.return_value = "Test prompt"
        port.get_current_version.return_value = PromptVersion.current(PromptType.ENTRY)
        port.render_prompt.return_value = "Rendered prompt"
        return port

    @pytest.fixture
    def mock_validation_port(self):
        port = AsyncMock(spec=ValidationPort)
        port.validate_response.return_value = ValidationResult(valid=True, message="OK")
        port.validate_decision.return_value = ValidationResult(valid=True, message="OK")
        return port

    @pytest.fixture
    def mock_decision_record_port(self):
        port = AsyncMock(spec=DecisionRecordPort)
        port.record.return_value = "record-123"
        return port

    @pytest.fixture
    def mock_ai_client(self):
        client = AsyncMock()
        client.analyze.return_value = {
            "decision": "allow",
            "confidence": 85,
            "reason": "Strong momentum",
        }
        return client

    @pytest.fixture
    def use_case(
        self,
        mock_prompt_port,
        mock_validation_port,
        mock_decision_record_port,
        mock_ai_client,
    ):
        return AnalyzeBreakoutUseCase(
            prompt_port=mock_prompt_port,
            validation_port=mock_validation_port,
            decision_record_port=mock_decision_record_port,
            ai_client=mock_ai_client,
        )

    @pytest.fixture
    def sample_request(self):
        return BreakoutAnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
            market_summary=MarketSummary(
                ticker="KRW-BTC",
                regime=MarketRegime.TRENDING_UP,
                atr_percent=Decimal("2.5"),
                breakout_strength=BreakoutStrength.MODERATE,
                risk_budget=Decimal("0.02"),
            ),
        )

    @pytest.mark.asyncio
    async def test_execute_returns_result(self, use_case, sample_request):
        """Given: 유효한 요청 When: execute Then: 결과 반환"""
        result = await use_case.execute(sample_request)

        assert isinstance(result, BreakoutAnalysisResult)
        assert result.decision is not None

    @pytest.mark.asyncio
    async def test_execute_uses_prompt_port(
        self, use_case, sample_request, mock_prompt_port
    ):
        """Given: 요청 When: execute Then: PromptPort 사용"""
        await use_case.execute(sample_request)

        mock_prompt_port.render_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_validates_response(
        self, use_case, sample_request, mock_validation_port
    ):
        """Given: AI 응답 When: execute Then: ValidationPort 사용"""
        await use_case.execute(sample_request)

        mock_validation_port.validate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_records_decision(
        self, use_case, sample_request, mock_decision_record_port
    ):
        """Given: 유효한 판단 When: execute Then: 기록 저장"""
        result = await use_case.execute(sample_request)

        mock_decision_record_port.record.assert_called_once()
        assert result.record_id == "record-123"

    @pytest.mark.asyncio
    async def test_execute_returns_allow(
        self, use_case, sample_request, mock_ai_client
    ):
        """Given: AI가 ALLOW 반환 When: execute Then: ALLOW 결과"""
        mock_ai_client.analyze.return_value = {
            "decision": "allow",
            "confidence": 90,
            "reason": "Perfect setup",
        }

        result = await use_case.execute(sample_request)

        assert result.decision.decision == DecisionType.ALLOW

    @pytest.mark.asyncio
    async def test_execute_returns_hold_on_validation_failure(
        self, use_case, sample_request, mock_validation_port
    ):
        """Given: 검증 실패 When: execute Then: HOLD 반환"""
        mock_validation_port.validate_response.return_value = ValidationResult(
            valid=False,
            message="Invalid response",
        )

        result = await use_case.execute(sample_request)

        assert result.decision.decision == DecisionType.HOLD

    @pytest.mark.asyncio
    async def test_execute_returns_hold_on_decision_override(
        self, use_case, sample_request, mock_validation_port
    ):
        """Given: 결정 override When: execute Then: override 적용"""
        mock_validation_port.validate_decision.return_value = ValidationResult(
            valid=False,
            message="Overbought",
            override_decision=DecisionType.HOLD,
        )

        result = await use_case.execute(sample_request)

        assert result.decision.decision == DecisionType.HOLD


class TestAnalyzeBreakoutUseCaseErrorHandling:
    """에러 처리 테스트"""

    @pytest.fixture
    def use_case(self):
        return AnalyzeBreakoutUseCase(
            prompt_port=AsyncMock(spec=PromptPort),
            validation_port=AsyncMock(spec=ValidationPort),
            decision_record_port=AsyncMock(spec=DecisionRecordPort),
            ai_client=AsyncMock(),
        )

    @pytest.fixture
    def sample_request(self):
        return BreakoutAnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
            market_summary=MarketSummary(
                ticker="KRW-BTC",
                regime=MarketRegime.TRENDING_UP,
                atr_percent=Decimal("2.5"),
                breakout_strength=BreakoutStrength.MODERATE,
                risk_budget=Decimal("0.02"),
            ),
        )

    @pytest.mark.asyncio
    async def test_returns_hold_on_ai_error(self, use_case, sample_request):
        """Given: AI 에러 When: execute Then: HOLD fallback"""
        use_case._ai_client.analyze.side_effect = Exception("API Error")
        use_case._prompt_port.render_prompt.return_value = "Prompt"
        use_case._prompt_port.get_current_version.return_value = PromptVersion.current(PromptType.ENTRY)

        result = await use_case.execute(sample_request)

        assert result.decision.decision == DecisionType.HOLD
        assert "error" in result.decision.reason.lower()

    @pytest.mark.asyncio
    async def test_records_fallback_decision(self, use_case, sample_request):
        """Given: 에러 발생 When: execute Then: fallback도 기록"""
        use_case._ai_client.analyze.side_effect = Exception("API Error")
        use_case._prompt_port.render_prompt.return_value = "Prompt"
        use_case._prompt_port.get_current_version.return_value = PromptVersion.current(PromptType.ENTRY)
        use_case._decision_record_port.record.return_value = "fallback-record"

        result = await use_case.execute(sample_request)

        use_case._decision_record_port.record.assert_called_once()
