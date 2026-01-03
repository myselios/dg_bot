"""
BreakoutFilter Domain Service

규칙 기반 돌파 필터링 (AI 없이).
"AI는 변동성돌파의 엔진이 아니라 브레이크여야 한다"
→ 기본 필터링은 규칙 기반, AI는 최종 확인만.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Tuple

from src.domain.value_objects.market_summary import (
    MarketSummary,
    MarketRegime,
    BreakoutStrength,
)


class FilterReason(Enum):
    """필터 차단 이유"""

    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLUME = "low_volume"
    WEAK_BREAKOUT = "weak_breakout"
    UNFAVORABLE_REGIME = "unfavorable_regime"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class FilterResult:
    """
    필터 적용 결과.

    Attributes:
        passed: 통과 여부
        reason: 결과 설명
        filter_reason: 차단 이유 (실패 시)
        score: 점수 (0-100)
    """

    passed: bool
    reason: str
    filter_reason: Optional[FilterReason] = None
    score: int = 0

    @classmethod
    def create_passed(cls, reason: str, score: int = 100) -> FilterResult:
        """통과 결과 생성"""
        return cls(passed=True, reason=reason, score=score)

    @classmethod
    def failed(cls, filter_reason: FilterReason, reason: str) -> FilterResult:
        """실패 결과 생성"""
        return cls(
            passed=False,
            reason=reason,
            filter_reason=filter_reason,
            score=0,
        )


@dataclass
class BreakoutFilter:
    """
    규칙 기반 돌파 필터.

    AI 호출 전에 규칙 기반으로 명확한 불량 케이스를 걸러냄.
    비용 절감 및 일관성 확보 목적.

    Attributes:
        rsi_overbought: RSI 과매수 임계값
        rsi_oversold: RSI 과매도 임계값
        max_atr_percent: 최대 ATR% (이 이상은 고변동성)
        min_volume_ratio: 최소 거래량 비율
        min_breakout_strength: 최소 돌파 강도
    """

    rsi_overbought: int = 70
    rsi_oversold: int = 30
    max_atr_percent: Decimal = Decimal("5.0")
    min_volume_ratio: Decimal = Decimal("0.8")
    min_breakout_strength: BreakoutStrength = BreakoutStrength.WEAK

    # 허용되는 시장 상태
    favorable_regimes: Tuple[MarketRegime, ...] = (
        MarketRegime.TRENDING_UP,
        MarketRegime.RANGING,
    )

    def apply(self, summary: MarketSummary) -> FilterResult:
        """
        필터 적용.

        순서대로 체크하고 첫 번째 실패 시 즉시 반환.
        """
        # 1. RSI 과매수 체크
        if summary.rsi is not None and summary.rsi > self.rsi_overbought:
            return FilterResult.failed(
                FilterReason.RSI_OVERBOUGHT,
                f"RSI {summary.rsi} exceeds overbought threshold {self.rsi_overbought}",
            )

        # 2. RSI 과매도 체크
        if summary.rsi is not None and summary.rsi < self.rsi_oversold:
            return FilterResult.failed(
                FilterReason.RSI_OVERSOLD,
                f"RSI {summary.rsi} below oversold threshold {self.rsi_oversold}",
            )

        # 3. 고변동성 체크
        if summary.atr_percent > self.max_atr_percent:
            return FilterResult.failed(
                FilterReason.HIGH_VOLATILITY,
                f"ATR% {summary.atr_percent} exceeds max {self.max_atr_percent}",
            )

        # 4. 시장 상태 체크
        if summary.regime not in self.favorable_regimes:
            return FilterResult.failed(
                FilterReason.UNFAVORABLE_REGIME,
                f"Market regime {summary.regime.value} is not favorable",
            )

        # 5. 돌파 강도 체크
        if summary.breakout_strength.score < self.min_breakout_strength.score:
            return FilterResult.failed(
                FilterReason.WEAK_BREAKOUT,
                f"Breakout strength {summary.breakout_strength.value} is too weak",
            )

        # 6. 거래량 체크
        if summary.volume_ratio is not None and summary.volume_ratio < self.min_volume_ratio:
            return FilterResult.failed(
                FilterReason.LOW_VOLUME,
                f"Volume ratio {summary.volume_ratio} below min {self.min_volume_ratio}",
            )

        # 모든 체크 통과
        score = self.calculate_score(summary)
        return FilterResult.create_passed("All filter conditions met", score)

    def calculate_score(self, summary: MarketSummary) -> int:
        """
        종합 점수 계산 (0-100).

        요소:
        - 시장 상태 (25점)
        - 돌파 강도 (25점)
        - RSI 위치 (25점)
        - 변동성/거래량 (25점)
        """
        score = 0

        # 시장 상태 (25점)
        regime_scores = {
            MarketRegime.TRENDING_UP: 25,
            MarketRegime.RANGING: 15,
            MarketRegime.VOLATILE: 5,
            MarketRegime.TRENDING_DOWN: 0,
            MarketRegime.UNKNOWN: 10,
        }
        score += regime_scores.get(summary.regime, 0)

        # 돌파 강도 (25점)
        strength_scores = {
            BreakoutStrength.STRONG: 25,
            BreakoutStrength.MODERATE: 18,
            BreakoutStrength.WEAK: 8,
            BreakoutStrength.NONE: 0,
        }
        score += strength_scores.get(summary.breakout_strength, 0)

        # RSI 위치 (25점) - 50에 가까울수록 좋음
        if summary.rsi is not None:
            rsi_diff = abs(summary.rsi - Decimal("50"))
            if rsi_diff <= 10:
                score += 25
            elif rsi_diff <= 20:
                score += 18
            elif rsi_diff <= 30:
                score += 10
            else:
                score += 0
        else:
            score += 12  # 데이터 없으면 중간값

        # 변동성/거래량 (25점)
        vol_score = 0

        # ATR 낮을수록 좋음 (최대 12점)
        if summary.atr_percent <= Decimal("2.0"):
            vol_score += 12
        elif summary.atr_percent <= Decimal("3.0"):
            vol_score += 8
        elif summary.atr_percent <= Decimal("4.0"):
            vol_score += 4
        else:
            vol_score += 0

        # 거래량 높을수록 좋음 (최대 13점)
        if summary.volume_ratio is not None:
            if summary.volume_ratio >= Decimal("2.0"):
                vol_score += 13
            elif summary.volume_ratio >= Decimal("1.5"):
                vol_score += 10
            elif summary.volume_ratio >= Decimal("1.0"):
                vol_score += 6
            else:
                vol_score += 0
        else:
            vol_score += 6  # 데이터 없으면 중간값

        score += vol_score

        return min(100, max(0, score))

    def filter_batch(
        self,
        summaries: List[MarketSummary],
        limit: Optional[int] = None,
    ) -> List[MarketSummary]:
        """
        배치 필터링.

        통과한 요약만 반환. 점수순 정렬.
        """
        passed = []
        for summary in summaries:
            result = self.apply(summary)
            if result.passed:
                passed.append((summary, result.score))

        # 점수순 정렬 (높은 순)
        passed.sort(key=lambda x: x[1], reverse=True)

        # 제한 적용
        if limit is not None:
            passed = passed[:limit]

        return [s for s, _ in passed]

    def rank_by_score(
        self,
        summaries: List[MarketSummary],
    ) -> List[Tuple[MarketSummary, int]]:
        """
        점수순 랭킹.

        모든 요약에 대해 점수 계산 후 정렬.
        """
        ranked = [(s, self.calculate_score(s)) for s in summaries]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
