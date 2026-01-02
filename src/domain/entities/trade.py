"""
Trade, Order, and Position Domain Entities

Core business entities for trading operations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


class OrderSide(Enum):
    """Order side (buy or sell)."""
    BUY = "buy"
    SELL = "sell"

    def opposite(self) -> OrderSide:
        """Return the opposite side."""
        return OrderSide.SELL if self == OrderSide.BUY else OrderSide.BUY


class OrderType(Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        """Check if this is a terminal (final) status."""
        return self in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED,
        )


class TradeStatus(Enum):
    """Trade status."""
    COMPLETED = "completed"
    PENDING_SETTLEMENT = "pending_settlement"
    FAILED = "failed"


@dataclass(frozen=True)
class Order:
    """
    Immutable order entity representing a trading order.

    Attributes:
        id: Unique order identifier
        ticker: Trading pair (e.g., "KRW-BTC")
        side: Buy or sell
        order_type: Market or limit
        amount: Order amount in quote currency (for market buy)
        volume: Order volume in base currency (for market sell, limit orders)
        price: Limit price (for limit orders)
        status: Current order status
        created_at: Order creation time
        executed_price: Actual execution price
        executed_volume: Actual executed volume
        fee: Trading fee
        exchange_order_id: Exchange's order ID
        filled_at: When order was filled
        cancel_reason: Reason for cancellation
        error_message: Error message if failed
    """
    id: UUID
    ticker: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    created_at: datetime
    amount: Optional[Money] = None
    volume: Optional[Decimal] = None
    price: Optional[Money] = None
    executed_price: Optional[Money] = None
    executed_volume: Optional[Decimal] = None
    fee: Optional[Money] = None
    exchange_order_id: Optional[str] = None
    filled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    error_message: Optional[str] = None

    # --- Factory Methods ---

    @classmethod
    def create_market_buy(
        cls,
        ticker: str,
        amount: Money,
    ) -> Order:
        """Create a market buy order."""
        return cls(
            id=uuid4(),
            ticker=ticker,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=amount,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @classmethod
    def create_market_sell(
        cls,
        ticker: str,
        volume: Decimal,
    ) -> Order:
        """Create a market sell order."""
        return cls(
            id=uuid4(),
            ticker=ticker,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            volume=volume,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @classmethod
    def create_limit_buy(
        cls,
        ticker: str,
        price: Money,
        volume: Decimal,
    ) -> Order:
        """Create a limit buy order."""
        return cls(
            id=uuid4(),
            ticker=ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=price,
            volume=volume,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @classmethod
    def create_limit_sell(
        cls,
        ticker: str,
        price: Money,
        volume: Decimal,
    ) -> Order:
        """Create a limit sell order."""
        return cls(
            id=uuid4(),
            ticker=ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=price,
            volume=volume,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    # --- State Transitions ---

    def fill(
        self,
        executed_price: Money,
        executed_volume: Decimal,
        fee: Money,
        exchange_order_id: Optional[str] = None,
    ) -> Order:
        """Return a new Order with filled status."""
        if self.status.is_terminal():
            raise ValueError(
                f"Cannot fill order in terminal status: {self.status.value}"
            )

        return Order(
            id=self.id,
            ticker=self.ticker,
            side=self.side,
            order_type=self.order_type,
            amount=self.amount,
            volume=self.volume,
            price=self.price,
            status=OrderStatus.FILLED,
            created_at=self.created_at,
            executed_price=executed_price,
            executed_volume=executed_volume,
            fee=fee,
            exchange_order_id=exchange_order_id or self.exchange_order_id,
            filled_at=datetime.now(),
        )

    def cancel(self, reason: Optional[str] = None) -> Order:
        """Return a new Order with cancelled status."""
        if self.status.is_terminal():
            raise ValueError(
                f"Cannot cancel order in terminal status: {self.status.value}"
            )

        return Order(
            id=self.id,
            ticker=self.ticker,
            side=self.side,
            order_type=self.order_type,
            amount=self.amount,
            volume=self.volume,
            price=self.price,
            status=OrderStatus.CANCELLED,
            created_at=self.created_at,
            cancel_reason=reason,
        )

    def fail(self, error: str) -> Order:
        """Return a new Order with failed status."""
        return Order(
            id=self.id,
            ticker=self.ticker,
            side=self.side,
            order_type=self.order_type,
            amount=self.amount,
            volume=self.volume,
            price=self.price,
            status=OrderStatus.FAILED,
            created_at=self.created_at,
            error_message=error,
        )

    # --- Computed Properties ---

    @property
    def executed_total(self) -> Optional[Money]:
        """Calculate executed total (price * volume)."""
        if self.executed_price is None or self.executed_volume is None:
            return None
        return self.executed_price * self.executed_volume

    @property
    def total_cost(self) -> Optional[Money]:
        """Calculate total cost including fee (for buy orders)."""
        if self.executed_total is None or self.fee is None:
            return None
        return self.executed_total + self.fee


@dataclass(frozen=True)
class Trade:
    """
    Immutable trade entity representing a completed transaction.

    Attributes:
        id: Unique trade identifier
        ticker: Trading pair
        side: Buy or sell
        price: Execution price
        volume: Traded volume
        fee: Trading fee
        status: Trade status
        executed_at: Execution timestamp
        exchange_trade_id: Exchange's trade ID
        order_id: Related order ID
    """
    id: UUID
    ticker: str
    side: OrderSide
    price: Money
    volume: Decimal
    fee: Money
    status: TradeStatus
    executed_at: datetime
    exchange_trade_id: Optional[str] = None
    order_id: Optional[UUID] = None

    # --- Factory Methods ---

    @classmethod
    def create(
        cls,
        ticker: str,
        side: OrderSide,
        price: Money,
        volume: Decimal,
        fee: Money,
        exchange_trade_id: Optional[str] = None,
    ) -> Trade:
        """Create a new trade."""
        return cls(
            id=uuid4(),
            ticker=ticker,
            side=side,
            price=price,
            volume=volume,
            fee=fee,
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
            exchange_trade_id=exchange_trade_id,
        )

    @classmethod
    def from_order(cls, order: Order) -> Trade:
        """Create a Trade from a filled Order."""
        if order.status != OrderStatus.FILLED:
            raise ValueError("Can only create Trade from filled Order")

        if order.executed_price is None or order.executed_volume is None:
            raise ValueError("Filled order must have execution details")

        return cls(
            id=uuid4(),
            ticker=order.ticker,
            side=order.side,
            price=order.executed_price,
            volume=order.executed_volume,
            fee=order.fee or Money.zero(order.executed_price.currency),
            status=TradeStatus.COMPLETED,
            executed_at=order.filled_at or datetime.now(),
            exchange_trade_id=order.exchange_order_id,
            order_id=order.id,
        )

    # --- Computed Properties ---

    @property
    def total_amount(self) -> Money:
        """Calculate total amount (price * volume)."""
        return self.price * self.volume

    @property
    def total_cost(self) -> Money:
        """Calculate total cost including fee (for buy trades)."""
        return self.total_amount + self.fee

    @property
    def net_amount(self) -> Money:
        """Calculate net amount after fee (for sell trades)."""
        return self.total_amount - self.fee


@dataclass(frozen=True)
class Position:
    """
    Immutable position entity representing a current holding.

    Attributes:
        id: Unique position identifier
        ticker: Trading pair (e.g., "KRW-BTC")
        symbol: Base currency symbol (e.g., "BTC")
        volume: Current holding volume
        avg_entry_price: Average entry price
        entry_time: When position was opened
        closed_at: When position was closed (if closed)
    """
    id: UUID
    ticker: str
    symbol: str
    volume: Decimal
    avg_entry_price: Money
    entry_time: datetime
    closed_at: Optional[datetime] = None

    # --- Factory Methods ---

    @classmethod
    def create(
        cls,
        ticker: str,
        symbol: str,
        volume: Decimal,
        avg_entry_price: Money,
        entry_time: Optional[datetime] = None,
    ) -> Position:
        """Create a new position."""
        return cls(
            id=uuid4(),
            ticker=ticker,
            symbol=symbol,
            volume=Decimal(str(volume)),
            avg_entry_price=avg_entry_price,
            entry_time=entry_time or datetime.now(),
        )

    @classmethod
    def empty(cls, ticker: str, symbol: str) -> Position:
        """Create an empty position."""
        return cls(
            id=uuid4(),
            ticker=ticker,
            symbol=symbol,
            volume=Decimal("0"),
            avg_entry_price=Money.zero(Currency.KRW),
            entry_time=datetime.now(),
        )

    # --- Computed Properties ---

    @property
    def total_cost(self) -> Money:
        """Calculate total cost (avg_price * volume)."""
        return self.avg_entry_price * self.volume

    def current_value(self, current_price: Money) -> Money:
        """Calculate current value at given price."""
        return current_price * self.volume

    def profit_loss(self, current_price: Money) -> Money:
        """Calculate unrealized P&L."""
        return self.current_value(current_price) - self.total_cost

    def profit_rate(self, current_price: Money) -> Percentage:
        """Calculate profit rate as percentage."""
        if self.avg_entry_price.is_zero():
            return Percentage.zero()

        rate = (
            (current_price.amount - self.avg_entry_price.amount)
            / self.avg_entry_price.amount
        )
        return Percentage(rate)

    def holding_duration(self) -> timedelta:
        """Calculate holding duration."""
        end_time = self.closed_at or datetime.now()
        return end_time - self.entry_time

    def holding_hours(self) -> float:
        """Calculate holding duration in hours."""
        return self.holding_duration().total_seconds() / 3600

    # --- State Checks ---

    def is_empty(self) -> bool:
        """Check if position is empty (no holdings)."""
        return self.volume == Decimal("0")

    def is_profitable(self, current_price: Money) -> bool:
        """Check if position is profitable."""
        return current_price.amount > self.avg_entry_price.amount

    def is_at_loss(self, current_price: Money) -> bool:
        """Check if position is at loss."""
        return current_price.amount < self.avg_entry_price.amount

    def should_stop_loss(
        self,
        current_price: Money,
        stop_loss_pct: Percentage,
    ) -> bool:
        """Check if stop loss should be triggered."""
        rate = self.profit_rate(current_price)
        return rate.value <= stop_loss_pct.value

    def should_take_profit(
        self,
        current_price: Money,
        take_profit_pct: Percentage,
    ) -> bool:
        """Check if take profit should be triggered."""
        rate = self.profit_rate(current_price)
        return rate.value >= take_profit_pct.value

    # --- Position Updates ---

    def add(self, volume: Decimal, price: Money) -> Position:
        """Add volume to position (averaging up/down)."""
        volume = Decimal(str(volume))

        # Calculate new average price
        total_cost = self.total_cost + (price * volume)
        new_volume = self.volume + volume
        new_avg_price = Money(
            total_cost.amount / new_volume,
            self.avg_entry_price.currency,
        )

        return Position(
            id=self.id,
            ticker=self.ticker,
            symbol=self.symbol,
            volume=new_volume,
            avg_entry_price=new_avg_price,
            entry_time=self.entry_time,
        )

    def reduce(self, volume: Decimal) -> Position:
        """Reduce volume from position."""
        volume = Decimal(str(volume))

        if volume > self.volume:
            raise ValueError(
                f"Cannot reduce by {volume}, only {self.volume} available. "
                f"Reduction would exceed position size."
            )

        new_volume = self.volume - volume

        return Position(
            id=self.id,
            ticker=self.ticker,
            symbol=self.symbol,
            volume=new_volume,
            avg_entry_price=self.avg_entry_price,
            entry_time=self.entry_time,
            closed_at=datetime.now() if new_volume == 0 else None,
        )

    def close(self) -> Position:
        """Close position completely."""
        return Position(
            id=self.id,
            ticker=self.ticker,
            symbol=self.symbol,
            volume=Decimal("0"),
            avg_entry_price=self.avg_entry_price,
            entry_time=self.entry_time,
            closed_at=datetime.now(),
        )
