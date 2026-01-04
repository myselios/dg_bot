"""
백테스팅 성과 분석 테스트
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from src.backtesting.performance import PerformanceAnalyzer
from src.backtesting.portfolio import Trade


class TestPerformanceAnalyzer:
    """PerformanceAnalyzer 클래스 테스트"""
    
    @pytest.mark.unit
    def test_calculate_metrics_basic(self):
        """기본 성과 지표 계산 테스트"""
        # Given
        initial_capital = 10000.0
        equity_curve = [10000.0, 10100.0, 10200.0, 10150.0, 10300.0]
        trades = []
        
        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=initial_capital
        )
        
        # Then
        assert 'total_return' in metrics
        assert 'final_equity' in metrics
        assert 'total_trades' in metrics
        assert metrics['total_trades'] == 0
        assert metrics['final_equity'] == equity_curve[-1]
        assert metrics['total_return'] == 3.0  # (10300 - 10000) / 10000 * 100
    
    @pytest.mark.unit
    def test_calculate_metrics_with_trades(self):
        """거래가 있을 때 성과 지표 계산 테스트"""
        # Given
        initial_capital = 10000.0
        equity_curve = [10000.0, 10100.0, 10200.0, 10150.0, 10300.0]
        
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        exit_time = datetime(2024, 1, 1, 12, 0, 0)
        
        trades = [
            Trade(
                symbol='KRW-BTC',
                entry_price=100.0,
                exit_price=110.0,
                size=1.0,
                entry_time=entry_time,
                exit_time=exit_time,
                pnl=10.0,
                pnl_percent=10.0,
                commission=5.0
            ),
            Trade(
                symbol='KRW-BTC',
                entry_price=110.0,
                exit_price=105.0,
                size=1.0,
                entry_time=entry_time,
                exit_time=exit_time,
                pnl=-5.0,
                pnl_percent=-4.55,
                commission=5.0
            )
        ]
        
        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=initial_capital
        )
        
        # Then
        assert metrics['total_trades'] == 2
        assert metrics['winning_trades'] == 1
        assert metrics['losing_trades'] == 1
        assert metrics['win_rate'] == 50.0
        assert metrics['avg_win'] == 10.0
        assert metrics['avg_loss'] == -5.0
    
    @pytest.mark.unit
    def test_calculate_max_drawdown(self):
        """최대 낙폭 계산 테스트"""
        # Given
        equity_series = pd.Series([100, 110, 105, 120, 115, 130])
        
        # When
        max_drawdown = PerformanceAnalyzer._calculate_max_drawdown(equity_series)
        
        # Then
        assert max_drawdown < 0  # 낙폭은 음수
        assert abs(max_drawdown) <= 100  # 100% 이하
    
    @pytest.mark.unit
    def test_calculate_sharpe_ratio(self):
        """샤프 비율 계산 테스트"""
        # Given
        returns = pd.Series([0.01, 0.02, -0.01, 0.03, -0.02, 0.01])
        
        # When
        sharpe = PerformanceAnalyzer._calculate_sharpe(returns)
        
        # Then
        assert isinstance(sharpe, (int, float))
    
    @pytest.mark.unit
    def test_calculate_sortino_ratio(self):
        """소르티노 비율 계산 테스트"""
        # Given
        returns = pd.Series([0.01, 0.02, -0.01, 0.03, -0.02, 0.01])
        
        # When
        sortino = PerformanceAnalyzer._calculate_sortino(returns)
        
        # Then
        assert isinstance(sortino, (int, float))
    
    @pytest.mark.unit
    def test_max_consecutive_wins(self):
        """최대 연속 승리 계산 테스트"""
        # Given
        boolean_list = [True, True, False, True, True, True, False]
        
        # When
        max_count = PerformanceAnalyzer._max_consecutive(boolean_list)
        
        # Then
        assert max_count == 3
    
    @pytest.mark.unit
    def test_max_consecutive_losses(self):
        """최대 연속 손실 계산 테스트"""
        # Given
        # False를 True로 변환하여 연속 손실 계산
        boolean_list = [False, False, True, False, False, False, True]
        # False를 True로 변환 (손실 = True)
        loss_list = [not x for x in boolean_list]
        
        # When
        max_count = PerformanceAnalyzer._max_consecutive(loss_list)
        
        # Then
        assert max_count == 3
    
    @pytest.mark.unit
    def test_calculate_metrics_empty_equity_curve(self):
        """빈 자산 곡선 처리 테스트"""
        # Given
        equity_curve = []
        trades = []
        initial_capital = 10000.0
        
        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=initial_capital
        )
        
        # Then
        assert metrics == {}  # 빈 딕셔너리 반환
    
    @pytest.mark.unit
    def test_calculate_metrics_profit_factor(self):
        """수익 팩터 계산 테스트"""
        # Given
        initial_capital = 10000.0
        equity_curve = [10000.0, 10100.0, 10200.0]
        
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        exit_time = datetime(2024, 1, 1, 12, 0, 0)
        
        trades = [
            Trade('KRW-BTC', 100.0, 110.0, 1.0, entry_time, exit_time, 10.0, 10.0, 5.0),
            Trade('KRW-BTC', 110.0, 105.0, 1.0, entry_time, exit_time, -5.0, -4.55, 5.0)
        ]
        
        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=initial_capital
        )
        
        # Then
        assert metrics['profit_factor'] == 2.0  # 10 / 5

