"""
BreakoutFilter Domain Service Tests

TDD - Red: 테스트 먼저 작성
규칙 기반 돌파 필터링 (AI 없이)
"""
import pytest
from decimal import Decimal

from src.domain.services.breakout_filter import (
    BreakoutFilter,
    FilterResult,
    FilterReason,
)
from src.domain.value_objects.market_summary import (
    MarketSummary,
    MarketRegime,
    BreakoutStrength,
)


class TestFilterResult:
    """필터 결과 테스트"""

    def test_filter_result_pass(self):
        """Given: PASS 결과 When: 생성 Then: 올바른 값"""
        result = FilterResult.create_passed("All conditions met")

        assert result.passed is True
        assert "All conditions" in result.reason

    def test_filter_result_fail(self):
        """Given: FAIL 결과 When: 생성 Then: 올바른 값"""
        result = FilterResult.failed(
            FilterReason.RSI_OVERBOUGHT,
            "RSI is 78, above threshold 70"
        )

        assert result.passed is False
        assert result.filter_reason == FilterReason.RSI_OVERBOUGHT

    def test_filter_result_with_score(self):
        """Given: 점수 포함 When: 생성 Then: 점수 저장"""
        result = FilterResult.create_passed("Good", score=85)
        assert result.score == 85


class TestFilterReason:
    """필터 이유 열거형 테스트"""

    def test_reason_values(self):
        """Given: 필터 이유 When: 값 확인 Then: 정의된 이유"""
        assert FilterReason.RSI_OVERBOUGHT.value == "rsi_overbought"
        assert FilterReason.RSI_OVERSOLD.value == "rsi_oversold"
        assert FilterReason.HIGH_VOLATILITY.value == "high_volatility"
        assert FilterReason.LOW_VOLUME.value == "low_volume"
        assert FilterReason.WEAK_BREAKOUT.value == "weak_breakout"
        assert FilterReason.UNFAVORABLE_REGIME.value == "unfavorable_regime"


class TestBreakoutFilterCreation:
    """BreakoutFilter 생성 테스트"""

    def test_create_with_defaults(self):
        """Given: 기본값 When: 생성 Then: 기본 임계값"""
        filter_ = BreakoutFilter()

        assert filter_.rsi_overbought == 70
        assert filter_.rsi_oversold == 30
        assert filter_.max_atr_percent == Decimal("5.0")
        assert filter_.min_volume_ratio == Decimal("0.8")

    def test_create_with_custom_thresholds(self):
        """Given: 커스텀 임계값 When: 생성 Then: 설정된 값"""
        filter_ = BreakoutFilter(
            rsi_overbought=75,
            rsi_oversold=25,
            max_atr_percent=Decimal("4.0"),
        )

        assert filter_.rsi_overbought == 75
        assert filter_.rsi_oversold == 25
        assert filter_.max_atr_percent == Decimal("4.0")


