"""
AnalyzeBreakoutUseCase - 돌파 분석 유스케이스

클린 아키텍처 기반의 AI 돌파 분석 비즈니스 로직.
PromptPort, ValidationPort, DecisionRecordPort를 조합하여
완전한 분석 워크플로우를 수행합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Protocol

from src.application.ports.outbound.prompt_port import PromptPort
from src.application.ports.outbound.validation_port import ValidationPort
from src.application.ports.outbound.decision_record_port import DecisionRecordPort
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType
from src.domain.value_objects.prompt_version import PromptVersion, PromptType
from src.domain.value_objects.market_summary import MarketSummary


class AIClient(Protocol):
    """AI 클라이언트 프로토콜"""

    async def analyze(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """AI 분석 호출"""
        ...


@dataclass(frozen=True)
class BreakoutAnalysisRequest:
    """
    돌파 분석 요청.

    Attributes:
        ticker: 거래 심볼
        current_price: 현재 가격
        market_summary: 시장 요약 정보
        additional_context: 추가 컨텍스트 (지표 등)
    """

    ticker: str
    current_price: Decimal
    market_summary: MarketSummary
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class BreakoutAnalysisResult:
    """
    돌파 분석 결과.

    Attributes:
        decision: AI 판단 결과
        record_id: 기록 ID (추적용)
        prompt_version: 사용된 프롬프트 버전
        validation_passed: 검증 통과 여부
        is_override: 원래 판단이 override 되었는지
        created_at: 생성 시각
    """

    decision: AIDecisionResult
    record_id: Optional[str] = None
    prompt_version: Optional[PromptVersion] = None
    validation_passed: bool = True
    is_override: bool = False
    created_at: datetime = field(default_factory=datetime.now)


class AnalyzeBreakoutUseCase:
    """
    돌파 분석 유스케이스.

    워크플로우:
    1. PromptPort로 프롬프트 생성
    2. AI 클라이언트로 분석 요청
    3. ValidationPort로 응답 검증
    4. ValidationPort로 결정 검증 (시장 컨텍스트 기반)
    5. DecisionRecordPort로 결정 기록
    6. 최종 결과 반환
    """

    def __init__(
        self,
        prompt_port: PromptPort,
        validation_port: ValidationPort,
        decision_record_port: DecisionRecordPort,
        ai_client: AIClient,
    ):
        """
        Initialize use case.

        Args:
            prompt_port: 프롬프트 생성/관리
            validation_port: 응답 검증
            decision_record_port: 결정 기록
            ai_client: AI 서비스 클라이언트
        """
        self._prompt_port = prompt_port
        self._validation_port = validation_port
        self._decision_record_port = decision_record_port
        self._ai_client = ai_client

    async def execute(
        self,
        request: BreakoutAnalysisRequest,
    ) -> BreakoutAnalysisResult:
        """
        돌파 분석 실행.

        Args:
            request: 분석 요청

        Returns:
            BreakoutAnalysisResult with decision and metadata
        """
        # Get prompt and version
        prompt_version = await self._prompt_port.get_current_version(PromptType.ENTRY)
        prompt = await self._prompt_port.render_prompt(
            prompt_type=PromptType.ENTRY,
            context={
                "ticker": request.ticker,
                "current_price": str(request.current_price),
                "market_regime": request.market_summary.regime.value,
                "atr_percent": str(request.market_summary.atr_percent),
                **(request.additional_context or {}),
            },
        )

        try:
            # Call AI
            raw_response = await self._ai_client.analyze(prompt)

            # Validate response format
            validation_result = await self._validation_port.validate_response(raw_response)

            if not validation_result.valid:
                # Invalid response - return HOLD
                decision = AIDecisionResult.hold(
                    ticker=request.ticker,
                    reason=f"Response validation failed: {validation_result.message}",
                )
                record_id = await self._record_decision(decision, prompt_version)

                return BreakoutAnalysisResult(
                    decision=decision,
                    record_id=record_id,
                    prompt_version=prompt_version,
                    validation_passed=False,
                )

            # Parse AI decision
            decision = AIDecisionResult.from_ai_response(
                response=raw_response,
                ticker=request.ticker,
                prompt_version=prompt_version.version,
            )

            # Validate decision against market context
            market_context = self._build_market_context(request)
            decision_validation = await self._validation_port.validate_decision(
                decision,
                market_context,
            )

            is_override = False
            if not decision_validation.valid and decision_validation.override_decision:
                # Apply override
                is_override = True
                original_reason = decision.reason
                decision = self._apply_override(
                    decision,
                    decision_validation.override_decision,
                    decision_validation.message,
                    original_reason,
                )

            # Record decision
            record_id = await self._record_decision(decision, prompt_version)

            return BreakoutAnalysisResult(
                decision=decision,
                record_id=record_id,
                prompt_version=prompt_version,
                validation_passed=decision_validation.valid,
                is_override=is_override,
            )

        except Exception as e:
            # Error - return safe HOLD
            decision = AIDecisionResult.fallback(
                ticker=request.ticker,
                error=str(e),
            )
            record_id = await self._record_decision(decision, prompt_version)

            return BreakoutAnalysisResult(
                decision=decision,
                record_id=record_id,
                prompt_version=prompt_version,
                validation_passed=False,
            )

    async def _record_decision(
        self,
        decision: AIDecisionResult,
        prompt_version: PromptVersion,
    ) -> str:
        """Record decision and return ID."""
        return await self._decision_record_port.record(
            decision=decision,
            prompt_version=prompt_version,
            params={
                "model": decision.model,
                "temperature": decision.temperature,
            },
        )

    def _build_market_context(
        self,
        request: BreakoutAnalysisRequest,
    ) -> Dict[str, Any]:
        """Build market context for validation."""
        context = {
            "regime": request.market_summary.regime.value,
            "atr_percent": float(request.market_summary.atr_percent),
            "breakout_strength": request.market_summary.breakout_strength.value,
        }

        # Add indicators from additional context
        if request.additional_context:
            if "rsi" in request.additional_context:
                context["rsi"] = request.additional_context["rsi"]
            if "macd_histogram" in request.additional_context:
                context["macd_histogram"] = request.additional_context["macd_histogram"]

        return context

    def _apply_override(
        self,
        original: AIDecisionResult,
        override_type: DecisionType,
        override_reason: str,
        original_reason: str,
    ) -> AIDecisionResult:
        """Apply decision override."""
        if override_type == DecisionType.HOLD:
            return AIDecisionResult.hold(
                ticker=original.ticker,
                reason=f"Override: {override_reason}. Original: {original_reason}",
                confidence=30,  # Low confidence for override
            )
        elif override_type == DecisionType.BLOCK:
            return AIDecisionResult.block(
                ticker=original.ticker,
                confidence=30,
                reason=f"Override: {override_reason}. Original: {original_reason}",
            )
        else:
            return original
