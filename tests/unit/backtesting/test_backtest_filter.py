"""
백테스팅 필터 테스트 (단일 게이트)

통합된 BacktestConfig와 evaluate_backtest() 메서드를 테스트합니다.
"""
import pytest
from typing import Dict, Any

from src.backtesting.quick_filter import (
    QuickBacktestFilter,
    BacktestConfig,
    PassResult,
)


class TestBacktestFilterConfig:
    """BacktestConfig 설정 테스트"""

    def test_backtest_config_exists(self):
        """BacktestConfig 클래스가 존재하는지 확인"""
        config = BacktestConfig()
        assert config is not None

    def test_backtest_config_has_trading_pass_thresholds(self):
        """BacktestConfig는 구 TradingPass 기준의 임계값을 사용"""
        config = BacktestConfig()

        # 기존 TradingPassConfig 기준
        assert config.min_return == 9.0
        assert config.min_win_rate == 35.0
        assert config.min_profit_factor == 1.5
        assert config.min_sharpe_ratio == 0.7
        assert config.max_drawdown == 25.0
        assert config.min_trades == 10


class TestBacktestEvaluation:
    """evaluate_backtest() 메서드 테스트"""

    def test_evaluate_backtest_all_pass(self):
        """모든 필터 통과 시 PASS 반환"""
        qf = QuickBacktestFilter()
        config = BacktestConfig()

        metrics = {
            'total_return': 15.0,
            'win_rate': 50.0,
            'profit_factor': 2.5,
            'sharpe_ratio': 1.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 0.6,
            'max_drawdown': 15.0,
            'consecutive_losses': 3,
            'volatility': 50.0,
            'total_trades': 20,
            'avg_win_loss_ratio': 2.0,
            'avg_holding_hours': 120.0,
            # Expectancy 계산을 위한 필드
            'avg_win': 2.0,  # 평균 수익
            'avg_loss': -1.0,  # 평균 손실
            'monthly_pf_ratio': 0.9
        }

        result = qf.evaluate_backtest(metrics, config)
        assert result.passed is True
        assert result.pass_type == 'backtest'

    def test_evaluate_backtest_partial_fail(self):
        """일부 필터 실패 시 FAIL 반환"""
        qf = QuickBacktestFilter()
        config = BacktestConfig()

        metrics = {
            'total_return': 5.0,  # 실패: min_return=9.0 미달
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 0.6,
            'max_drawdown': 15.0,
            'consecutive_losses': 3,
            'volatility': 50.0,
            'total_trades': 20,
            'avg_win_loss_ratio': 1.5,
            'avg_holding_hours': 120.0,
            'expectancy': 1.5,
            'monthly_pf_ratio': 0.8
        }

        result = qf.evaluate_backtest(metrics, config)
        assert result.passed is False
        assert result.pass_type == 'backtest'

    def test_evaluate_backtest_with_expectancy_fail(self):
        """Expectancy 필터 실패 시 FAIL 반환"""
        qf = QuickBacktestFilter()
        config = BacktestConfig()

        metrics = {
            'total_return': 15.0,
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 0.6,
            'max_drawdown': 15.0,
            'consecutive_losses': 3,
            'volatility': 50.0,
            'total_trades': 20,
            'avg_win_loss_ratio': 1.5,
            'avg_holding_hours': 120.0,
            'expectancy': 0.5,  # 실패: 너무 낮음
            'monthly_pf_ratio': 0.3  # 실패: 너무 낮음
        }

        result = qf.evaluate_backtest(metrics, config)
        assert result.passed is False
        assert result.pass_type == 'backtest'


class TestBacktestConfigCustomization:
    """BacktestConfig 커스터마이징 테스트"""

    def test_backtest_config_custom_thresholds(self):
        """커스텀 임계값으로 BacktestConfig 생성"""
        config = BacktestConfig(
            min_return=15.0,
            min_win_rate=40.0,
            max_drawdown=20.0
        )

        assert config.min_return == 15.0
        assert config.min_win_rate == 40.0
        assert config.max_drawdown == 20.0

    def test_evaluate_backtest_with_custom_config(self):
        """커스텀 설정으로 백테스팅 평가"""
        qf = QuickBacktestFilter()
        config = BacktestConfig(min_return=20.0)  # 엄격한 기준

        metrics = {
            'total_return': 15.0,  # 실패: min_return=20.0 미달
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 0.6,
            'max_drawdown': 15.0,
            'consecutive_losses': 3,
            'volatility': 50.0,
            'total_trades': 20,
            'avg_win_loss_ratio': 1.5,
            'avg_holding_hours': 120.0,
            'expectancy': 1.5,
            'monthly_pf_ratio': 0.8
        }

        result = qf.evaluate_backtest(metrics, config)
        assert result.passed is False


class TestLegacyConfigCompatibility:
    """구 ResearchPassConfig, TradingPassConfig 호환성 테스트"""

    def test_research_pass_config_still_exists(self):
        """ResearchPassConfig는 deprecated이지만 존재해야 함"""
        from src.backtesting.quick_filter import ResearchPassConfig
        config = ResearchPassConfig()
        assert config is not None

    def test_trading_pass_config_still_exists(self):
        """TradingPassConfig는 deprecated이지만 존재해야 함"""
        from src.backtesting.quick_filter import TradingPassConfig
        config = TradingPassConfig()
        assert config is not None

    def test_evaluate_research_pass_still_works(self):
        """evaluate_research_pass()는 deprecated이지만 작동해야 함"""
        qf = QuickBacktestFilter()
        metrics = {
            'total_return': 10.0,
            'win_rate': 35.0,
            'profit_factor': 1.5,
            'sharpe_ratio': 0.6,
            'sortino_ratio': 0.7,
            'calmar_ratio': 0.3,
            'max_drawdown': 20.0,
            'consecutive_losses': 5,
            'volatility': 60.0,
            'total_trades': 15,
            'avg_win_loss_ratio': 1.2,
            'avg_holding_hours': 180.0
        }

        result = qf.evaluate_research_pass(metrics)
        assert result is not None
        assert hasattr(result, 'passed')

    def test_evaluate_trading_pass_still_works(self):
        """evaluate_trading_pass()는 deprecated이지만 작동해야 함"""
        qf = QuickBacktestFilter()
        metrics = {
            'total_return': 15.0,
            'win_rate': 45.0,
            'profit_factor': 2.0,
            'sharpe_ratio': 1.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 0.6,
            'max_drawdown': 15.0,
            'consecutive_losses': 3,
            'volatility': 50.0,
            'total_trades': 20,
            'avg_win_loss_ratio': 1.5,
            'avg_holding_hours': 120.0
        }

        result = qf.evaluate_trading_pass(metrics)
        assert result is not None
        assert hasattr(result, 'passed')
