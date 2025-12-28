"""
통합 플로우 테스트 (빠른 백테스팅 필터링 포함)
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from src.backtesting import QuickBacktestFilter, QuickBacktestResult
from src.backtesting.backtester import BacktestResult


@pytest.fixture
def sample_chart_data():
    """샘플 차트 데이터 (30일)"""
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return {
        'day': pd.DataFrame({
            'open': [100 + i * 0.5 for i in range(30)],
            'high': [105 + i * 0.5 for i in range(30)],
            'low': [95 + i * 0.5 for i in range(30)],
            'close': [102 + i * 0.5 for i in range(30)],
            'volume': [1000 + i * 10 for i in range(30)]
        }, index=dates),
        'minute60': pd.DataFrame(),
        'minute15': pd.DataFrame()
    }


@pytest.fixture
def mock_backtest_result_passed():
    """필터링 통과 Mock 백테스트 결과"""
    return BacktestResult(
        initial_capital=10_000_000,
        final_equity=11_000_000,
        equity_curve=[10_000_000 + i * 33333 for i in range(30)],
        trades=[],
        metrics={
            'total_return': 10.0,
            'win_rate': 60.0,
            'sharpe_ratio': 1.5,
            'max_drawdown': -10.0,
            'total_trades': 10,
            'profit_factor': 1.8,
            'final_equity': 11_000_000,
            'volatility': 20.0,
            'sortino_ratio': 1.2,
            'calmar_ratio': 1.0,
            'winning_trades': 6,
            'losing_trades': 4,
            'avg_win': 200_000,
            'avg_loss': -100_000,
            'max_consecutive_wins': 4,
            'max_consecutive_losses': 2,
            'avg_holding_period_hours': 48.0,
            'total_commission': 50_000
        }
    )


@pytest.fixture
def mock_backtest_result_failed():
    """필터링 미달 Mock 백테스트 결과"""
    return BacktestResult(
        initial_capital=10_000_000,
        final_equity=10_300_000,
        equity_curve=[10_000_000 + i * 10000 for i in range(30)],
        trades=[],
        metrics={
            'total_return': 3.0,
            'win_rate': 45.0,
            'sharpe_ratio': 0.5,
            'max_drawdown': -20.0,
            'total_trades': 10,
            'profit_factor': 0.8,
            'final_equity': 10_300_000,
            'volatility': 25.0,
            'sortino_ratio': 0.3,
            'calmar_ratio': 0.15,
            'winning_trades': 4,
            'losing_trades': 6,
            'avg_win': 150_000,
            'avg_loss': -200_000,
            'max_consecutive_wins': 2,
            'max_consecutive_losses': 4,
            'avg_holding_period_hours': 72.0,
            'total_commission': 50_000
        }
    )


class TestIntegratedBacktestFilter:
    """통합 백테스팅 필터 테스트"""
    
    @pytest.mark.integration
    @patch('src.backtesting.quick_filter.BacktestRunner')
    def test_filter_passed_flow(
        self,
        mock_runner_class,
        sample_chart_data,
        mock_backtest_result_passed
    ):
        """필터링 통과 시 플로우 테스트"""
        # Given
        ticker = 'KRW-ETH'
        mock_runner_class.run_backtest = Mock(return_value=mock_backtest_result_passed)
        
        filter_instance = QuickBacktestFilter()
        
        # When
        result = filter_instance.run_quick_backtest(ticker, sample_chart_data)
        
        # Then
        assert result.passed is True
        assert mock_runner_class.run_backtest.called
        assert result.metrics['total_return'] >= 5.0
        assert result.metrics['win_rate'] >= 50.0
        assert result.metrics['sharpe_ratio'] >= 1.0
        assert abs(result.metrics['max_drawdown']) <= 15.0
    
    @pytest.mark.integration
    @patch('src.backtesting.quick_filter.BacktestRunner')
    def test_filter_failed_flow(
        self,
        mock_runner_class,
        sample_chart_data,
        mock_backtest_result_failed
    ):
        """필터링 미달 시 플로우 테스트"""
        # Given
        ticker = 'KRW-ETH'
        mock_runner_class.run_backtest = Mock(return_value=mock_backtest_result_failed)
        
        filter_instance = QuickBacktestFilter()
        
        # When
        result = filter_instance.run_quick_backtest(ticker, sample_chart_data)
        
        # Then
        assert result.passed is False
        assert mock_runner_class.run_backtest.called
        # 최소 하나 이상의 조건이 실패해야 함
        assert not all(result.filter_results.values())
    
    @pytest.mark.integration
    def test_backtest_result_format(self, mock_backtest_result_passed):
        """백테스팅 결과 형식 테스트"""
        # Given
        filter_instance = QuickBacktestFilter()
        
        # When
        filter_results = filter_instance._check_filters(mock_backtest_result_passed.metrics)
        reason = filter_instance._generate_reason(
            mock_backtest_result_passed.metrics,
            filter_results,
            all(filter_results.values())
        )
        
        # Then
        assert isinstance(filter_results, dict)
        assert all(key in filter_results for key in ['return', 'win_rate', 'sharpe_ratio', 'max_drawdown'])
        assert isinstance(reason, str)
        assert len(reason) > 0


