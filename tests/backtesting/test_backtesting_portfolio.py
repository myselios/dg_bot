"""
백테스팅 포트폴리오 테스트
"""
import pytest
import pandas as pd
from datetime import datetime
from src.backtesting.portfolio import (
    Portfolio, Position, Trade, InsufficientFundsError
)


class TestPosition:
    """Position 클래스 테스트"""
    
    @pytest.mark.unit
    def test_position_creation(self):
        """포지션 생성 테스트"""
        # Given
        symbol = 'KRW-BTC'
        size = 1.0
        entry_price = 100.0
        entry_time = datetime.now()
        commission = 5.0
        
        # When
        position = Position(
            symbol=symbol,
            size=size,
            entry_price=entry_price,
            entry_time=entry_time,
            commission=commission
        )
        
        # Then
        assert position.symbol == symbol
        assert position.size == size
        assert position.entry_price == entry_price
        assert position.entry_time == entry_time
        assert position.commission == commission
        assert position.current_price == entry_price
    
    @pytest.mark.unit
    def test_position_current_value(self):
        """포지션 현재 가치 계산 테스트"""
        # Given
        position = Position(
            symbol='KRW-BTC',
            size=2.0,
            entry_price=100.0,
            entry_time=datetime.now(),
            commission=5.0
        )
        position.update_price(110.0)
        
        # When
        value = position.current_value
        
        # Then
        assert value == 220.0  # 2.0 * 110.0
    
    @pytest.mark.unit
    def test_position_unrealized_pnl(self):
        """미실현 손익 계산 테스트"""
        # Given
        position = Position(
            symbol='KRW-BTC',
            size=1.0,
            entry_price=100.0,
            entry_time=datetime.now(),
            commission=5.0
        )
        position.update_price(110.0)
        
        # When
        pnl = position.unrealized_pnl
        pnl_percent = position.unrealized_pnl_percent
        
        # Then
        assert pnl == 10.0  # (110 - 100) * 1.0
        assert pnl_percent == 10.0  # ((110 - 100) / 100) * 100
    
    @pytest.mark.unit
    def test_position_update_price(self):
        """가격 업데이트 테스트"""
        # Given
        position = Position(
            symbol='KRW-BTC',
            size=1.0,
            entry_price=100.0,
            entry_time=datetime.now(),
            commission=5.0
        )
        
        # When
        position.update_price(120.0)
        
        # Then
        assert position.current_price == 120.0


class TestTrade:
    """Trade 클래스 테스트"""
    
    @pytest.mark.unit
    def test_trade_creation(self):
        """거래 생성 테스트"""
        # Given
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        exit_time = datetime(2024, 1, 1, 12, 0, 0)
        
        # When
        trade = Trade(
            symbol='KRW-BTC',
            entry_price=100.0,
            exit_price=110.0,
            size=1.0,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=10.0,
            pnl_percent=10.0,
            commission=5.0
        )
        
        # Then
        assert trade.symbol == 'KRW-BTC'
        assert trade.entry_price == 100.0
        assert trade.exit_price == 110.0
        assert trade.size == 1.0
        assert trade.pnl == 10.0
        assert trade.pnl_percent == 10.0
        assert trade.commission == 5.0
        assert trade.holding_period.total_seconds() == 7200  # 2시간


