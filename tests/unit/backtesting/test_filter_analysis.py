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

# 아직 구현되지 않은 클래스/함수 - 테스트가 실패해야 함
from src.backtesting.quick_filter import (
    QuickBacktestFilter,
    QuickBacktestConfig,
    FilterStatistics,  # 새로 추가할 클래스
    FilterAnalysisResult,  # 새로 추가할 클래스
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
        config = QuickBacktestConfig()
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
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.analyze_filter_results(sample_metrics_failing)

        # return 필터: max(0, 15.0 - 10.0) = 5.0 (실패 거리)
        return_stats = result.filter_stats['return']
        assert return_stats.metric_value == 10.0
        assert return_stats.threshold == 15.0
        assert return_stats.fail_distance == pytest.approx(5.0, abs=0.01)
        assert return_stats.passed is False

        # sharpe_ratio 필터: max(0, 1.0 - 0.7) = 0.3 (실패 거리)
        sharpe_stats = result.filter_stats['sharpe_ratio']
        assert sharpe_stats.metric_value == 0.7
        assert sharpe_stats.threshold == 1.0
        assert sharpe_stats.fail_distance == pytest.approx(0.3, abs=0.01)
        assert sharpe_stats.passed is False

    def test_fail_distance_for_maximum_filters(self, sample_metrics_failing):
        """최대값 필터(<=)의 fail_distance 계산 확인"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.analyze_filter_results(sample_metrics_failing)

        # max_drawdown 필터: max(0, 20.0 - 15.0) = 5.0 (실패 거리)
        dd_stats = result.filter_stats['max_drawdown']
        assert dd_stats.metric_value == 20.0  # abs(max_drawdown)
        assert dd_stats.threshold == 15.0
        assert dd_stats.fail_distance == pytest.approx(5.0, abs=0.01)
        assert dd_stats.passed is False

    def test_passing_filter_has_zero_fail_distance(self, sample_metrics_failing):
        """통과한 필터는 fail_distance = 0이어야 함"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.analyze_filter_results(sample_metrics_failing)

        # min_trades 필터: 25 >= 20, max(0, 20 - 25) = 0 (통과)
        trades_stats = result.filter_stats['min_trades']
        assert trades_stats.metric_value == 25
        assert trades_stats.threshold == 20
        assert trades_stats.fail_distance == pytest.approx(0.0, abs=0.01)
        assert trades_stats.passed is True

        # volatility 필터: 45 <= 50, max(0, 45 - 50) = 0 (통과)
        vol_stats = result.filter_stats['volatility']
        assert vol_stats.metric_value == 45.0
        assert vol_stats.threshold == 50.0
        assert vol_stats.fail_distance == pytest.approx(0.0, abs=0.01)
        assert vol_stats.passed is True


class TestFilterStatisticsAggregation:
    """필터별 통계 집계 테스트 (3단 비교)"""

    @pytest.fixture
    def multiple_metrics_samples(self) -> List[Dict[str, Any]]:
        """여러 코인의 메트릭 샘플"""
        return [
            # 코인 1: sharpe, return 실패
            {
                'total_return': 10.0,
                'win_rate': 40.0,
                'profit_factor': 2.0,
                'sharpe_ratio': 0.5,
                'sortino_ratio': 1.3,
                'calmar_ratio': 1.0,
                'max_drawdown': -10.0,
                'max_consecutive_losses': 3,
                'volatility': 40.0,
                'total_trades': 30,
                'avg_win': 5.0,
                'avg_loss': -3.0,
                'avg_holding_period_hours': 48.0,
            },
            # 코인 2: sharpe, sortino 실패
            {
                'total_return': 20.0,
                'win_rate': 42.0,
                'profit_factor': 1.9,
                'sharpe_ratio': 0.8,
                'sortino_ratio': 1.0,
                'calmar_ratio': 0.9,
                'max_drawdown': -12.0,
                'max_consecutive_losses': 4,
                'volatility': 45.0,
                'total_trades': 25,
                'avg_win': 4.0,
                'avg_loss': -2.5,
                'avg_holding_period_hours': 72.0,
            },
            # 코인 3: 모두 통과
            {
                'total_return': 25.0,
                'win_rate': 45.0,
                'profit_factor': 2.2,
                'sharpe_ratio': 1.5,
                'sortino_ratio': 1.8,
                'calmar_ratio': 1.2,
                'max_drawdown': -8.0,
                'max_consecutive_losses': 2,
                'volatility': 35.0,
                'total_trades': 40,
                'avg_win': 6.0,
                'avg_loss': -3.0,
                'avg_holding_period_hours': 36.0,
            },
        ]

    def test_aggregate_filter_statistics(self, multiple_metrics_samples):
        """여러 코인의 필터 통계 집계 (3단 비교)"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        # 새로운 메서드: aggregate_filter_statistics
        aggregated = filter_obj.aggregate_filter_statistics(multiple_metrics_samples)

        # 집계 결과 구조 확인
        assert 'sharpe_ratio' in aggregated
        sharpe_agg = aggregated['sharpe_ratio']

        assert 'fail_count' in sharpe_agg
        assert 'pass_count' in sharpe_agg
        assert 'avg_value' in sharpe_agg
        assert 'current_threshold' in sharpe_agg
        assert 'research_threshold' in sharpe_agg
        assert 'trading_threshold' in sharpe_agg
        assert 'avg_fail_distance' in sharpe_agg
        assert 'current_fail_rate' in sharpe_agg
        assert 'research_fail_rate' in sharpe_agg
        assert 'trading_fail_rate' in sharpe_agg
        assert 'verdict' in sharpe_agg

    def test_fail_count_calculation(self, multiple_metrics_samples):
        """실패 카운트 계산 확인"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        aggregated = filter_obj.aggregate_filter_statistics(multiple_metrics_samples)

        # sharpe_ratio: 3개 중 2개 실패 (0.5, 0.8 < 1.0)
        assert aggregated['sharpe_ratio']['fail_count'] == 2
        assert aggregated['sharpe_ratio']['pass_count'] == 1

        # return: 3개 중 1개 실패 (10.0 < 15.0)
        assert aggregated['return']['fail_count'] == 1
        assert aggregated['return']['pass_count'] == 2

    def test_avg_fail_distance_calculation(self, multiple_metrics_samples):
        """평균 fail_distance 계산 확인"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        aggregated = filter_obj.aggregate_filter_statistics(multiple_metrics_samples)

        # sharpe_ratio fail_distance:
        # 코인1: max(0, 1.0 - 0.5) = 0.5
        # 코인2: max(0, 1.0 - 0.8) = 0.2
        # 코인3: max(0, 1.0 - 1.5) = 0.0
        # 평균: (0.5 + 0.2 + 0.0) / 3 = 0.233
        sharpe_avg_fd = aggregated['sharpe_ratio']['avg_fail_distance']
        expected_avg = (0.5 + 0.2 + 0.0) / 3
        assert sharpe_avg_fd == pytest.approx(expected_avg, abs=0.01)

    def test_three_tier_fail_rates(self, multiple_metrics_samples):
        """3단 임계값 기준 실패율 계산"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        aggregated = filter_obj.aggregate_filter_statistics(multiple_metrics_samples)

        # 3단 임계값 확인
        sharpe = aggregated['sharpe_ratio']
        assert sharpe['current_threshold'] == 1.0  # QuickBacktestConfig
        assert sharpe['research_threshold'] == 0.4  # ResearchPassConfig
        assert sharpe['trading_threshold'] == 0.7  # TradingPassConfig

        # 실패율: current > trading > research 순으로 높아야 함
        # (현재 기준이 가장 엄격하므로)

    def test_verdict_based_on_three_tier_comparison(self, multiple_metrics_samples):
        """3단 비교 기반 verdict 생성"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        aggregated = filter_obj.aggregate_filter_statistics(multiple_metrics_samples)

        # verdict는 3단 비교 기반
        # - 현재 fail 높고 Research pass 높음 → "현재 기준 과도"
        # - Research도 fail 높음 → "전략/데이터 문제 가능"
        sharpe_verdict = aggregated['sharpe_ratio']['verdict']
        # sharpe는 Research에서 0.4 기준이므로 대부분 통과
        assert sharpe_verdict in [
            "현재 기준 과도 (Research에선 통과)",
            "완화 검토 필요",
            "통과",
        ]


class TestFilterAnalysisReport:
    """필터 분석 리포트 생성 테스트"""

    @pytest.fixture
    def sample_aggregated_stats(self) -> Dict[str, Dict[str, Any]]:
        """집계된 필터 통계 샘플 (3단 비교 포함)"""
        return {
            'sharpe_ratio': {
                'fail_count': 8,
                'pass_count': 2,
                'avg_value': 0.65,
                'current_threshold': 1.0,
                'research_threshold': 0.4,
                'trading_threshold': 0.7,
                'avg_fail_distance': 0.35,
                'current_fail_rate': 80.0,
                'research_fail_rate': 30.0,  # Research에선 대부분 통과
                'trading_fail_rate': 50.0,
                'verdict': '현재 기준 과도 (Research에선 통과)',
            },
            'return': {
                'fail_count': 5,
                'pass_count': 5,
                'avg_value': 12.0,
                'current_threshold': 15.0,
                'research_threshold': 8.0,
                'trading_threshold': 12.0,
                'avg_fail_distance': 3.0,
                'current_fail_rate': 50.0,
                'research_fail_rate': 20.0,
                'trading_fail_rate': 40.0,
                'verdict': '현재 기준 과도 (Research에선 통과)',
            },
            'profit_factor': {
                'fail_count': 9,
                'pass_count': 1,
                'avg_value': 1.2,
                'current_threshold': 1.8,
                'research_threshold': 1.3,
                'trading_threshold': 1.5,
                'avg_fail_distance': 0.6,
                'current_fail_rate': 90.0,
                'research_fail_rate': 75.0,  # Research에서도 대부분 실패
                'trading_fail_rate': 85.0,
                'verdict': '전략/데이터 문제 가능',
            },
        }

    def test_get_top_failing_filters(self, sample_aggregated_stats):
        """가장 많이 탈락하는 필터 Top 3 식별"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        # 새로운 메서드: get_top_failing_filters
        top_3 = filter_obj.get_top_failing_filters(sample_aggregated_stats, top_n=3)

        assert len(top_3) == 3
        # 실패 카운트 순: profit_factor(9) > sharpe_ratio(8) > return(5)
        assert top_3[0][0] == 'profit_factor'
        assert top_3[1][0] == 'sharpe_ratio'
        assert top_3[2][0] == 'return'

    def test_generate_filter_analysis_report(self, sample_aggregated_stats):
        """필터 분석 리포트 생성 (3단 비교 기반)"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        # 새로운 메서드: generate_filter_analysis_report
        report = filter_obj.generate_filter_analysis_report(sample_aggregated_stats)

        # 리포트 구조 확인
        assert 'top_failing_filters' in report
        assert 'current_too_strict' in report
        assert 'needs_relaxation' in report
        assert 'potential_issues' in report
        assert 'summary' in report

        # current_too_strict: Research에선 통과하는 필터
        assert 'sharpe_ratio' in report['current_too_strict']
        assert 'return' in report['current_too_strict']

        # potential_issues: Research에서도 대부분 실패
        assert 'profit_factor' in report['potential_issues']


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