class TestBreakoutFilterApply:
    """BreakoutFilter 적용 테스트"""

    @pytest.fixture
    def filter_(self):
        """기본 필터 인스턴스"""
        return BreakoutFilter()

    def test_pass_favorable_conditions(self, filter_):
        """Given: 유리한 조건 When: apply Then: PASS"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            volume_ratio=Decimal("1.5"),
            rsi=Decimal("55"),
        )

        result = filter_.apply(summary)

        assert result.passed is True

    def test_fail_rsi_overbought(self, filter_):
        """Given: RSI 과매수 When: apply Then: FAIL"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            rsi=Decimal("78"),  # 과매수
        )

        result = filter_.apply(summary)

        assert result.passed is False
        assert result.filter_reason == FilterReason.RSI_OVERBOUGHT

    def test_fail_rsi_oversold(self, filter_):
        """Given: RSI 과매도 When: apply Then: FAIL"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_DOWN,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.WEAK,
            risk_budget=Decimal("0.02"),
            rsi=Decimal("22"),  # 과매도
        )

        result = filter_.apply(summary)

        assert result.passed is False
        assert result.filter_reason == FilterReason.RSI_OVERSOLD

    def test_fail_high_volatility(self, filter_):
        """Given: 고변동성 When: apply Then: FAIL"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.VOLATILE,
            atr_percent=Decimal("6.0"),  # 너무 높음
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            rsi=Decimal("55"),
        )

        result = filter_.apply(summary)

        assert result.passed is False
        assert result.filter_reason == FilterReason.HIGH_VOLATILITY

    def test_fail_low_volume(self, filter_):
        """Given: 낮은 거래량 When: apply Then: FAIL"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.MODERATE,
            risk_budget=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),  # 낮음
            rsi=Decimal("55"),
        )

        result = filter_.apply(summary)

        assert result.passed is False
        assert result.filter_reason == FilterReason.LOW_VOLUME

    def test_fail_weak_breakout(self, filter_):
        """Given: 약한 돌파 When: apply Then: FAIL"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.RANGING,
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.NONE,  # 돌파 없음
            risk_budget=Decimal("0.02"),
            rsi=Decimal("55"),
        )

        result = filter_.apply(summary)

        assert result.passed is False
        assert result.filter_reason == FilterReason.WEAK_BREAKOUT

    def test_fail_unfavorable_regime(self, filter_):
        """Given: 불리한 시장 상태 When: apply Then: FAIL"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_DOWN,  # 하락 추세
            atr_percent=Decimal("2.5"),
            breakout_strength=BreakoutStrength.MODERATE,
            risk_budget=Decimal("0.02"),
            rsi=Decimal("55"),
        )

        result = filter_.apply(summary)

        assert result.passed is False
        assert result.filter_reason == FilterReason.UNFAVORABLE_REGIME


class TestBreakoutFilterScore:
    """필터 점수 계산 테스트"""

    @pytest.fixture
    def filter_(self):
        """기본 필터 인스턴스"""
        return BreakoutFilter()

    def test_calculate_score_high(self, filter_):
        """Given: 좋은 조건 When: calculate_score Then: 높은 점수"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_UP,
            atr_percent=Decimal("2.0"),
            breakout_strength=BreakoutStrength.STRONG,
            risk_budget=Decimal("0.02"),
            volume_ratio=Decimal("2.0"),
            rsi=Decimal("55"),
        )

        score = filter_.calculate_score(summary)

        assert score >= 80

    def test_calculate_score_medium(self, filter_):
        """Given: 보통 조건 When: calculate_score Then: 중간 점수"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.RANGING,
            atr_percent=Decimal("3.0"),
            breakout_strength=BreakoutStrength.MODERATE,
            risk_budget=Decimal("0.02"),
            volume_ratio=Decimal("1.2"),
            rsi=Decimal("50"),
        )

        score = filter_.calculate_score(summary)

        assert 40 <= score < 80

    def test_calculate_score_low(self, filter_):
        """Given: 나쁜 조건 When: calculate_score Then: 낮은 점수"""
        summary = MarketSummary(
            ticker="KRW-BTC",
            regime=MarketRegime.TRENDING_DOWN,
            atr_percent=Decimal("5.0"),
            breakout_strength=BreakoutStrength.WEAK,
            risk_budget=Decimal("0.02"),
            volume_ratio=Decimal("0.7"),
            rsi=Decimal("75"),
        )

        score = filter_.calculate_score(summary)

        assert score < 40


class TestBreakoutFilterBatch:
    """배치 필터링 테스트"""

    @pytest.fixture
    def filter_(self):
        """기본 필터 인스턴스"""
        return BreakoutFilter()

    def test_filter_batch(self, filter_):
        """Given: 여러 요약 When: filter_batch Then: 통과한 것만 반환"""
        summaries = [
            # 통과
            MarketSummary(
                ticker="KRW-BTC",
                regime=MarketRegime.TRENDING_UP,
                atr_percent=Decimal("2.0"),
                breakout_strength=BreakoutStrength.STRONG,
                risk_budget=Decimal("0.02"),
                rsi=Decimal("55"),
            ),
            # 실패 (과매수)
            MarketSummary(
                ticker="KRW-ETH",
                regime=MarketRegime.TRENDING_UP,
                atr_percent=Decimal("2.5"),
                breakout_strength=BreakoutStrength.MODERATE,
                risk_budget=Decimal("0.02"),
                rsi=Decimal("80"),
            ),
            # 통과
            MarketSummary(
                ticker="KRW-XRP",
                regime=MarketRegime.RANGING,
                atr_percent=Decimal("2.0"),
                breakout_strength=BreakoutStrength.MODERATE,
                risk_budget=Decimal("0.02"),
                rsi=Decimal("50"),
                volume_ratio=Decimal("1.2"),
            ),
        ]

        passed = filter_.filter_batch(summaries)

        assert len(passed) == 2
        assert passed[0].ticker == "KRW-BTC"
        assert passed[1].ticker == "KRW-XRP"

    def test_filter_batch_with_limit(self, filter_):
        """Given: 여러 요약 + 제한 When: filter_batch Then: 상위 N개만"""
        summaries = [
            MarketSummary(
                ticker=f"KRW-COIN{i}",
                regime=MarketRegime.TRENDING_UP,
                atr_percent=Decimal("2.0"),
                breakout_strength=BreakoutStrength.STRONG,
                risk_budget=Decimal("0.02"),
                rsi=Decimal("55"),
            )
            for i in range(5)
        ]

        passed = filter_.filter_batch(summaries, limit=3)

        assert len(passed) == 3

    def test_rank_by_score(self, filter_):
        """Given: 여러 요약 When: rank_by_score Then: 점수순 정렬"""
        summaries = [
            MarketSummary(
                ticker="KRW-LOW",
                regime=MarketRegime.RANGING,
                atr_percent=Decimal("4.0"),
                breakout_strength=BreakoutStrength.WEAK,
                risk_budget=Decimal("0.02"),
                rsi=Decimal("60"),
            ),
            MarketSummary(
                ticker="KRW-HIGH",
                regime=MarketRegime.TRENDING_UP,
                atr_percent=Decimal("2.0"),
                breakout_strength=BreakoutStrength.STRONG,
                risk_budget=Decimal("0.02"),
                rsi=Decimal("55"),
                volume_ratio=Decimal("2.0"),
            ),
        ]

        ranked = filter_.rank_by_score(summaries)

        assert ranked[0][0].ticker == "KRW-HIGH"  # 높은 점수 먼저
        assert ranked[0][1] > ranked[1][1]  # 점수 비교
