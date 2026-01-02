"""
ExecuteTradeUseCase - Business logic for executing trades.

This use case handles buy/sell order execution through the exchange port,
with proper validation, fee calculation, and trade recording.
"""
from decimal import Decimal
from datetime import datetime
import re
from uuid import uuid4

from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.ports.outbound.persistence_port import PersistencePort
from src.application.dto.trading import OrderResponse
from src.domain.entities.trade import Trade, OrderSide, TradeStatus
from src.domain.value_objects.money import Money, Currency
from src.config.settings import TradingConfig


# Minimum order amount in KRW
MIN_ORDER_AMOUNT = Decimal("5000")

# Ticker format pattern
TICKER_PATTERN = re.compile(r"^KRW-[A-Z]{2,10}$")


class ExecuteTradeUseCase:
    """
    Use case for executing trading operations.

    Handles validation, execution, and recording of buy/sell orders.
    """

    def __init__(
        self,
        exchange: ExchangePort,
        persistence: PersistencePort,
    ):
        """
        Initialize with required ports.

        Args:
            exchange: Exchange port for order execution
            persistence: Persistence port for trade recording
        """
        self.exchange = exchange
        self.persistence = persistence

    async def execute_buy(
        self,
        ticker: str,
        amount: Money,
    ) -> OrderResponse:
        """
        Execute a market buy order.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")
            amount: Amount to spend in KRW

        Returns:
            OrderResponse with execution result
        """
        # Validate ticker format
        if not self._validate_ticker(ticker):
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.BUY,
                error_message=f"Invalid ticker format: {ticker}. Expected format: KRW-XXX",
            )

        # Validate positive amount
        if amount.amount <= 0:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.BUY,
                error_message="Amount must be positive",
            )

        # Validate minimum order amount
        if amount.amount < MIN_ORDER_AMOUNT:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.BUY,
                error_message=f"Amount below minimum order size ({MIN_ORDER_AMOUNT} KRW)",
            )

        # Check available balance
        balance = await self.exchange.get_balance("KRW")
        if balance.available.amount < amount.amount:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.BUY,
                error_message=f"Insufficient balance. Available: {balance.available.amount}, Required: {amount.amount}",
            )

        # Execute the order
        response = await self.exchange.execute_market_buy(ticker, amount)

        # Record trade if successful
        if response.success:
            trade = self._create_trade_from_response(response, OrderSide.BUY)
            await self.persistence.save_trade(trade)

        return response

    async def execute_sell(
        self,
        ticker: str,
        volume: Decimal,
    ) -> OrderResponse:
        """
        Execute a market sell order.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")
            volume: Volume to sell

        Returns:
            OrderResponse with execution result
        """
        # Validate ticker format
        if not self._validate_ticker(ticker):
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message=f"Invalid ticker format: {ticker}. Expected format: KRW-XXX",
            )

        # Validate positive volume
        if volume <= 0:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message="Volume must be positive",
            )

        # Check position
        position = await self.exchange.get_position(ticker)
        if position is None:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message=f"No position found for {ticker}",
            )

        if position.volume < volume:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message=f"Insufficient holdings. Available: {position.volume}, Requested: {volume}",
            )

        # Execute the order
        response = await self.exchange.execute_market_sell(ticker, volume)

        # Record trade if successful
        if response.success:
            trade = self._create_trade_from_response(response, OrderSide.SELL)
            await self.persistence.save_trade(trade)

        return response

    async def execute_sell_all(self, ticker: str) -> OrderResponse:
        """
        Sell entire position for a ticker.

        Args:
            ticker: Trading pair

        Returns:
            OrderResponse with execution result
        """
        # Validate ticker format
        if not self._validate_ticker(ticker):
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message=f"Invalid ticker format: {ticker}. Expected format: KRW-XXX",
            )

        # Get current position
        position = await self.exchange.get_position(ticker)
        if position is None or position.volume <= 0:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message=f"No position found for {ticker}",
            )

        # Sell entire position
        return await self.execute_sell(ticker, position.volume)

    def _validate_ticker(self, ticker: str) -> bool:
        """Validate ticker format."""
        return bool(TICKER_PATTERN.match(ticker))

    def _create_trade_from_response(
        self,
        response: OrderResponse,
        side: OrderSide,
    ) -> Trade:
        """Create a Trade entity from OrderResponse."""
        return Trade(
            id=uuid4(),
            ticker=response.ticker,
            side=side,
            price=response.executed_price or Money.zero(Currency.KRW),
            volume=response.executed_volume or Decimal("0"),
            fee=response.fee or Money.zero(Currency.KRW),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
            exchange_trade_id=response.order_id,
        )
