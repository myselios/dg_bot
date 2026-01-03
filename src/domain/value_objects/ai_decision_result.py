"""
AIDecisionResult Value Object

AI 판단 결과를 ALLOW/BLOCK/HOLD로 단순화.
"AI는 변동성돌파의 엔진이 아니라 브레이크여야 한다"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class DecisionType(Enum):
    """
    AI 판단 유형.

    - ALLOW: 돌파 진입 허용 (브레이크 해제)
    - BLOCK: 돌파 진입 차단 (브레이크 작동)
    - HOLD: 판단 보류 (불확실, 에러 등)
    """

    ALLOW = "allow"
    BLOCK = "block"
    HOLD = "hold"

    @property
    def is_actionable(self) -> bool:
        """실행 가능한 판단인지 (ALLOW만 True)"""
        return self == DecisionType.ALLOW


@dataclass(frozen=True)
class DecisionConfidence:
    """
    판단 신뢰도 (0-100).

    AI의 확신 정도를 수치화.
    """

    value: int

    def __post_init__(self) -> None:
        """검증"""
        if not 0 <= self.value <= 100:
            raise ValueError(f"Confidence must be 0-100, got {self.value}")

    @property
    def level(self) -> str:
        """신뢰도 수준"""
        if self.value >= 80:
            return "very_high"
        elif self.value >= 60:
            return "high"
        elif self.value >= 40:
            return "medium"
        elif self.value >= 20:
            return "low"
        else:
            return "very_low"

    def is_sufficient(self, threshold: int = 60) -> bool:
        """충분한 신뢰도인지"""
        return self.value >= threshold


@dataclass(frozen=True)
class AIDecisionResult:
    """
    AI 판단 결과 Value Object.

    AI의 돌파 허용/차단 판단과 메타데이터를 담는 불변 객체.

    Attributes:
        decision: 판단 유형 (ALLOW/BLOCK/HOLD)
        confidence: 신뢰도 (0-100)
        reason: 판단 근거
        ticker: 거래 심볼
        prompt_version: 사용된 프롬프트 버전
        model: AI 모델명
        temperature: 모델 temperature
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        created_at: 생성 시각
    """

    decision: DecisionType
    confidence: DecisionConfidence
    reason: str
    ticker: str
    prompt_version: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    # --- Factory Methods ---

    @classmethod
    def allow(
        cls,
        ticker: str,
        confidence: int,
        reason: str,
        **metadata,
    ) -> AIDecisionResult:
        """ALLOW 결과 생성"""
        return cls(
            decision=DecisionType.ALLOW,
            confidence=DecisionConfidence(confidence),
            reason=reason,
            ticker=ticker,
            **metadata,
        )

    @classmethod
    def block(
        cls,
        ticker: str,
        confidence: int,
        reason: str,
        **metadata,
    ) -> AIDecisionResult:
        """BLOCK 결과 생성"""
        return cls(
            decision=DecisionType.BLOCK,
            confidence=DecisionConfidence(confidence),
            reason=reason,
            ticker=ticker,
            **metadata,
        )

    @classmethod
    def hold(
        cls,
        ticker: str,
        reason: str,
        confidence: int = 50,
        **metadata,
    ) -> AIDecisionResult:
        """HOLD 결과 생성 (기본 신뢰도 50)"""
        return cls(
            decision=DecisionType.HOLD,
            confidence=DecisionConfidence(confidence),
            reason=reason,
            ticker=ticker,
            **metadata,
        )

    @classmethod
    def fallback(
        cls,
        ticker: str,
        error: str,
    ) -> AIDecisionResult:
        """에러 시 안전한 HOLD 결과 생성"""
        return cls(
            decision=DecisionType.HOLD,
            confidence=DecisionConfidence(0),
            reason=f"Fallback due to error: {error}",
            ticker=ticker,
        )

    @classmethod
    def from_ai_response(
        cls,
        response: Dict[str, Any],
        ticker: str,
        **metadata,
    ) -> AIDecisionResult:
        """
        AI JSON 응답으로부터 결과 생성.

        잘못된 값은 HOLD로 처리 (안전 fallback).
        """
        decision_str = response.get("decision", "hold").lower()

        # 판단 유형 매핑
        decision_map = {
            "allow": DecisionType.ALLOW,
            "block": DecisionType.BLOCK,
            "hold": DecisionType.HOLD,
            # 호환성을 위한 별칭
            "buy": DecisionType.ALLOW,
            "sell": DecisionType.BLOCK,
            "wait": DecisionType.HOLD,
        }

        decision = decision_map.get(decision_str, DecisionType.HOLD)

        # 신뢰도 (범위 체크)
        raw_confidence = response.get("confidence", 50)
        confidence = max(0, min(100, int(raw_confidence)))

        reason = response.get("reason", "No reason provided")

        return cls(
            decision=decision,
            confidence=DecisionConfidence(confidence),
            reason=reason,
            ticker=ticker,
            **metadata,
        )

    # --- Query Methods ---

    def should_execute(self, confidence_threshold: int = 60) -> bool:
        """
        실행해야 하는지 판단.

        조건:
        - ALLOW 판단
        - 신뢰도가 임계값 이상
        """
        return (
            self.decision == DecisionType.ALLOW
            and self.confidence.is_sufficient(confidence_threshold)
        )

    def is_confident(self, threshold: int = 60) -> bool:
        """신뢰도가 충분한지"""
        return self.confidence.is_sufficient(threshold)

    @property
    def total_tokens(self) -> int:
        """총 토큰 사용량"""
        input_t = self.input_tokens or 0
        output_t = self.output_tokens or 0
        return input_t + output_t

    # --- Conversion Methods ---

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        result = {
            "decision": self.decision.value,
            "confidence": self.confidence.value,
            "reason": self.reason,
            "ticker": self.ticker,
            "should_execute": self.should_execute(),
            "created_at": self.created_at.isoformat(),
        }

        # 메타데이터
        metadata = {}
        if self.prompt_version:
            metadata["prompt_version"] = self.prompt_version
        if self.model:
            metadata["model"] = self.model
        if self.temperature is not None:
            metadata["temperature"] = self.temperature
        if self.input_tokens is not None:
            metadata["input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            metadata["output_tokens"] = self.output_tokens
        if self.total_tokens > 0:
            metadata["total_tokens"] = self.total_tokens

        if metadata:
            result["metadata"] = metadata

        return result

    def to_log_entry(self) -> str:
        """로그용 문자열"""
        return (
            f"[{self.ticker}] {self.decision.name} "
            f"(confidence={self.confidence.value}%): {self.reason}"
        )

    def __str__(self) -> str:
        """문자열 표현"""
        return (
            f"AIDecisionResult({self.ticker}: {self.decision.name}, "
            f"{self.confidence.value}%)"
        )

    def __repr__(self) -> str:
        """상세 표현"""
        return (
            f"AIDecisionResult(decision={self.decision}, "
            f"confidence={self.confidence.value}, "
            f"ticker={self.ticker!r}, reason={self.reason!r})"
        )
