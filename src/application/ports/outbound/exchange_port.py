"""
ExchangePort - Interface for exchange operations.

This port defines the contract for interacting with cryptocurrency exchanges.
Adapters implementing this interface handle the actual API communication.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

from src.domain.entities.trade import Order
from src.domain.value_objects.money import Money
from src.application.dto.trading import (
    OrderRequest,
    OrderResponse,
    BalanceInfo,
    PositionInfo,
)


class ExchangePort(ABC):
    """
    Port interface for exchange operations.

    This interface defines all operations that can be performed on a
    cryptocurrency exchange. Implementations (adapters) will handle
    the specifics of each exchange's API.
    """

    # --- Balance Operations ---

    @abstractmethod
    async def get_balance(self, currency: str) -> BalanceInfo:
        """
        Get balance for a specific currency.

        Args:
            currency: Currency code (e.g., "KRW", "BTC")

        Returns:
            BalanceInfo with total, available, and locked amounts

        Raises:
            ExchangeError: If API call fails
        """
        pass

    @abstractmethod
    async def get_all_balances(self) -> List[BalanceInfo]:
        """
        Get all non-zero balances.

        Returns:
            List of BalanceInfo for all currencies with balance

        Raises:
            ExchangeError: If API call fails
        """
        pass

    # --- Order Operations ---

    @abstractmethod
    async def execute_order(self, request: OrderRequest) -> OrderResponse:
        """
        Execute a trading order.

        Args:
            request: Order request with all necessary details

        Returns:
            OrderResponse with execution result

        Raises:
            ExchangeError: If order execution fails
            InsufficientFundsError: If balance is insufficient
        """
        pass

    @abstractmethod
    async def execute_market_buy(
        self,
        ticker: str,
        amount: Money,
    ) -> OrderResponse:
        """
        Execute a market buy order.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")
            amount: Amount in quote currency to spend

        Returns:
            OrderResponse with execution result
        """
        pass

    @abstractmethod
    async def execute_market_sell(
        self,
        ticker: str,
        volume: Decimal,
    ) -> OrderResponse:
        """
        Execute a market sell order.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")
            volume: Volume in base currency to sell

        Returns:
            OrderResponse with execution result
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Exchange order ID

        Returns:
            True if cancellation was successful

        Raises:
            ExchangeError: If cancellation fails
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """
        Get current status of an order.

        Args:
            order_id: Exchange order ID

        Returns:
            OrderResponse with current order status

        Raises:
            ExchangeError: If order not found or API fails
        """
        pass

    # --- Position Operations ---

    @abstractmethod
    async def get_position(self, ticker: str) -> Optional[PositionInfo]:
        """
        Get current position for a ticker.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")

        Returns:
            PositionInfo if position exists, None otherwise
        """
        pass

    @abstractmethod
    async def get_all_positions(self) -> List[PositionInfo]:
        """
        Get all open positions.

        Returns:
            List of PositionInfo for all positions
        """
        pass

    # --- Market Data ---

    @abstractmethod
    async def get_current_price(self, ticker: str) -> Money:
        """
        Get current market price for a ticker.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")

        Returns:
            Current price as Money

        Raises:
            ExchangeError: If ticker not found or API fails
        """
        pass

    @abstractmethod
    async def get_orderbook(
        self,
        ticker: str,
    ) -> dict:
        """
        Get current orderbook for a ticker.

        Args:
            ticker: Trading pair

        Returns:
            Orderbook data with bids and asks
        """
        pass

    # --- Utility ---

    @abstractmethod
    async def is_market_open(self, ticker: str) -> bool:
        """
        Check if market is open for trading.

        Args:
            ticker: Trading pair

        Returns:
            True if market is open
        """
        pass

    @abstractmethod
    async def get_min_order_amount(self, ticker: str) -> Money:
        """
        Get minimum order amount for a ticker.

        Args:
            ticker: Trading pair

        Returns:
            Minimum order amount
        """
        pass
