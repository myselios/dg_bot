"""
MarketSummary Value Object Tests

TDD - Red: 테스트 먼저 작성
"""
import pytest
from decimal import Decimal

from src.domain.value_objects.market_summary import (
    MarketSummary,
    MarketRegime,
    BreakoutStrength,
)


class TestMarketRegime:
    """시장 상태 열거형 테스트"""

    def test_regime_values(self):
        """Given: 시장 상태 열거형 When: 값 확인 Then: 정의된 상태 반환"""
        assert MarketRegime.TRENDING_UP.value == "trending_up"
        assert MarketRegime.TRENDING_DOWN.value == "trending_down"
        assert MarketRegime.RANGING.value == "ranging"
        assert MarketRegime.VOLATILE.value == "volatile"
        assert MarketRegime.UNKNOWN.value == "unknown"


class TestBreakoutStrength:
    """돌파 강도 열거형 테스트"""

    def test_strength_values(self):
        """Given: 돌파 강도 열거형 When: 값 확인 Then: 정의된 강도 반환"""
        assert BreakoutStrength.STRONG.value == "strong"
        assert BreakoutStrength.MODERATE.value == "moderate"
        assert BreakoutStrength.WEAK.value == "weak"
        assert BreakoutStrength.NONE.value == "none"

    def test_strength_score(self):
        """Given: 돌파 강도 When: 점수 확인 Then: 수치화된 점수 반환"""
        assert BreakoutStrength.STRONG.score == 3
        assert BreakoutStrength.MODERATE.score == 2
        assert BreakoutStrength.WEAK.score == 1
        assert BreakoutStrength.NONE.score == 0


class TestMarketSummaryCreation:
    """MarketSummary 생성 테스트"""

    def test_create_with_all_fields(self):
        """Given: 모든 필드 제공 When: 생성 Then: 올바른 값 설정"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            volume_ratio=Decimal("1.5"),
            rsi=Decimal("55"),
            btc_dominance=Decimal("45.5"),
        )

        assert summary.ticker == "KRW-BTC"
        assert summary.regime == MarketRegime.TRENDING_UP
        assert summary.atr_percent == Decimal("2.5")
        assert summary.breakout_strength == BreakoutStrength.STRONG
        assert summary.risk_budget == Decimal("0.02")
        assert summary.volume_ratio == Decimal("1.5")
        assert summary.rsi == Decimal("55")
        assert summary.btc_dominance == Decimal("45.5")

    def test_create_with_float_conversion(self):
        """Given: float 값 제공 When: 생성 Then: Decimal로 변환"""
        summary = MarketSummary(
            ticker="KRW-ETH",
            regime=MarketRegime.RANGING,
            atr_percent=3.0,
            breakout_strength=BreakoutStrength.MODERATE,
            risk_budget=0.015,
        )

        assert isinstance(summary.atr_percent, Decimal)
        assert summary.atr_percent == Decimal("3.0")
        assert isinstance(summary.risk_budget, Decimal)

    def test_immutable(self):
        """Given: 생성된 객체 When: 수정 시도 Then: FrozenInstanceError 발생"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            summary.ticker = "KRW-ETH"


class TestMarketSummaryFactoryMethods:
    """MarketSummary 팩토리 메서드 테스트"""

    def test_from_indicators(self):
        """Given: 기술 지표 딕셔너리 When: from_indicators Then: 요약 생성"""
        indicators = {
            "atr": 1500000,
            "current_price": 60000000,
            "rsi": 55,
            "volume_ratio": 1.2,
            "adx": 25,
            "bb_position": 0.7,  # 볼린저 밴드 위치
        }

        summary = MarketSummary.from_indicators(
            ticker="KRW-BTC",
            indicators=indicators,
            risk_budget=Decimal("0.02"),
        )

        assert summary.ticker == "KRW-BTC"
        assert summary.atr_percent == Decimal("2.5")  # 1500000/60000000 * 100
        assert summary.rsi == Decimal("55")

    def test_from_indicators_with_regime_detection(self):
        """Given: ADX, RSI 등 지표 When: from_indicators Then: regime 자동 감지"""
        # 강한 상승 추세
        trending_up = {
            "atr": 1500000,
            "current_price": 60000000,
            "rsi": 65,
            "adx": 30,  # ADX > 25 = 추세 존재
            "macd_histogram": 100,  # 양수 = 상승
            "volume_ratio": 1.5,
        }
        summary = MarketSummary.from_indicators("KRW-BTC", trending_up)
        assert summary.regime == MarketRegime.TRENDING_UP

        # 횡보장
        ranging = {
            "atr": 500000,
            "current_price": 60000000,
            "rsi": 50,
            "adx": 15,  # ADX < 20 = 횡보
            "macd_histogram": 10,
            "volume_ratio": 0.8,
        }
        summary = MarketSummary.from_indicators("KRW-BTC", ranging)
        assert summary.regime == MarketRegime.RANGING


class TestMarketSummaryMethods:
    """MarketSummary 메서드 테스트"""

    def test_is_high_volatility(self):
        """Given: ATR% When: is_high_volatility Then: 변동성 판단"""
        high_vol = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.VOLATILE,
            atr_percent=Decimal("5.0"),  # 5% ATR
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
        )
        assert high_vol.is_high_volatility() is True

        low_vol = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.RANGING,
            atr_percent=Decimal("1.5"),  # 1.5% ATR
            breakout_strength=BreakoutStrength.WEAK,
            risk_budget=Decimal("0.02"),
        )
        assert low_vol.is_high_volatility() is False

    def test_is_favorable_for_entry(self):
        """Given: 시장 상태 When: is_favorable_for_entry Then: 진입 적합성 판단"""
        # 상승 추세 + 강한 돌파 = 진입 적합
        favorable = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            rsi=Decimal("55"),
        )
        assert favorable.is_favorable_for_entry() is True

        # 과매수 상태 = 진입 부적합
        overbought = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            rsi=Decimal("75"),  # 과매수
        )
        assert overbought.is_favorable_for_entry() is False

    def test_suggested_position_size(self):
        """Given: 리스크 예산과 ATR When: suggested_position_size Then: 포지션 크기 제안"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),  # 2% 리스크
        )

        # 리스크 예산 / ATR% = 포지션 크기
        # 0.02 / 0.025 = 0.8 (80% 포지션)
        position_size = summary.suggested_position_size()
        assert position_size == Decimal("0.8")

    def test_to_prompt_context(self):
        """Given: MarketSummary When: to_prompt_context Then: AI 프롬프트용 딕셔너리"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            rsi=Decimal("55"),
            volume_ratio=Decimal("1.5"),
        )

        context = summary.to_prompt_context()

        assert context["ticker"] == "KRW-BTC"
        assert context["regime"] == "trending_up"
        assert context["atr_percent"] == "2.5%"
        assert context["breakout_strength"] == "strong"
        assert context["risk_budget"] == "2.0%"
        assert context["rsi"] == 55
        assert context["volume_ratio"] == 1.5


class TestMarketSummaryEquality:
    """MarketSummary 동등성 테스트"""

    def test_equal_summaries(self):
        """Given: 동일한 값 When: 비교 Then: 동등"""
        s1 = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
        )
        s2 = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
        )

        assert s1 == s2

    def test_unequal_summaries(self):
        """Given: 다른 값 When: 비교 Then: 비동등"""
        s1 = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
        )
        s2 = MarketSummary(
            ticker="KRW-ETH",  # 다른 티커
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
        )

        assert s1 != s2
