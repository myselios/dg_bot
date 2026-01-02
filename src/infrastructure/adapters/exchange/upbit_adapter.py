"""
UpbitExchangeAdapter - Upbit exchange implementation of ExchangePort.

This adapter wraps the existing UpbitClient to implement the ExchangePort interface.
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any
import pyupbit

from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.dto.trading import (
    OrderRequest,
    OrderResponse,
    BalanceInfo,
    PositionInfo,
)
from src.domain.entities.trade import OrderSide, OrderStatus
from src.domain.value_objects.money import Money, Currency
from src.config.settings import APIConfig, TradingConfig


class UpbitExchangeAdapter(ExchangePort):
    """
    Upbit exchange adapter implementing ExchangePort.

    Wraps pyupbit library for Upbit API communication.
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Initialize Upbit adapter.

        Args:
            access_key: Upbit API access key (uses config if not provided)
            secret_key: Upbit API secret key (uses config if not provided)
        """
        self._access_key = access_key or APIConfig.UPBIT_ACCESS_KEY
        self._secret_key = secret_key or APIConfig.UPBIT_SECRET_KEY
        self._client: Optional[pyupbit.Upbit] = None

    @property
    def client(self) -> pyupbit.Upbit:
        """Lazy initialization of Upbit client."""
        if self._client is None:
            self._client = pyupbit.Upbit(self._access_key, self._secret_key)
        return self._client

    # --- Balance Operations ---

    async def get_balance(self, currency: str) -> BalanceInfo:
        """Get balance for a specific currency."""
        try:
            balance = self.client.get_balance(currency)
            locked = self.client.get_balance(currency + "_LOCKED") or 0

            total = Decimal(str(balance or 0)) + Decimal(str(locked))

            # Determine currency enum
            try:
                currency_enum = Currency[currency]
            except KeyError:
                currency_enum = Currency.KRW

            return BalanceInfo(
                currency=currency,
                total=Money(total, currency_enum),
                available=Money(Decimal(str(balance or 0)), currency_enum),
                locked=Money(Decimal(str(locked)), currency_enum),
            )
        except Exception as e:
            # Return zero balance on error
            return BalanceInfo(
                currency=currency,
                total=Money.zero(Currency.KRW),
                available=Money.zero(Currency.KRW),
                locked=Money.zero(Currency.KRW),
            )

    async def get_all_balances(self) -> List[BalanceInfo]:
        """Get all non-zero balances."""
        try:
            balances = self.client.get_balances()
            result = []

            for bal in balances or []:
                currency = bal.get("currency", "")
                total = Decimal(str(bal.get("balance", 0)))
                locked = Decimal(str(bal.get("locked", 0)))

                if total > 0 or locked > 0:
                    try:
                        currency_enum = Currency[currency]
                    except KeyError:
                        currency_enum = Currency.KRW

                    result.append(BalanceInfo(
                        currency=currency,
                        total=Money(total + locked, currency_enum),
                        available=Money(total, currency_enum),
                        locked=Money(locked, currency_enum),
                    ))

            return result
        except Exception:
            return []

    # --- Order Operations ---

    async def execute_order(self, request: OrderRequest) -> OrderResponse:
        """Execute a trading order."""
        if request.side == OrderSide.BUY:
            if request.amount:
                return await self.execute_market_buy(request.ticker, request.amount)
        else:
            if request.volume:
                return await self.execute_market_sell(request.ticker, request.volume)

        return OrderResponse.failure_response(
            ticker=request.ticker,
            side=request.side,
            error_message="Invalid order request",
        )

    async def execute_market_buy(
        self,
        ticker: str,
        amount: Money,
    ) -> OrderResponse:
        """Execute a market buy order."""
        try:
            result = self.client.buy_market_order(ticker, float(amount.amount))

            if result is None:
                return OrderResponse.failure_response(
                    ticker=ticker,
                    side=OrderSide.BUY,
                    error_message="Order returned None",
                )

            # Parse response
            order_id = result.get("uuid", "")
            executed_volume = Decimal(str(result.get("volume", 0)))
            executed_price = Decimal(str(result.get("price", 0)))

            # Calculate fee
            fee_amount = amount.amount * Decimal(str(TradingConfig.FEE_RATE))

            return OrderResponse.success_response(
                ticker=ticker,
                side=OrderSide.BUY,
                order_id=order_id,
                executed_price=Money.krw(executed_price) if executed_price > 0 else amount,
                executed_volume=executed_volume,
                fee=Money.krw(fee_amount),
            )
        except Exception as e:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.BUY,
                error_message=str(e),
            )

    async def execute_market_sell(
        self,
        ticker: str,
        volume: Decimal,
    ) -> OrderResponse:
        """Execute a market sell order."""
        try:
            result = self.client.sell_market_order(ticker, float(volume))

            if result is None:
                return OrderResponse.failure_response(
                    ticker=ticker,
                    side=OrderSide.SELL,
                    error_message="Order returned None",
                )

            order_id = result.get("uuid", "")
            executed_price_str = result.get("price", "0")
            executed_price = Decimal(str(executed_price_str)) if executed_price_str else Decimal("0")

            # Get current price if not in result
            if executed_price == 0:
                current = await self.get_current_price(ticker)
                executed_price = current.amount

            total = executed_price * volume
            fee_amount = total * Decimal(str(TradingConfig.FEE_RATE))

            return OrderResponse.success_response(
                ticker=ticker,
                side=OrderSide.SELL,
                order_id=order_id,
                executed_price=Money.krw(executed_price),
                executed_volume=volume,
                fee=Money.krw(fee_amount),
            )
        except Exception as e:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message=str(e),
            )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            result = self.client.cancel_order(order_id)
            return result is not None
        except Exception:
            return False

    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get current status of an order."""
        try:
            result = self.client.get_order(order_id)

            if result is None:
                return OrderResponse.failure_response(
                    ticker="",
                    side=OrderSide.BUY,
                    error_message="Order not found",
                )

            # Parse status
            state = result.get("state", "")
            status_map = {
                "done": OrderStatus.FILLED,
                "cancel": OrderStatus.CANCELLED,
                "wait": OrderStatus.PENDING,
            }
            status = status_map.get(state, OrderStatus.PENDING)

            side = OrderSide.BUY if result.get("side") == "bid" else OrderSide.SELL

            return OrderResponse(
                success=status == OrderStatus.FILLED,
                ticker=result.get("market", ""),
                side=side,
                order_id=order_id,
                status=status,
            )
        except Exception as e:
            return OrderResponse.failure_response(
                ticker="",
                side=OrderSide.BUY,
                error_message=str(e),
            )

    # --- Position Operations ---

    async def get_position(self, ticker: str) -> Optional[PositionInfo]:
        """Get current position for a ticker."""
        try:
            # Extract symbol from ticker (e.g., "KRW-BTC" -> "BTC")
            symbol = ticker.split("-")[-1] if "-" in ticker else ticker

            balance = self.client.get_balance(symbol)
            avg_price = self.client.get_avg_buy_price(symbol)

            if not balance or float(balance) == 0:
                return None

            volume = Decimal(str(balance))
            avg_buy_price = Decimal(str(avg_price or 0))
            current_price = await self.get_current_price(ticker)

            total_cost = avg_buy_price * volume
            current_value = current_price.amount * volume
            profit_loss = current_value - total_cost
            profit_rate = (
                ((current_price.amount - avg_buy_price) / avg_buy_price * 100)
                if avg_buy_price > 0
                else Decimal("0")
            )

            return PositionInfo(
                ticker=ticker,
                symbol=symbol,
                volume=volume,
                avg_buy_price=Money.krw(avg_buy_price),
                current_price=current_price,
                profit_loss=Money.krw(profit_loss),
                profit_rate=profit_rate,
                total_cost=Money.krw(total_cost),
                current_value=Money.krw(current_value),
            )
        except Exception:
            return None

    async def get_all_positions(self) -> List[PositionInfo]:
        """Get all open positions."""
        positions = []
        balances = await self.get_all_balances()

        for balance in balances:
            if balance.currency == "KRW":
                continue

            ticker = f"KRW-{balance.currency}"
            position = await self.get_position(ticker)
            if position and not position.is_empty():
                positions.append(position)

        return positions

    # --- Market Data ---

    async def get_current_price(self, ticker: str) -> Money:
        """Get current market price for a ticker."""
        try:
            price = pyupbit.get_current_price(ticker)
            return Money.krw(Decimal(str(price or 0)))
        except Exception:
            return Money.zero(Currency.KRW)

    async def get_orderbook(self, ticker: str) -> dict:
        """Get current orderbook for a ticker."""
        try:
            orderbook = pyupbit.get_orderbook(ticker)
            if orderbook and len(orderbook) > 0:
                return orderbook[0]
            return {"bids": [], "asks": []}
        except Exception:
            return {"bids": [], "asks": []}

    # --- Utility ---

    async def is_market_open(self, ticker: str) -> bool:
        """Check if market is open for trading."""
        try:
            price = pyupbit.get_current_price(ticker)
            return price is not None and price > 0
        except Exception:
            return False

    async def get_min_order_amount(self, ticker: str) -> Money:
        """Get minimum order amount for a ticker."""
        return Money.krw(TradingConfig.MIN_ORDER_AMOUNT)
