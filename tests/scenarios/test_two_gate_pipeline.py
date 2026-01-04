"""
Phase 3: 2단 게이트 파이프라인 통합 테스트

TDD RED Phase - 테스트 먼저 작성
목표: Research → AI → Trading 파이프라인 완성

핵심 설계 (P0-5): 1 Backtest, 2 Evaluations
- 백테스트는 1회만 실행 (비용/시간 절약)
- Research/Trading은 같은 metrics에 다른 임계값 적용
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.backtesting.quick_filter import (
    QuickBacktestFilter,
    QuickBacktestConfig,
    ResearchPassConfig,
    TradingPassConfig,
    PassResult,
)


class TestTwoGatePipelineFlow:
    """2단 게이트 파이프라인 흐름 테스트"""

    @pytest.fixture
    def good_metrics(self) -> Dict[str, Any]:
        """좋은 전략 메트릭 (Research, Trading 모두 통과)"""
        return {
            'total_return': 25.0,
            'win_rate': 48.0,
            'profit_factor': 2.2,
            'sharpe_ratio': 1.3,
            'sortino_ratio': 1.6,
            'calmar_ratio': 1.1,
            'max_drawdown': -10.0,
            'max_consecutive_losses': 3,
            'volatility': 35.0,
            'total_trades': 65,
            'avg_win': 5.5,
            'avg_loss': -2.5,
            'avg_holding_period_hours': 36.0,
        }

    @pytest.fixture
    def moderate_metrics(self) -> Dict[str, Any]:
        """중간 전략 메트릭 (Research 통과, Trading 실패)"""
        return {
            'total_return': 10.0,
            'win_rate': 35.0,
            'profit_factor': 1.4,
            'sharpe_ratio': 0.55,
            'sortino_ratio': 0.7,
            'calmar_ratio': 0.35,
            'max_drawdown': -22.0,
            'max_consecutive_losses': 5,
            'volatility': 55.0,
            'total_trades': 35,
            'avg_win': 4.0,
            'avg_loss': -3.0,
            'avg_holding_period_hours': 80.0,
        }

    @pytest.fixture
    def poor_metrics(self) -> Dict[str, Any]:
        """나쁜 전략 메트릭 (Research도 실패)"""
        return {
            'total_return': 3.0,
            'win_rate': 25.0,
            'profit_factor': 0.9,
            'sharpe_ratio': 0.1,
            'sortino_ratio': 0.2,
            'calmar_ratio': 0.1,
            'max_drawdown': -40.0,
            'max_consecutive_losses': 10,
            'volatility': 120.0,
            'total_trades': 15,
            'avg_win': 2.0,
            'avg_loss': -3.0,
            'avg_holding_period_hours': 150.0,
        }

    def test_good_strategy_passes_both_gates(self, good_metrics):
        """좋은 전략은 Research, Trading 모두 통과"""
        research_filter = QuickBacktestFilter(ResearchPassConfig())
        trading_filter = QuickBacktestFilter(TradingPassConfig())

        research_result = research_filter.evaluate_research_pass(good_metrics)
        trading_result = trading_filter.evaluate_trading_pass(good_metrics)

        assert research_result.passed is True
        assert trading_result.passed is True

    def test_moderate_strategy_passes_research_fails_trading(self, moderate_metrics):
        """중간 전략은 Research 통과, Trading 실패"""
        research_filter = QuickBacktestFilter(ResearchPassConfig())
        trading_filter = QuickBacktestFilter(TradingPassConfig())

        research_result = research_filter.evaluate_research_pass(moderate_metrics)
        trading_result = trading_filter.evaluate_trading_pass(moderate_metrics)

        assert research_result.passed is True
        assert trading_result.passed is False

    def test_poor_strategy_fails_both_gates(self, poor_metrics):
        """나쁜 전략은 Research도 실패"""
        research_filter = QuickBacktestFilter(ResearchPassConfig())

        research_result = research_filter.evaluate_research_pass(poor_metrics)

        assert research_result.passed is False


class TestExpectancyIntegration:
    """기대값 필터 통합 테스트"""

    @pytest.fixture
    def metrics_with_win_loss(self) -> Dict[str, Any]:
        """승률과 손익비 포함 메트릭"""
        return {
            'total_return': 15.0,
            'win_rate': 35.0,  # 0.35
            'profit_factor': 1.6,
            'sharpe_ratio': 0.8,
            'sortino_ratio': 1.0,
            'calmar_ratio': 0.5,
            'max_drawdown': -18.0,
            'max_consecutive_losses': 4,
            'volatility': 50.0,
            'total_trades': 55,
            'avg_win': 3.5,
            'avg_loss': -2.0,  # R = 1.75
            'avg_holding_period_hours': 60.0,
        }

    def test_trading_pass_includes_expectancy_check(self, metrics_with_win_loss):
        """Trading Pass는 기대값 검증 포함"""
        config = TradingPassConfig()
        filter_obj = QuickBacktestFilter(config)

        # check_expectancy_with_metrics 메서드 호출 가능 확인
        result = filter_obj.check_expectancy_with_metrics(metrics_with_win_loss)

        assert 'passed' in result
        assert 'net_expectancy' in result
        assert 'min_r_required' in result

    def test_logical_conflict_blocked_by_expectancy(self):
        """논리적 충돌 조합 (승률 33% + R=1.0) 차단"""
        metrics = {
            'total_return': 15.0,
            'win_rate': 33.0,  # 0.33
            'profit_factor': 1.2,
            'sharpe_ratio': 0.5,
            'sortino_ratio': 0.6,
            'calmar_ratio': 0.3,
            'max_drawdown': -20.0,
            'max_consecutive_losses': 6,
            'volatility': 70.0,
            'total_trades': 40,
            'avg_win': 2.5,
            'avg_loss': -2.5,  # R = 1.0
            'avg_holding_period_hours': 100.0,
        }

        config = TradingPassConfig()
        filter_obj = QuickBacktestFilter(config)

        result = filter_obj.check_expectancy_with_metrics(metrics)

        assert result['passed'] is False
        assert result['net_expectancy'] < 0


class TestCachingMechanism:
    """캐싱 메커니즘 테스트 (P0-5, P0-8, P0-13)"""

    def test_start_scan_cycle_returns_run_id(self):
        """start_scan_cycle은 run_id를 반환해야 함"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        run_id = filter_obj.start_scan_cycle()

        assert run_id is not None
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_get_or_run_backtest_without_start_scan_cycle_raises_error(self):
        """start_scan_cycle 호출 없이 get_or_run_backtest 호출 시 RuntimeError"""
        config = QuickBacktestConfig()
        filter_obj = QuickBacktestFilter(config)

        # start_scan_cycle() 없이 호출 시 RuntimeError
        with pytest.raises(RuntimeError, match="Must call start_scan_cycle"):
            filter_obj.get_or_run_backtest("KRW-BTC")

    def test_same_ticker_uses_cached_metrics(self):
        """같은 ticker는 캐시된 metrics 사용"""
        config = ResearchPassConfig()
        filter_obj = QuickBacktestFilter(config)

        # Mock the backtest method to track calls
        filter_obj._run_backtest_internal = Mock(return_value={
            'total_return': 20.0,
            'win_rate': 45.0,
            'profit_factor': 1.8,
            'sharpe_ratio': 1.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 0.8,
            'max_drawdown': -12.0,
            'max_consecutive_losses': 3,
            'volatility': 40.0,
            'total_trades': 50,
            'avg_win': 4.0,
            'avg_loss': -2.5,
            'avg_holding_period_hours': 48.0,
        })

        filter_obj.start_scan_cycle()

        # 첫 번째 호출 - 백테스트 실행
        metrics1 = filter_obj.get_or_run_backtest("KRW-BTC")

        # 두 번째 호출 - 캐시 사용
        metrics2 = filter_obj.get_or_run_backtest("KRW-BTC")

        # 백테스트는 1회만 호출되어야 함
        assert filter_obj._run_backtest_internal.call_count == 1
        assert metrics1 == metrics2

    def test_different_ticker_runs_new_backtest(self):
        """다른 ticker는 새 백테스트 실행"""
        config = ResearchPassConfig()
        filter_obj = QuickBacktestFilter(config)

        call_count = [0]

        def mock_backtest(ticker):
            call_count[0] += 1
            return {'total_return': 10.0 * call_count[0]}

        filter_obj._run_backtest_internal = mock_backtest

        filter_obj.start_scan_cycle()

        metrics_btc = filter_obj.get_or_run_backtest("KRW-BTC")
        metrics_eth = filter_obj.get_or_run_backtest("KRW-ETH")

        assert call_count[0] == 2
        assert metrics_btc['total_return'] != metrics_eth['total_return']


