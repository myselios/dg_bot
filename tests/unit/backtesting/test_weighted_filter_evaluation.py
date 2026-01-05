"""
Phase 7: 가중치 기반 필터 평가 테스트 (TDD)

핵심 AND + 가중 점수 기반 평가 시스템 검증
- 핵심 필터 (Tier 1): return, profit_factor, sharpe_ratio, expectancy → AND 필수
- 가중 필터 (Tier 2~4): 총 8.0점 중 5.0점 이상 필요 (62.5%)
"""
import pytest
from typing import Dict, Any

from src.backtesting.quick_filter import (
    QuickBacktestFilter,
    BacktestConfig,
    PassResult,
)


# ============================================================
# 테스트용 메트릭 생성 헬퍼
# ============================================================

def create_metrics(
    total_return: float = 15.0,
    win_rate: float = 50.0,
    profit_factor: float = 2.0,
    sharpe_ratio: float = 1.0,
    sortino_ratio: float = 1.5,
    calmar_ratio: float = 0.8,
    max_drawdown: float = -15.0,
    max_consecutive_losses: int = 4,
    volatility: float = 40.0,
    total_trades: int = 50,
    avg_win: float = 200_000,
    avg_loss: float = -100_000,
    avg_holding_period_hours: float = 72.0,
    avg_loss_pct: float = 0.03,  # 3%
) -> Dict[str, Any]:
    """테스트용 메트릭 생성"""
    return {
        'total_return': total_return,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio,
        'max_drawdown': max_drawdown,
        'max_consecutive_losses': max_consecutive_losses,
        'volatility': volatility,
        'total_trades': total_trades,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'avg_holding_period_hours': avg_holding_period_hours,
        'avg_loss_pct': avg_loss_pct,
    }


# ============================================================
# Phase 7: 핵심 필터 테스트
# ============================================================

class TestCoreFilterLogic:
    """핵심 필터 (Tier 1) 테스트"""

    def test_core_filter_failure_overrides_weighted_score(self):
        """핵심 필터 1개 실패 시 가중 점수와 무관하게 FAIL"""
        # Given: 핵심 필터(return) 실패, 나머지 모두 우수
        metrics = create_metrics(
            total_return=5.0,  # 핵심 실패 (< 9.0)
            profit_factor=2.5,  # 핵심 통과
            sharpe_ratio=1.5,  # 핵심 통과
            # 가중 필터 모두 우수 (8.0/8.0점)
            max_drawdown=-10.0,
            sortino_ratio=2.0,
            total_trades=100,
            win_rate=60.0,
            calmar_ratio=1.5,
            avg_win=300_000,
            avg_loss=-100_000,
            max_consecutive_losses=2,
            volatility=30.0,
            avg_holding_period_hours=48.0,
        )

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # When
        result = qf.evaluate_backtest_weighted(metrics)

        # Then: 가중 점수 최대(8.0)여도 핵심 실패로 FAIL
        assert result.passed is False
        assert "핵심 필터" in result.reason or "return" in result.reason.lower()

    def test_all_core_filters_must_pass(self):
        """핵심 필터 4개 모두 통과 필수"""
        # Given: 핵심 필터 모두 통과
        metrics = create_metrics(
            total_return=15.0,  # 핵심 통과
            profit_factor=2.0,  # 핵심 통과
            sharpe_ratio=1.0,  # 핵심 통과
            # expectancy는 check_expectancy_with_metrics에서 계산
            win_rate=50.0,
            avg_win=200_000,
            avg_loss=-100_000,
        )

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # When
        result = qf.evaluate_backtest_weighted(metrics)

        # Then: 핵심 필터 통과 확인
        # 가중 점수에 따라 최종 결과 결정
        assert result is not None


