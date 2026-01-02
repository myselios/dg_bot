"""
백테스팅 엔진 테스트
"""
import pytest
import pandas as pd
from datetime import datetime
from src.backtesting.backtester import Backtester, BacktestResult
from src.backtesting.strategy import Strategy, Signal
from src.backtesting.portfolio import Portfolio


class SimpleStrategy(Strategy):
    """간단한 테스트 전략"""
    
    def __init__(self, buy_on_index=None, sell_on_index=None):
        self.buy_on_index = set(buy_on_index or [])
        self.sell_on_index = set(sell_on_index or [])
        self.current_index = 0
    
    def generate_signal(self, data: pd.DataFrame, portfolio=None):
        """신호 생성"""
        if self.current_index in self.buy_on_index:
            current_price = data['close'].iloc[-1]
            self.current_index += 1
            return Signal(action='buy', price=current_price)
        elif self.current_index in self.sell_on_index:
            current_price = data['close'].iloc[-1]
            self.current_index += 1
            return Signal(action='sell', price=current_price)
        
        self.current_index += 1
        return None
    
    def calculate_position_size(self, signal: Signal, portfolio: Portfolio) -> float:
        """포지션 크기 계산"""
        # 포트폴리오의 10% 사용
        return (portfolio.equity * 0.1) / signal.price


@pytest.fixture
def sample_backtest_data():
    """백테스트용 샘플 데이터"""
    dates = pd.date_range('2024-01-01', periods=10, freq='D')
    return pd.DataFrame({
        'open': [100 + i for i in range(10)],
        'high': [105 + i for i in range(10)],
        'low': [95 + i for i in range(10)],
        'close': [102 + i for i in range(10)],
        'volume': [1000 + i * 10 for i in range(10)]
    }, index=dates)


class TestBacktester:
    """Backtester 클래스 테스트"""
    
    @pytest.mark.unit
    def test_backtester_initialization(self, sample_backtest_data):
        """백테스터 초기화 테스트"""
        # Given
        strategy = SimpleStrategy()
        ticker = 'KRW-BTC'
        initial_capital = 10000.0
        
        # When
        backtester = Backtester(
            strategy=strategy,
            data=sample_backtest_data,
            ticker=ticker,
            initial_capital=initial_capital
        )
        
        # Then
        assert backtester.strategy == strategy
        assert backtester.ticker == ticker
        assert backtester.initial_capital == initial_capital
        assert backtester.portfolio.initial_capital == initial_capital
        assert len(backtester.orders) == 0
        assert len(backtester.trades) == 0
        assert len(backtester.equity_curve) == 0
    
    @pytest.mark.unit
    def test_backtester_run_no_trades(self, sample_backtest_data):
        """거래가 없는 백테스트 실행 테스트"""
        # Given
        strategy = SimpleStrategy()  # 신호 없음
        backtester = Backtester(
            strategy=strategy,
            data=sample_backtest_data,
            ticker='KRW-BTC',
            initial_capital=10000.0
        )
        
        # When
        result = backtester.run()
        
        # Then
        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 10000.0
        assert len(result.equity_curve) == len(sample_backtest_data)
        assert len(result.trades) == 0
        assert 'total_return' in result.metrics
    
    @pytest.mark.unit
    def test_backtester_run_with_buy_signal(self, sample_backtest_data):
        """매수 신호가 있는 백테스트 실행 테스트"""
        # Given
        strategy = SimpleStrategy(buy_on_index=[5])  # 5번째 인덱스에서 매수
        backtester = Backtester(
            strategy=strategy,
            data=sample_backtest_data,
            ticker='KRW-BTC',
            initial_capital=10000.0
        )
        
        # When
        result = backtester.run()
        
        # Then
        assert len(backtester.orders) > 0
        assert any(order['action'] == 'buy' for order in backtester.orders)
        # 포지션이 열려있어야 함
        assert 'KRW-BTC' in backtester.portfolio.positions
    
    @pytest.mark.unit
    def test_backtester_run_with_buy_and_sell(self, sample_backtest_data):
        """매수 후 매도 신호가 있는 백테스트 실행 테스트"""
        # Given
        strategy = SimpleStrategy(
            buy_on_index=[3],
            sell_on_index=[7]
        )
        backtester = Backtester(
            strategy=strategy,
            data=sample_backtest_data,
            ticker='KRW-BTC',
            initial_capital=10000.0
        )
        
        # When
        result = backtester.run()
        
        # Then
        assert len(backtester.orders) >= 2
        assert any(order['action'] == 'buy' for order in backtester.orders)
        assert any(order['action'] == 'sell' for order in backtester.orders)
        assert len(result.trades) > 0
        # 포지션이 청산되었어야 함
        assert 'KRW-BTC' not in backtester.portfolio.positions
    
    @pytest.mark.unit
    def test_backtester_equity_curve_updates(self, sample_backtest_data):
        """자산 곡선 업데이트 테스트"""
        # Given
        strategy = SimpleStrategy()
        backtester = Backtester(
            strategy=strategy,
            data=sample_backtest_data,
            ticker='KRW-BTC',
            initial_capital=10000.0
        )
        
        # When
        result = backtester.run()
        
        # Then
        assert len(result.equity_curve) == len(sample_backtest_data)
        assert result.equity_curve[0] == 10000.0  # 초기 자본
        # 모든 값이 양수여야 함
        assert all(value > 0 for value in result.equity_curve)
    
    @pytest.mark.unit
    def test_backtester_commission_and_slippage(self, sample_backtest_data):
        """수수료와 슬리피지 적용 테스트"""
        # Given
        strategy = SimpleStrategy(buy_on_index=[5])
        backtester = Backtester(
            strategy=strategy,
            data=sample_backtest_data,
            ticker='KRW-BTC',
            initial_capital=10000.0,
            commission=0.001,  # 0.1%
            slippage=0.0002    # 0.02%
        )
        
        # When
        result = backtester.run()
        
        # Then
        # 수수료와 슬리피지가 적용되어 현금이 더 적게 남아야 함
        assert backtester.portfolio.cash < 10000.0
        if 'KRW-BTC' in backtester.portfolio.positions:
            position = backtester.portfolio.positions['KRW-BTC']
            # 슬리피지가 적용되었음을 확인 (entry_price가 양수여야 함)
            assert position.entry_price > 0
            # 슬리피지 비율 확인 (0.02% = 0.0002)
            # 실제 체결 가격이 데이터 범위 내에 있어야 함
            min_price = sample_backtest_data['close'].min()
            max_price = sample_backtest_data['close'].max() * 1.01  # 슬리피지 포함
            assert min_price <= position.entry_price <= max_price