class TestCacheConfigHash:
    """캐시 config_hash 테스트 (P0-13)"""

    def test_config_hash_changes_with_commission(self):
        """commission 변경 시 config_hash 변경"""
        config1 = ResearchPassConfig(commission=0.0005)
        config2 = ResearchPassConfig(commission=0.001)

        filter1 = QuickBacktestFilter(config1)
        filter2 = QuickBacktestFilter(config2)

        filter1.start_scan_cycle()
        filter2.start_scan_cycle()

        # config_hash가 달라야 함
        assert filter1._current_config_hash != filter2._current_config_hash

    def test_config_hash_changes_with_slippage(self):
        """slippage 변경 시 config_hash 변경"""
        config1 = ResearchPassConfig(slippage=0.0001)
        config2 = ResearchPassConfig(slippage=0.0005)

        filter1 = QuickBacktestFilter(config1)
        filter2 = QuickBacktestFilter(config2)

        filter1.start_scan_cycle()
        filter2.start_scan_cycle()

        assert filter1._current_config_hash != filter2._current_config_hash

    def test_same_config_same_hash(self):
        """같은 config는 같은 hash"""
        config1 = ResearchPassConfig()
        config2 = ResearchPassConfig()

        filter1 = QuickBacktestFilter(config1)
        filter2 = QuickBacktestFilter(config2)

        filter1.start_scan_cycle()
        filter2.start_scan_cycle()

        assert filter1._current_config_hash == filter2._current_config_hash