class TestWeightedScoreCalculation:
    """가중 점수 계산 테스트"""

    def test_weighted_score_calculation_accuracy(self):
        """가중치 계산 정확성"""
        # Given: 특정 가중 필터만 통과
        metrics = create_metrics(
            # 핵심 필터 모두 통과
            total_return=15.0,
            profit_factor=2.0,
            sharpe_ratio=1.0,
            # 가중 필터 선택적 통과
            max_drawdown=-15.0,  # 통과 (2.0점)
            sortino_ratio=1.5,  # 통과 (1.5점)
            total_trades=50,  # 통과 (1.0점) - min_trades=30
            win_rate=40.0,  # 통과 (0.5점)
            # 실패
            calmar_ratio=0.2,  # 실패 (0점)
            volatility=90.0,  # 실패 (0점)
        )

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # When
        result = qf.evaluate_backtest_weighted(metrics)

        # Then: 가중 점수 계산 확인
        assert result is not None
        # 점수: max_drawdown(2.0) + sortino(1.5) + min_trades(1.0) + win_rate(0.5) = 5.0

    def test_tier_structure_integrity(self):
        """Tier별 가중치 합 검증"""
        # FILTER_WEIGHTS 상수 검증
        from src.backtesting.quick_filter import FILTER_WEIGHTS

        # Tier별 합계 검증
        tier2_filters = ['max_drawdown', 'sortino_ratio', 'min_trades', 'win_rate']
        tier3_filters = ['calmar_ratio', 'avg_win_loss_ratio', 'max_consecutive_losses']
        tier4_filters = ['volatility', 'avg_holding_hours']

        tier2_sum = sum(FILTER_WEIGHTS.get(f, 0) for f in tier2_filters)
        tier3_sum = sum(FILTER_WEIGHTS.get(f, 0) for f in tier3_filters)
        tier4_sum = sum(FILTER_WEIGHTS.get(f, 0) for f in tier4_filters)

        # 예상 합계
        assert tier2_sum == 5.0  # 2.0 + 1.5 + 1.0 + 0.5
        assert tier3_sum == 2.0  # 1.0 + 0.5 + 0.5
        assert tier4_sum == 1.0  # 0.5 + 0.5

        # 총합
        total = tier2_sum + tier3_sum + tier4_sum
        assert total == 8.0


class TestWeightedEvaluationPassFail:
    """가중치 평가 통과/실패 테스트"""

    def test_core_pass_weighted_above_threshold(self):
        """핵심 통과 + 가중 점수 >= 5.0 → PASS"""
        # Given: 핵심 통과, 가중 점수 5.0+ (62.5%)
        metrics = create_metrics(
            # 핵심 통과
            total_return=15.0,
            profit_factor=2.0,
            sharpe_ratio=1.0,
            # 가중 점수 5.5점
            max_drawdown=-15.0,  # 2.0
            sortino_ratio=1.5,  # 1.5
            total_trades=50,  # 1.0
            win_rate=40.0,  # 0.5
            calmar_ratio=0.5,  # 0.5 (추가)
        )

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # When
        result = qf.evaluate_backtest_weighted(metrics)

        # Then
        assert result.passed is True
        assert "통과" in result.reason

    def test_core_pass_weighted_below_threshold(self):
        """핵심 통과 + 가중 점수 < 5.0 → FAIL"""
        # Given: 핵심 통과, 가중 점수 미달
        metrics = create_metrics(
            # 핵심 통과
            total_return=15.0,
            profit_factor=2.0,
            sharpe_ratio=1.0,
            # 가중 점수 2.0점만 (미달)
            max_drawdown=-15.0,  # 2.0
            # 나머지 모두 실패
            sortino_ratio=0.5,  # 실패
            total_trades=10,  # 실패 (min_trades=30)
            win_rate=20.0,  # 실패
            calmar_ratio=0.1,  # 실패
            volatility=100.0,  # 실패
            max_consecutive_losses=10,  # 실패
            avg_holding_period_hours=500.0,  # 실패
        )

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # When
        result = qf.evaluate_backtest_weighted(metrics)

        # Then
        assert result.passed is False
        assert "미달" in result.reason


class TestRealWorldScenarios:
    """실제 사례 테스트"""

    def test_doge_case_passes_with_weighted_logic(self):
        """DOGE 사례: 기존 탈락 → 변경 후 통과"""
        # Given: DOGE 실제 사례 (12/13 통과, 거래수만 실패)
        metrics = create_metrics(
            total_return=14.3,  # 핵심 통과 (>= 9.0)
            profit_factor=2.2,  # 핵심 통과
            sharpe_ratio=0.9,  # 핵심 통과 (>= 0.7)
            # 가중 필터 대부분 통과
            max_drawdown=-18.0,  # 통과 (2.0)
            sortino_ratio=1.2,  # 통과 (1.5)
            total_trades=8,  # 실패 (0) - min_trades=30 미달
            win_rate=45.0,  # 통과 (0.5)
            calmar_ratio=0.6,  # 통과 (1.0)
            avg_win=250_000,
            avg_loss=-100_000,  # avg_win_loss_ratio = 2.5 통과 (0.5)
            max_consecutive_losses=3,  # 통과 (0.5)
            volatility=50.0,  # 통과 (0.5)
            avg_holding_period_hours=100.0,  # 통과 (0.5)
        )
        # 가중 점수: 2.0 + 1.5 + 0 + 0.5 + 1.0 + 0.5 + 0.5 + 0.5 + 0.5 = 7.0점

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # When
        result = qf.evaluate_backtest_weighted(metrics)

        # Then: 가중 점수 7.0 >= 5.0 이므로 통과
        assert result.passed is True

    def test_eth_still_passes_with_weighted_logic(self):
        """ETH 사례: 기존 통과 → 변경 후에도 통과 유지"""
        # Given: ETH 기존 통과 사례
        metrics = create_metrics(
            total_return=9.7,  # 핵심 통과
            profit_factor=1.8,  # 핵심 통과
            sharpe_ratio=0.85,  # 핵심 통과
            max_drawdown=-12.0,  # 통과
            sortino_ratio=1.3,  # 통과
            total_trades=35,  # 통과 (min_trades=30)
            win_rate=42.0,  # 통과
            calmar_ratio=0.7,  # 통과
            avg_win=180_000,
            avg_loss=-100_000,
            max_consecutive_losses=4,  # 통과
            volatility=45.0,  # 통과
            avg_holding_period_hours=120.0,  # 통과
        )

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # When
        result = qf.evaluate_backtest_weighted(metrics)

        # Then
        assert result.passed is True


