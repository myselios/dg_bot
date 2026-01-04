"""
포트폴리오 관리 클래스
"""
from datetime import datetime
from typing import Dict, Optional
import pandas as pd
from ..exceptions import InsufficientFundsError


class Position:
    """개별 포지션"""

    def __init__(
        self,
        symbol: str,
        size: float,
        entry_price: float,
        entry_time: datetime,
        commission: float
    ):
        self.symbol = symbol
        self.size = size
        self.entry_price = entry_price
        self.entry_time = entry_time  # 백테스트 시 bar timestamp 사용
        self.commission = commission
        self.current_price = entry_price
        
    @property
    def current_value(self) -> float:
        """현재 가치"""
        return self.size * self.current_price
    
    @property
    def unrealized_pnl(self) -> float:
        """미실현 손익"""
        return (self.current_price - self.entry_price) * self.size
    
    @property
    def unrealized_pnl_percent(self) -> float:
        """미실현 손익률"""
        return ((self.current_price - self.entry_price) / self.entry_price) * 100
    
    def update_price(self, price: float):
        """가격 업데이트"""
        self.current_price = price


class Trade:
    """완료된 거래"""
    
    def __init__(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        size: float,
        entry_time: datetime,
        exit_time: datetime,
        pnl: float,
        pnl_percent: float,
        commission: float
    ):
        self.symbol = symbol
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.size = size
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.pnl = pnl
        self.pnl_percent = pnl_percent
        self.commission = commission
        self.holding_period = exit_time - entry_time


class Portfolio:
    """포트폴리오 관리 클래스"""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}  # {symbol: Position}
        self.closed_trades: list[Trade] = []
        
    @property
    def total_value(self) -> float:
        """총 자산 가치"""
        position_value = sum(
            pos.current_value for pos in self.positions.values()
        )
        return self.cash + position_value
    
    @property
    def equity(self) -> float:
        """순자산"""
        return self.total_value
    
    def open_position(
        self,
        symbol: str,
        size: float,
        price: float,
        commission: float,
        slippage: float,
        timestamp: Optional[datetime] = None
    ) -> Position:
        """
        포지션 오픈

        Args:
            symbol: 거래 종목
            size: 포지션 크기
            price: 체결 가격
            commission: 수수료율
            slippage: 슬리피지율
            timestamp: 진입 시점 (백테스트 시 bar timestamp 사용, None이면 현재 시간)
        """
        # 실제 체결 가격 (슬리피지 포함)
        execution_price = price * (1 + slippage)

        # 총 비용
        cost = size * execution_price
        commission_cost = cost * commission
        total_cost = cost + commission_cost

        if total_cost > self.cash:
            raise InsufficientFundsError(
                required=total_cost,
                available=self.cash,
                currency="KRW"
            )

        # 포지션 생성 (timestamp가 없으면 현재 시간 사용)
        entry_time = timestamp if timestamp is not None else datetime.now()
        position = Position(
            symbol=symbol,
            size=size,
            entry_price=execution_price,
            entry_time=entry_time,
            commission=commission_cost
        )

        self.positions[symbol] = position
        self.cash -= total_cost

        return position
    
    def close_position(
        self,
        symbol: str,
        price: float,
        commission: float,
        slippage: float,
        timestamp: Optional[datetime] = None
    ) -> Optional[Trade]:
        """
        포지션 청산

        Args:
            symbol: 거래 종목
            price: 청산 가격
            commission: 수수료율
            slippage: 슬리피지율
            timestamp: 청산 시점 (백테스트 시 bar timestamp 사용, None이면 현재 시간)
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        # 실제 체결 가격
        execution_price = price * (1 - slippage)

        # 수익 계산
        proceeds = position.size * execution_price
        commission_cost = proceeds * commission
        net_proceeds = proceeds - commission_cost

        # 청산 시간 (timestamp가 없으면 현재 시간 사용)
        exit_time = timestamp if timestamp is not None else datetime.now()

        # 거래 기록
        trade = Trade(
            symbol=symbol,
            entry_price=position.entry_price,
            exit_price=execution_price,
            size=position.size,
            entry_time=position.entry_time,
            exit_time=exit_time,
            pnl=net_proceeds - (position.size * position.entry_price + position.commission),
            pnl_percent=((execution_price - position.entry_price) / position.entry_price) * 100,
            commission=position.commission + commission_cost
        )

        self.closed_trades.append(trade)
        self.cash += net_proceeds
        del self.positions[symbol]

        return trade
    
    def update(self, current_bar: pd.Series):
        """포트폴리오 업데이트 (미실현 손익)"""
        current_price = current_bar['close']
        for position in self.positions.values():
            position.update_price(current_price)

