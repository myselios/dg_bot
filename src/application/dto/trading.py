"""
Trading DTOs for order execution and position management.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from src.domain.entities.trade import OrderSide, OrderType, OrderStatus
from src.domain.value_objects.money import Money, Currency


@dataclass(frozen=True)
class OrderRequest:
    """
    Request to execute an order.

    Attributes:
        ticker: Trading pair (e.g., "KRW-BTC")
        side: Buy or sell
        order_type: Market or limit
        amount: Amount in quote currency (for market buy)
        volume: Volume in base currency (for market sell, limit)
        price: Limit price (for limit orders)
    """
    ticker: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    amount: Optional[Money] = None
    volume: Optional[Decimal] = None
    price: Optional[Money] = None

    def __post_init__(self) -> None:
        """Validate order request."""
        if self.side == OrderSide.BUY and self.order_type == OrderType.MARKET:
            if self.amount is None:
                raise ValueError("Market buy order requires amount")
        elif self.side == OrderSide.SELL and self.order_type == OrderType.MARKET:
            if self.volume is None:
                raise ValueError("Market sell order requires volume")
        elif self.order_type == OrderType.LIMIT:
            if self.price is None or self.volume is None:
                raise ValueError("Limit order requires price and volume")

    @classmethod
    def market_buy(cls, ticker: str, amount: Money) -> OrderRequest:
        """Create market buy order request."""
        return cls(
            ticker=ticker,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=amount,
        )

    @classmethod
    def market_sell(cls, ticker: str, volume: Decimal) -> OrderRequest:
        """Create market sell order request."""
        return cls(
            ticker=ticker,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            volume=volume,
        )

    @classmethod
    def limit_buy(
        cls,
        ticker: str,
        price: Money,
        volume: Decimal,
    ) -> OrderRequest:
        """Create limit buy order request."""
        return cls(
            ticker=ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=price,
            volume=volume,
        )

    @classmethod
    def limit_sell(
        cls,
        ticker: str,
        price: Money,
        volume: Decimal,
    ) -> OrderRequest:
        """Create limit sell order request."""
        return cls(
            ticker=ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=price,
            volume=volume,
        )


@dataclass(frozen=True)
class OrderResponse:
    """
    Response from order execution.

    Attributes:
        success: Whether the order was successful
        order_id: Exchange order ID
        ticker: Trading pair
        side: Buy or sell
        status: Order status
        executed_price: Actual execution price
        executed_volume: Actual executed volume
        fee: Trading fee
        total_amount: Total amount (price * volume)
        error_message: Error message if failed
        raw_response: Raw exchange response
        executed_at: Execution timestamp
    """
    success: bool
    ticker: str
    side: OrderSide
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    executed_price: Optional[Money] = None
    executed_volume: Optional[Decimal] = None
    fee: Optional[Money] = None
    total_amount: Optional[Money] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    executed_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def success_response(
        cls,
        ticker: str,
        side: OrderSide,
        order_id: str,
        executed_price: Money,
        executed_volume: Decimal,
        fee: Money,
    ) -> OrderResponse:
        """Create successful order response."""
        total = executed_price * executed_volume
        return cls(
            success=True,
            ticker=ticker,
            side=side,
            order_id=order_id,
            status=OrderStatus.FILLED,
            executed_price=executed_price,
            executed_volume=executed_volume,
            fee=fee,
            total_amount=total,
        )

    @classmethod
    def failure_response(
        cls,
        ticker: str,
        side: OrderSide,
        error_message: str,
    ) -> OrderResponse:
        """Create failed order response."""
        return cls(
            success=False,
            ticker=ticker,
            side=side,
            status=OrderStatus.FAILED,
            error_message=error_message,
        )


@dataclass(frozen=True)
class BalanceInfo:
    """
    Account balance information.

    Attributes:
        currency: Currency code (e.g., "KRW", "BTC")
        total: Total balance
        available: Available balance (not locked)
        locked: Locked balance (in orders)
    """
    currency: str
    total: Money
    available: Money
    locked: Money

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BalanceInfo:
        """Create from dictionary."""
        currency_str = data.get("currency", "KRW")
        try:
            currency_enum = Currency[currency_str]
        except KeyError:
            currency_enum = Currency.KRW

        return cls(
            currency=currency_str,
            total=Money(Decimal(str(data.get("total", 0))), currency_enum),
            available=Money(Decimal(str(data.get("available", 0))), currency_enum),
            locked=Money(Decimal(str(data.get("locked", 0))), currency_enum),
        )


@dataclass(frozen=True)
class PositionInfo:
    """
    Current position information.

    Attributes:
        ticker: Trading pair
        symbol: Base currency symbol
        volume: Current holding volume
        avg_buy_price: Average buy price
        current_price: Current market price
        profit_loss: Unrealized P&L
        profit_rate: Profit rate as percentage
        total_cost: Total cost of position
        current_value: Current market value
    """
    ticker: str
    symbol: str
    volume: Decimal
    avg_buy_price: Money
    current_price: Money
    profit_loss: Money
    profit_rate: Decimal
    total_cost: Money
    current_value: Money

    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.profit_loss.amount > Decimal("0")

    def is_empty(self) -> bool:
        """Check if position is empty."""
        return self.volume == Decimal("0")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PositionInfo:
        """Create from dictionary."""
        volume = Decimal(str(data.get("volume", 0)))
        avg_price = Decimal(str(data.get("avg_buy_price", 0)))
        current_price = Decimal(str(data.get("current_price", 0)))

        total_cost = avg_price * volume
        current_value = current_price * volume
        profit_loss = current_value - total_cost
        profit_rate = (
            ((current_price - avg_price) / avg_price * 100)
            if avg_price > 0
            else Decimal("0")
        )

        return cls(
            ticker=data.get("ticker", ""),
            symbol=data.get("symbol", ""),
            volume=volume,
            avg_buy_price=Money.krw(avg_price),
            current_price=Money.krw(current_price),
            profit_loss=Money.krw(profit_loss),
            profit_rate=profit_rate,
            total_cost=Money.krw(total_cost),
            current_value=Money.krw(current_value),
        )