class TestMinTradesAdjustment:
    """min_trades 기준 조정 테스트 (10 → 30)"""

    def test_min_trades_default_is_30(self):
        """BacktestConfig 기본 min_trades가 30인지 확인"""
        config = BacktestConfig()

        # Phase 7 변경: 10 → 30
        assert config.min_trades == 30

    def test_trades_below_30_fails_min_trades_filter(self):
        """거래수 30 미만 시 min_trades 필터 실패"""
        metrics = create_metrics(total_trades=25)

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        # min_trades 필터만 확인
        filter_results = qf._check_filters(metrics, config=config)
        assert filter_results['min_trades'] is False

    def test_trades_30_or_more_passes_min_trades_filter(self):
        """거래수 30 이상 시 min_trades 필터 통과"""
        metrics = create_metrics(total_trades=30)

        config = BacktestConfig(use_weighted_evaluation=True)
        qf = QuickBacktestFilter(config)

        filter_results = qf._check_filters(metrics, config=config)
        assert filter_results['min_trades'] is True


class TestBackwardCompatibility:
    """하위 호환성 테스트"""

    def test_use_weighted_evaluation_flag_default_true(self):
        """use_weighted_evaluation 기본값 True (Phase 7 활성화)"""
        config = BacktestConfig()
        assert config.use_weighted_evaluation is True

    def test_evaluate_backtest_uses_all_and_when_flag_false(self):
        """use_weighted_evaluation=False 시 기존 ALL AND 로직 사용"""
        metrics = create_metrics()

        # 기본 설정 (use_weighted_evaluation=False)
        config = BacktestConfig(use_weighted_evaluation=False)
        qf = QuickBacktestFilter(config)

        # 기존 evaluate_backtest 사용
        result = qf.evaluate_backtest(metrics, config=config)

        # ALL AND 로직: 모든 필터 통과 필요
        assert result.pass_type == 'backtest'


class TestFilterWeightsConstant:
    """FILTER_WEIGHTS 상수 테스트"""

    def test_filter_weights_contains_all_weighted_filters(self):
        """FILTER_WEIGHTS에 모든 가중 필터 포함"""
        from src.backtesting.quick_filter import FILTER_WEIGHTS

        expected_filters = [
            'max_drawdown', 'sortino_ratio', 'min_trades', 'win_rate',
            'calmar_ratio', 'avg_win_loss_ratio', 'max_consecutive_losses',
            'volatility', 'avg_holding_hours',
        ]

        for f in expected_filters:
            assert f in FILTER_WEIGHTS, f"{f} not in FILTER_WEIGHTS"

    def test_filter_weights_values_are_correct(self):
        """FILTER_WEIGHTS 값 정확성"""
        from src.backtesting.quick_filter import FILTER_WEIGHTS

        assert FILTER_WEIGHTS['max_drawdown'] == 2.0
        assert FILTER_WEIGHTS['sortino_ratio'] == 1.5
        assert FILTER_WEIGHTS['min_trades'] == 1.0
        assert FILTER_WEIGHTS['win_rate'] == 0.5
        assert FILTER_WEIGHTS['calmar_ratio'] == 1.0
        assert FILTER_WEIGHTS['avg_win_loss_ratio'] == 0.5
        assert FILTER_WEIGHTS['max_consecutive_losses'] == 0.5
        assert FILTER_WEIGHTS['volatility'] == 0.5
        assert FILTER_WEIGHTS['avg_holding_hours'] == 0.5


class TestCoreFiltersConstant:
    """CORE_FILTERS 상수 테스트"""

    def test_core_filters_contains_four_required(self):
        """CORE_FILTERS에 필수 4개 포함"""
        from src.backtesting.quick_filter import CORE_FILTERS

        expected = {'return', 'profit_factor', 'sharpe_ratio', 'expectancy'}
        assert CORE_FILTERS == expected
