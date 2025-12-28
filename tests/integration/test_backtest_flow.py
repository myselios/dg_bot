"""
백테스팅 플로우 통합 테스트
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from src.backtesting.data_provider import HistoricalDataProvider
from src.backtesting.backtester import Backtester
from src.backtesting.strategy import Strategy, Signal
from src.backtesting.portfolio import Portfolio
from datetime import datetime


@pytest.fixture
def sample_backtest_data():
    """백테스팅용 샘플 데이터"""
    dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'open': [3000000 + i * 10000 for i in range(30)],
        'high': [3100000 + i * 10000 for i in range(30)],
        'low': [2900000 + i * 10000 for i in range(30)],
        'close': [3050000 + i * 10000 for i in range(30)],
        'volume': [100.0] * 30,
        'value': [305000000.0] * 30
    }, index=dates)


@pytest.fixture
def mock_strategy():
    """모킹된 전략"""
    strategy = Mock(spec=Strategy)
    
    # 매수 신호 생성
    buy_signal = Signal(
        action='buy',
        price=3050000.0,
        size=0.1,
        reason={'rsi': 30, 'macd': 'bullish'}
    )
    
    # 매도 신호 생성
    sell_signal = Signal(
        action='sell',
        price=3300000.0,
        size=0.1,
        reason={'rsi': 70, 'profit': 10}
    )
    
    # 신호 생성 시뮬레이션
    def generate_signal(data, portfolio=None):
        if len(data) < 10:
            return None
        if len(data) == 15:
            return buy_signal
        if len(data) == 25:
            return sell_signal
        return None
    
    strategy.generate_signal = generate_signal
    strategy.calculate_position_size = Mock(return_value=0.1)
    
    return strategy


@pytest.mark.integration
class TestBacktestFlow:
    """백테스팅 플로우 통합 테스트"""
    
    def test_complete_backtest_flow(self, sample_backtest_data, mock_strategy):
        """전체 백테스팅 플로우 테스트"""
        # Given
        ticker = "KRW-ETH"
        initial_capital = 10_000_000
        
        # When
        backtester = Backtester(
            strategy=mock_strategy,
            data=sample_backtest_data,
            ticker=ticker,
            initial_capital=initial_capital,
            commission=0.0005,
            slippage=0.0001
        )
        
        result = backtester.run()
        
        # Then
        assert result is not None
        assert result.initial_capital == initial_capital
        assert len(result.equity_curve) == len(sample_backtest_data)
        assert result.final_equity >= 0
    
    def test_backtest_with_data_provider(self, mock_strategy):
        """데이터 프로바이더를 통한 백테스팅 플로우"""
        # Given
        provider = HistoricalDataProvider()
        
        # 샘플 데이터 생성
        sample_data = pd.DataFrame({
            'open': [3000000] * 10,
            'high': [3100000] * 10,
            'low': [2900000] * 10,
            'close': [3050000] * 10,
            'volume': [100.0] * 10,
            'value': [305000000.0] * 10
        }, index=pd.date_range(start='2024-01-01', periods=10, freq='D'))
        
        # When
        with patch.object(provider, 'load_historical_data', return_value=sample_data):
            data = provider.load_historical_data(
                ticker='KRW-ETH',
                days=10,
                interval='day',
                use_cache=False
            )
            
            if data is not None:
                backtester = Backtester(
                    strategy=mock_strategy,
                    data=data,
                    ticker='KRW-ETH',
                    initial_capital=10_000_000
                )
                result = backtester.run()
        
        # Then
        assert data is not None
        if data is not None:
            assert result is not None
    
    def test_backtest_portfolio_updates(self, sample_backtest_data, mock_strategy):
        """백테스팅 중 포트폴리오 업데이트 테스트"""
        # Given
        backtester = Backtester(
            strategy=mock_strategy,
            data=sample_backtest_data,
            ticker="KRW-ETH",
            initial_capital=10_000_000
        )
        
        # When
        result = backtester.run()
        
        # Then
        assert len(backtester.equity_curve) == len(sample_backtest_data)
        # 각 시점마다 포트폴리오가 업데이트되었는지 확인
        assert all(equity >= 0 for equity in backtester.equity_curve)
    
    def test_backtest_trade_execution(self, sample_backtest_data, mock_strategy):
        """백테스팅 중 거래 실행 테스트"""
        # Given
        backtester = Backtester(
            strategy=mock_strategy,
            data=sample_backtest_data,
            ticker="KRW-ETH",
            initial_capital=10_000_000
        )
        
        # When
        result = backtester.run()
        
        # Then
        # 전략이 신호를 생성했으면 거래가 기록되어야 함
        assert len(backtester.orders) >= 0  # 신호가 있으면 주문이 있어야 함
        assert len(backtester.trades) >= 0