class TestPortfolio:
    """Portfolio 클래스 테스트"""
    
    @pytest.mark.unit
    def test_portfolio_initialization(self):
        """포트폴리오 초기화 테스트"""
        # Given
        initial_capital = 10000.0
        
        # When
        portfolio = Portfolio(initial_capital)
        
        # Then
        assert portfolio.initial_capital == initial_capital
        assert portfolio.cash == initial_capital
        assert len(portfolio.positions) == 0
        assert len(portfolio.closed_trades) == 0
        assert portfolio.total_value == initial_capital
        assert portfolio.equity == initial_capital
    
    @pytest.mark.unit
    def test_portfolio_open_position(self):
        """포지션 오픈 테스트"""
        # Given
        portfolio = Portfolio(initial_capital=10000.0)
        symbol = 'KRW-BTC'
        size = 1.0
        price = 100.0
        commission = 0.0005
        slippage = 0.0001
        
        # When
        position = portfolio.open_position(
            symbol=symbol,
            size=size,
            price=price,
            commission=commission,
            slippage=slippage
        )
        
        # Then
        assert symbol in portfolio.positions
        assert portfolio.positions[symbol] == position
        assert position.size == size
        # 슬리피지가 적용된 가격
        expected_price = price * (1 + slippage)
        assert position.entry_price == expected_price
        # 현금이 차감되었는지 확인
        expected_cost = size * expected_price * (1 + commission)
        assert portfolio.cash < portfolio.initial_capital
    
    @pytest.mark.unit
    def test_portfolio_open_position_insufficient_funds(self):
        """자금 부족 시 예외 발생 테스트"""
        # Given
        portfolio = Portfolio(initial_capital=100.0)
        symbol = 'KRW-BTC'
        size = 10.0  # 너무 큰 포지션
        price = 100.0
        commission = 0.0005
        slippage = 0.0001
        
        # When & Then
        with pytest.raises(InsufficientFundsError):
            portfolio.open_position(
                symbol=symbol,
                size=size,
                price=price,
                commission=commission,
                slippage=slippage
            )
    
    @pytest.mark.unit
    def test_portfolio_close_position(self):
        """포지션 청산 테스트"""
        # Given
        portfolio = Portfolio(initial_capital=10000.0)
        symbol = 'KRW-BTC'
        size = 1.0
        entry_price = 100.0
        exit_price = 110.0
        commission = 0.0005
        slippage = 0.0001
        
        # 포지션 오픈
        portfolio.open_position(
            symbol=symbol,
            size=size,
            price=entry_price,
            commission=commission,
            slippage=slippage
        )
        initial_cash = portfolio.cash
        
        # When
        trade = portfolio.close_position(
            symbol=symbol,
            price=exit_price,
            commission=commission,
            slippage=slippage
        )
        
        # Then
        assert trade is not None
        assert symbol not in portfolio.positions
        assert len(portfolio.closed_trades) == 1
        assert portfolio.closed_trades[0] == trade
        assert portfolio.cash > initial_cash  # 현금이 증가했어야 함
    
    @pytest.mark.unit
    def test_portfolio_close_nonexistent_position(self):
        """존재하지 않는 포지션 청산 테스트"""
        # Given
        portfolio = Portfolio(initial_capital=10000.0)
        
        # When
        trade = portfolio.close_position(
            symbol='KRW-BTC',
            price=100.0,
            commission=0.0005,
            slippage=0.0001
        )
        
        # Then
        assert trade is None
    
    @pytest.mark.unit
    def test_portfolio_update(self):
        """포트폴리오 업데이트 테스트"""
        # Given
        portfolio = Portfolio(initial_capital=10000.0)
        symbol = 'KRW-BTC'
        
        # 포지션 오픈
        portfolio.open_position(
            symbol=symbol,
            size=1.0,
            price=100.0,
            commission=0.0005,
            slippage=0.0001
        )
        
        # When
        current_bar = pd.Series({
            'open': 105.0,
            'high': 110.0,
            'low': 100.0,
            'close': 110.0,
            'volume': 1000.0
        })
        portfolio.update(current_bar)
        
        # Then
        position = portfolio.positions[symbol]
        assert position.current_price == 110.0
        assert position.unrealized_pnl > 0
    
    @pytest.mark.unit
    def test_portfolio_total_value_with_position(self):
        """포지션이 있을 때 총 자산 가치 계산 테스트"""
        # Given
        portfolio = Portfolio(initial_capital=10000.0)
        
        # 포지션 오픈
        portfolio.open_position(
            symbol='KRW-BTC',
            size=1.0,
            price=100.0,
            commission=0.0005,
            slippage=0.0001
        )
        
        # 가격 업데이트
        current_bar = pd.Series({
            'open': 100.0,
            'high': 110.0,
            'low': 95.0,
            'close': 110.0,
            'volume': 1000.0
        })
        portfolio.update(current_bar)
        
        # When
        total_value = portfolio.total_value
        
        # Then
        # 현금 + 포지션 가치
        assert total_value > portfolio.cash
        assert total_value == portfolio.equity




