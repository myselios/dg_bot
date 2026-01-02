"""
백테스팅 러너 테스트
TDD 원칙: 백테스팅 실행 프로세스를 검증합니다.
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.backtesting.runner import BacktestRunner
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
from src.backtesting.backtester import BacktestResult


class TestBacktestRunner:
    """BacktestRunner 테스트"""
    
    @pytest.fixture
    def sample_data(self):
        """샘플 차트 데이터"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
            'open': [100 + i for i in range(100)],
            'high': [102 + i for i in range(100)],
            'low': [99 + i for i in range(100)],
            'close': [101 + i for i in range(100)],
            'volume': [1000 for _ in range(100)]
        }, index=dates)
    
    @pytest.mark.unit
    def test_runner_initialization(self):
        """러너 초기화 테스트"""
        # When
        runner = BacktestRunner()
        
        # Then
        assert runner is not None
        assert hasattr(runner, 'run_backtest')
    
    @pytest.mark.unit
    def test_run_backtest_with_valid_data(self, sample_data):
        """유효한 데이터로 백테스트 실행"""
        # Given
        runner = BacktestRunner()
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-ETH")
        
        # When
        with patch('src.backtesting.runner.Backtester') as MockBacktester:
            mock_backtester = MockBacktester.return_value
            mock_result = BacktestResult(
                initial_capital=10000000,
                final_equity=11000000,
                equity_curve=[10000000, 11000000],
                trades=[],
                metrics={
                    'total_return': 10.0,
                    'total_trades': 5,
                    'winning_trades': 3,
                    'losing_trades': 2,
                    'win_rate': 60.0,
                    'max_drawdown': 5.0,
                    'sharpe_ratio': 1.5,
                    'profit_factor': 2.0
                }
            )
            mock_backtester.run.return_value = mock_result
            
            result = runner.run_backtest(
                strategy=strategy,
                data=sample_data,
                ticker="KRW-ETH",
                initial_capital=10000000
            )
        
        # Then
        assert result is not None
        assert result.metrics['total_return'] == 10.0
        assert result.metrics['total_trades'] == 5
    
    @pytest.mark.unit
    def test_run_backtest_with_empty_data(self):
        """빈 데이터로 백테스트 실행"""
        # Given
        runner = BacktestRunner()
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-ETH")
        empty_data = pd.DataFrame()

        # When/Then - 빈 데이터는 예외를 발생시키거나 None/빈 결과 반환
        try:
            result = runner.run_backtest(
                strategy=strategy,
                data=empty_data,
                ticker="KRW-ETH"
            )
            # 결과가 반환되면 빈 결과여야 함
            assert result is None or result.metrics.get('total_trades', 0) == 0
        except (KeyError, ValueError, IndexError):
            # 빈 데이터로 인한 예외는 허용
            pass
    
    @pytest.mark.unit
    def test_run_backtest_with_insufficient_data(self):
        """불충분한 데이터로 백테스트 실행"""
        # Given
        runner = BacktestRunner()
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-ETH")
        
        # 매우 적은 데이터 (10개 미만)
        dates = pd.date_range(start='2024-01-01', periods=5, freq='D')
        insufficient_data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104],
            'high': [102, 103, 104, 105, 106],
            'low': [99, 100, 101, 102, 103],
            'close': [101, 102, 103, 104, 105],
            'volume': [1000, 1100, 1200, 1300, 1400]
        }, index=dates)
        
        # When
        result = runner.run_backtest(
            strategy=strategy,
            data=insufficient_data,
            ticker="KRW-ETH"
        )
        
        # Then
        # 데이터가 충분하지 않으면 None이거나 거래가 없어야 함
        assert result is None or result.metrics.get('total_trades', 0) == 0
    
    @pytest.mark.unit
    def test_run_backtest_with_custom_parameters(self, sample_data):
        """커스텀 파라미터로 백테스트 실행"""
        # Given
        runner = BacktestRunner()
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-ETH")
        
        # When
        with patch('src.backtesting.runner.Backtester') as MockBacktester:
            mock_backtester = MockBacktester.return_value
            mock_result = BacktestResult(
                initial_capital=5000000,
                final_equity=5500000,
                equity_curve=[5000000, 5500000],
                trades=[],
                metrics={
                    'total_return': 10.0,
                    'total_trades': 3,
                    'winning_trades': 2,
                    'losing_trades': 1,
                    'win_rate': 66.67,
                    'max_drawdown': 3.0,
                    'sharpe_ratio': 1.8,
                    'profit_factor': 2.5
                }
            )
            mock_backtester.run.return_value = mock_result
            
            result = runner.run_backtest(
                strategy=strategy,
                data=sample_data,
                ticker="KRW-ETH",
                initial_capital=5000000,
                commission=0.001,
                slippage=0.0005
            )
        
        # Then
        assert result is not None
        assert result.initial_capital == 5000000
        assert result.final_equity == 5500000
    
    @pytest.mark.unit
    def test_run_backtest_exception_handling(self, sample_data):
        """백테스트 실행 중 예외 처리"""
        # Given
        runner = BacktestRunner()
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-ETH")
        
        # When
        with pytest.raises(Exception):
            with patch('src.backtesting.runner.Backtester') as MockBacktester:
                MockBacktester.return_value.run.side_effect = Exception("백테스트 오류")
                
                result = runner.run_backtest(
                    strategy=strategy,
                    data=sample_data,
                    ticker="KRW-ETH"
                )