class TestOneBacktestTwoEvaluations:
    """1 Backtest, 2 Evaluations 테스트 (P0-5)"""

    def test_evaluate_both_passes_with_same_metrics(self):
        """같은 metrics로 Research, Trading 모두 평가"""
        metrics = {
            'total_return': 18.0,
            'win_rate': 42.0,
            'profit_factor': 1.7,
            'sharpe_ratio': 0.9,
            'sortino_ratio': 1.1,
            'calmar_ratio': 0.6,
            'max_drawdown': -15.0,
            'max_consecutive_losses': 4,
            'volatility': 45.0,
            'total_trades': 45,
            'avg_win': 4.5,
            'avg_loss': -2.8,
            'avg_holding_period_hours': 55.0,
        }

        research_filter = QuickBacktestFilter(ResearchPassConfig())
        trading_filter = QuickBacktestFilter(TradingPassConfig())

        # 같은 metrics에 다른 임계값 적용
        research_result = research_filter.evaluate_research_pass(metrics)
        trading_result = trading_filter.evaluate_trading_pass(metrics)

        # Research는 더 느슨하므로 통과 확률 높음
        # Trading은 더 엄격하므로 통과 확률 낮음
        assert research_result.pass_type == 'research'
        assert trading_result.pass_type == 'trading'


class TestScenarioResearchToTrading:
    """Research → AI → Trading 시나리오 테스트"""

    def test_scenario_research_pass_to_ai(self):
        """시나리오: Research 통과 → AI 분석 대상"""
        metrics = {
            'total_return': 12.0,
            'win_rate': 38.0,
            'profit_factor': 1.5,
            'sharpe_ratio': 0.6,
            'sortino_ratio': 0.8,
            'calmar_ratio': 0.4,
            'max_drawdown': -20.0,
            'max_consecutive_losses': 5,
            'volatility': 60.0,
            'total_trades': 30,
            'avg_win': 3.5,
            'avg_loss': -2.5,
            'avg_holding_period_hours': 70.0,
        }

        research_filter = QuickBacktestFilter(ResearchPassConfig())
        research_result = research_filter.evaluate_research_pass(metrics)

        # Research 통과 → AI 분석 대상으로 선정
        if research_result.passed:
            # AI 분석 수행 (mock)
            ai_decision = "BUY"

            if ai_decision == "BUY":
                # Trading Pass 평가
                trading_filter = QuickBacktestFilter(TradingPassConfig())
                trading_result = trading_filter.evaluate_trading_pass(metrics)

                # Trading 결과에 따라 실거래 결정
                assert trading_result.pass_type == 'trading'
