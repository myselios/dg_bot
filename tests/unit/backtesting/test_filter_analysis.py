"""
Phase 0: 필터별 탈락 사유 분석 테스트

TDD RED Phase - 테스트 먼저 작성
목표: 12개 필터 중 어디서 가장 많이 탈락하는지 + 실패 거리(fail_distance) 파악

수정: gap → fail_distance (항상 >= 0, 0이면 통과)
- min 필터: max(0, threshold - value)
- max 필터: max(0, value - threshold)
"""
import pytest
from dataclasses import dataclass
from typing import Dict, Any, List

from src.backtesting.quick_filter import (
    QuickBacktestFilter,
    BacktestConfig,
    FilterStatistics,
    FilterAnalysisResult,
)


class TestFilterStatisticsCollection:
    """필터별 통계 수집 테스트"""

    @pytest.fixture
    def sample_metrics_passing(self) -> Dict[str, Any]:
        """모든 필터 통과하는 샘플 메트릭"""
        return {
            'total_return': 20.0,  # >= 15%
            'win_rate': 45.0,  # >= 38%
            'profit_factor': 2.0,  # >= 1.8
            'sharpe_ratio': 1.2,  # >= 1.0
            'sortino_ratio': 1.5,  # >= 1.2
            'calmar_ratio': 1.0,  # >= 0.8
            'max_drawdown': -10.0,  # <= 15%
            'max_consecutive_losses': 3,  # <= 5
            'volatility': 40.0,  # <= 50%
            'total_trades': 30,  # >= 20
            'avg_win': 5.0,
            'avg_loss': -3.0,  # avg_win_loss_ratio = 1.67 >= 1.3
            'avg_holding_period_hours': 48.0,  # <= 168h
        }

    @pytest.fixture
    def sample_metrics_failing(self) -> Dict[str, Any]:
        """여러 필터 실패하는 샘플 메트릭"""
        return {
            'total_return': 10.0,  # < 15% - 실패
            'win_rate': 35.0,  # < 38% - 실패
            'profit_factor': 1.5,  # < 1.8 - 실패
            'sharpe_ratio': 0.7,  # < 1.0 - 실패
            'sortino_ratio': 0.9,  # < 1.2 - 실패
            'calmar_ratio': 0.5,  # < 0.8 - 실패
            'max_drawdown': -20.0,  # > 15% - 실패
            'max_consecutive_losses': 4,  # <= 5 - 통과
            'volatility': 45.0,  # <= 50% - 통과
            'total_trades': 25,  # >= 20 - 통과
            'avg_win': 3.0,
            'avg_loss': -3.0,  # avg_win_loss_ratio = 1.0 < 1.3 - 실패
            'avg_holding_period_hours': 100.0,  # <= 168h - 통과
        }

    def test_filter_analysis_returns_statistics_structure(self, sample_metrics_failing):
        """필터 분석 결과가 올바른 구조를 가지는지 확인"""
        config = BacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        # 새로운 메서드: analyze_filter_results
        result = filter_obj.analyze_filter_results(sample_metrics_failing)

        # FilterAnalysisResult 타입 확인
        assert isinstance(result, FilterAnalysisResult)

        # 12개 필터 모두 분석되었는지 확인
        assert len(result.filter_stats) == 12

        # 각 필터 통계가 올바른 구조를 가지는지 확인
        for filter_name, stats in result.filter_stats.items():
            assert isinstance(stats, FilterStatistics)
            assert hasattr(stats, 'metric_value')
            assert hasattr(stats, 'threshold')
            assert hasattr(stats, 'fail_distance')  # gap → fail_distance
            assert hasattr(stats, 'passed')

    def test_fail_distance_for_minimum_filters(self, sample_metrics_failing):
        """최소값 필터(>=)의 fail_distance 계산 확인"""
        config = BacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.analyze_filter_results(sample_metrics_failing)

        # sharpe_ratio 필터: BacktestConfig.min_sharpe_ratio = 0.7
        # 샘플 데이터: 0.7 (통과)
        sharpe_stats = result.filter_stats['sharpe_ratio']
        assert sharpe_stats.metric_value == 0.7
        assert sharpe_stats.threshold == 0.7  # BacktestConfig 기본값
        assert sharpe_stats.fail_distance == pytest.approx(0.0, abs=0.01)
        assert sharpe_stats.passed is True

        # sortino_ratio 필터: BacktestConfig.min_sortino_ratio = 0.9
        # 샘플 데이터: 0.9 (통과)
        sortino_stats = result.filter_stats['sortino_ratio']
        assert sortino_stats.metric_value == 0.9
        assert sortino_stats.threshold == 0.9  # BacktestConfig 기본값
        assert sortino_stats.fail_distance == pytest.approx(0.0, abs=0.01)
        assert sortino_stats.passed is True

    def test_fail_distance_for_maximum_filters(self, sample_metrics_failing):
        """최대값 필터(<=)의 fail_distance 계산 확인"""
        config = BacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.analyze_filter_results(sample_metrics_failing)

        # max_drawdown 필터: BacktestConfig.max_drawdown = 25.0
        # 샘플 데이터: 20.0 (통과)
        dd_stats = result.filter_stats['max_drawdown']
        assert dd_stats.metric_value == 20.0  # abs(max_drawdown)
        assert dd_stats.threshold == 25.0  # BacktestConfig 기본값
        assert dd_stats.fail_distance == pytest.approx(0.0, abs=0.01)
        assert dd_stats.passed is True

    def test_passing_filter_has_zero_fail_distance(self, sample_metrics_failing):
        """통과한 필터는 fail_distance = 0이어야 함"""
        config = BacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.analyze_filter_results(sample_metrics_failing)

        # min_trades 필터: BacktestConfig.min_trades = 30
        # 샘플 데이터: 25 (실패)
        trades_stats = result.filter_stats['min_trades']
        assert trades_stats.metric_value == 25
        assert trades_stats.threshold == 30  # BacktestConfig 기본값
        assert trades_stats.fail_distance == pytest.approx(5.0, abs=0.01)  # 30 - 25
        assert trades_stats.passed is False

        # volatility 필터: BacktestConfig.max_volatility = 80.0
        # 샘플 데이터: 45 (통과)
        vol_stats = result.filter_stats['volatility']
        assert vol_stats.metric_value == 45.0
        assert vol_stats.threshold == 80.0  # BacktestConfig 기본값
        assert vol_stats.fail_distance == pytest.approx(0.0, abs=0.01)
        assert vol_stats.passed is True


class TestFilterStatisticsDataClasses:
    """데이터 클래스 구조 테스트"""

    def test_filter_statistics_dataclass(self):
        """FilterStatistics 데이터클래스 구조"""
        stats = FilterStatistics(
            metric_value=0.7,
            threshold=1.0,
            fail_distance=0.3,  # gap → fail_distance
            passed=False,
            filter_type='minimum',  # 'minimum' 또는 'maximum'
        )

        assert stats.metric_value == 0.7
        assert stats.threshold == 1.0
        assert stats.fail_distance == 0.3
        assert stats.passed is False
        assert stats.filter_type == 'minimum'

    def test_filter_analysis_result_dataclass(self):
        """FilterAnalysisResult 데이터클래스 구조"""
        filter_stats = {
            'sharpe_ratio': FilterStatistics(
                metric_value=0.7,
                threshold=1.0,
                fail_distance=0.3,
                passed=False,
                filter_type='minimum',
            )
        }

        result = FilterAnalysisResult(
            filter_stats=filter_stats,
            total_passed=5,
            total_failed=7,
        )

        assert len(result.filter_stats) == 1
        assert result.total_passed == 5
        assert result.total_failed == 7
