"""
MarketSummary Value Object

시장 상태를 요약하여 AI 프롬프트에 전달할 표준화된 데이터 구조.
raw OHLC 대신 요약값만 제공하여 토큰 비용 절감 및 일관성 확보.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Union


class MarketRegime(Enum):
    """시장 상태 (체제)"""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class BreakoutStrength(Enum):
    """돌파 강도"""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"

    @property
    def score(self) -> int:
        """돌파 강도를 수치화"""
        scores = {
            BreakoutStrength.STRONG: 3,
            BreakoutStrength.MODERATE: 2,
            BreakoutStrength.WEAK: 1,
            BreakoutStrength.NONE: 0,
        }
        return scores[self]


@dataclass(frozen=True)
class MarketSummary:
    """
    시장 상태 요약 Value Object.

    AI 프롬프트에 전달할 표준화된 시장 정보.
    raw 데이터 대신 계산된 요약값만 포함.

    Attributes:
        ticker: 거래 심볼 (예: "KRW-BTC")
        regime: 시장 상태 (상승/하락/횡보/변동)
        atr_percent: ATR 백분율 (변동성 지표)
        breakout_strength: 돌파 강도
        risk_budget: 리스크 예산 (0.0 ~ 1.0)
        volume_ratio: 거래량 비율 (현재/평균)
        rsi: RSI 값 (0-100)
        btc_dominance: BTC 도미넌스 (시장 지표)
    """

    ticker: str
    regime: MarketRegime
    atr_percent: Decimal
    breakout_strength: BreakoutStrength
    risk_budget: Decimal
    volume_ratio: Optional[Decimal] = None
    rsi: Optional[Decimal] = None
    btc_dominance: Optional[Decimal] = None

    def __post_init__(self) -> None:
        """Decimal 변환 및 검증"""
        # atr_percent
        if not isinstance(self.atr_percent, Decimal):
            object.__setattr__(self, "atr_percent", Decimal(str(self.atr_percent)))

        # risk_budget
        if not isinstance(self.risk_budget, Decimal):
            object.__setattr__(self, "risk_budget", Decimal(str(self.risk_budget)))

        # volume_ratio
        if self.volume_ratio is not None and not isinstance(self.volume_ratio, Decimal):
            object.__setattr__(self, "volume_ratio", Decimal(str(self.volume_ratio)))

        # rsi
        if self.rsi is not None and not isinstance(self.rsi, Decimal):
            object.__setattr__(self, "rsi", Decimal(str(self.rsi)))

        # btc_dominance
        if self.btc_dominance is not None and not isinstance(self.btc_dominance, Decimal):
            object.__setattr__(self, "btc_dominance", Decimal(str(self.btc_dominance)))

    # --- Factory Methods ---

    @classmethod
    def from_indicators(
        cls,
        ticker: str,
        indicators: Dict[str, Any],
        risk_budget: Optional[Decimal] = None,
    ) -> MarketSummary:
        """
        기술 지표 딕셔너리로부터 MarketSummary 생성.

        Args:
            ticker: 거래 심볼
            indicators: 기술 지표 딕셔너리
            risk_budget: 리스크 예산 (기본값: 0.02)

        Returns:
            MarketSummary 인스턴스
        """
        # ATR 백분율 계산
        atr = indicators.get("atr", 0)
        current_price = indicators.get("current_price", 1)
        atr_percent = Decimal(str(atr)) / Decimal(str(current_price)) * 100 if current_price else Decimal("0")

        # 시장 상태 감지
        regime = cls._detect_regime(indicators)

        # 돌파 강도 감지
        breakout_strength = cls._detect_breakout_strength(indicators)

        return cls(
            ticker=ticker,
            regime=regime,
            atr_percent=atr_percent.quantize(Decimal("0.1")),
            breakout_strength=breakout_strength,
            risk_budget=risk_budget or Decimal("0.02"),
            volume_ratio=Decimal(str(indicators.get("volume_ratio", 1))) if indicators.get("volume_ratio") else None,
            rsi=Decimal(str(indicators.get("rsi", 50))) if indicators.get("rsi") else None,
        )

    @staticmethod
    def _detect_regime(indicators: Dict[str, Any]) -> MarketRegime:
        """지표 기반 시장 상태 감지"""
        adx = indicators.get("adx", 0)
        macd_histogram = indicators.get("macd_histogram", 0)
        rsi = indicators.get("rsi", 50)
        atr = indicators.get("atr", 0)
        current_price = indicators.get("current_price", 1)

        # ATR% 계산 (변동성)
        atr_percent = (atr / current_price * 100) if current_price else 0

        # 고변동성 (ATR > 4%)
        if atr_percent > 4:
            return MarketRegime.VOLATILE

        # 추세 존재 (ADX > 25)
        if adx > 25:
            if macd_histogram > 0 or rsi > 55:
                return MarketRegime.TRENDING_UP
            elif macd_histogram < 0 or rsi < 45:
                return MarketRegime.TRENDING_DOWN

        # 횡보 (ADX < 20)
        if adx < 20:
            return MarketRegime.RANGING

        return MarketRegime.UNKNOWN

    @staticmethod
    def _detect_breakout_strength(indicators: Dict[str, Any]) -> BreakoutStrength:
        """돌파 강도 감지"""
        volume_ratio = indicators.get("volume_ratio", 1)
        adx = indicators.get("adx", 0)
        bb_position = indicators.get("bb_position", 0.5)

        # 강한 돌파: 거래량 1.5x 이상, ADX > 25, BB 상단 돌파
        if volume_ratio > 1.5 and adx > 25 and bb_position > 0.8:
            return BreakoutStrength.STRONG

        # 보통 돌파: 거래량 1.2x 이상, ADX > 20
        if volume_ratio > 1.2 and adx > 20:
            return BreakoutStrength.MODERATE

        # 약한 돌파: 거래량 1.0x 이상
        if volume_ratio > 1.0:
            return BreakoutStrength.WEAK

        return BreakoutStrength.NONE

    # --- Query Methods ---

    def is_high_volatility(self, threshold: Decimal = Decimal("3.0")) -> bool:
        """
        고변동성 여부 판단.

        Args:
            threshold: ATR% 임계값 (기본: 3.0%)

        Returns:
            True if ATR% > threshold
        """
        return self.atr_percent > threshold

    def is_favorable_for_entry(self) -> bool:
        """
        진입에 유리한 상태인지 판단.

        조건:
        - 상승 추세 또는 횡보
        - 강한/보통 돌파 강도
        - RSI 30-70 범위 (과매수/과매도 아님)
        """
        # 상승 추세 또는 횡보
        if self.regime not in (MarketRegime.TRENDING_UP, MarketRegime.RANGING):
            return False

        # 돌파 강도
        if self.breakout_strength in (BreakoutStrength.NONE, BreakoutStrength.WEAK):
            return False

        # RSI 체크
        if self.rsi is not None:
            if self.rsi < 30 or self.rsi > 70:
                return False

        return True

    def suggested_position_size(self) -> Decimal:
        """
        리스크 기반 포지션 크기 제안.

        계산: risk_budget / (atr_percent / 100)
        최대 1.0 (100%)
        """
        if self.atr_percent == Decimal("0"):
            return Decimal("0")

        atr_decimal = self.atr_percent / Decimal("100")
        position_size = self.risk_budget / atr_decimal

        # 최대 100%
        return min(position_size, Decimal("1.0"))

    # --- Conversion Methods ---

    def to_prompt_context(self) -> Dict[str, Any]:
        """
        AI 프롬프트용 컨텍스트 딕셔너리 생성.

        모든 값을 문자열/숫자로 변환하여 JSON 직렬화 가능하게 함.
        """
        return {
            "ticker": self.ticker,
            "regime": self.regime.value,
            "atr_percent": f"{self.atr_percent}%",
            "breakout_strength": self.breakout_strength.value,
            "risk_budget": f"{float(self.risk_budget * 100):.1f}%",
            "rsi": int(self.rsi) if self.rsi is not None else None,
            "volume_ratio": float(self.volume_ratio) if self.volume_ratio is not None else None,
            "btc_dominance": float(self.btc_dominance) if self.btc_dominance is not None else None,
            "is_high_volatility": self.is_high_volatility(),
            "is_favorable_for_entry": self.is_favorable_for_entry(),
            "suggested_position_size": float(self.suggested_position_size()),
        }

    def __str__(self) -> str:
        """문자열 표현"""
        return (
            f"MarketSummary({self.ticker}: {self.regime.value}, "
            f"ATR={self.atr_percent}%, {self.breakout_strength.value})"
        )

    def __repr__(self) -> str:
        """상세 표현"""
        return (
            f"MarketSummary(ticker={self.ticker!r}, regime={self.regime}, "
            f"atr_percent={self.atr_percent}, breakout_strength={self.breakout_strength}, "
            f"risk_budget={self.risk_budget})"
        )
