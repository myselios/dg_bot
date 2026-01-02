"""
MarketDataPort - Interface for market data operations.

This port defines the contract for fetching market data.
Adapters implementing this interface handle data collection from various sources.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from src.application.dto.analysis import MarketData, TechnicalIndicators


class MarketDataPort(ABC):
    """
    Port interface for market data operations.

    This interface defines operations for collecting market data
    including OHLCV data, orderbooks, and technical indicators.
    """

    # --- OHLCV Data ---

    @abstractmethod
    async def get_ohlcv(
        self,
        ticker: str,
        interval: str = "minute60",
        count: int = 200,
    ) -> List[MarketData]:
        """
        Get OHLCV (candlestick) data.

        Args:
            ticker: Trading pair (e.g., "KRW-BTC")
            interval: Time interval (minute1, minute60, day, etc.)
            count: Number of candles to fetch

        Returns:
            List of MarketData (most recent last)

        Raises:
            DataCollectionError: If data fetch fails
        """
        pass

    @abstractmethod
    async def get_current_price(self, ticker: str) -> Decimal:
        """
        Get current market price.

        Args:
            ticker: Trading pair

        Returns:
            Current price as Decimal

        Raises:
            DataCollectionError: If price fetch fails
        """
        pass

    @abstractmethod
    async def get_ticker_info(self, ticker: str) -> Dict[str, Any]:
        """
        Get ticker information including 24h stats.

        Args:
            ticker: Trading pair

        Returns:
            Dictionary with ticker info (price, volume, change, etc.)
        """
        pass

    # --- Technical Indicators ---

    @abstractmethod
    async def calculate_indicators(
        self,
        market_data: List[MarketData],
    ) -> TechnicalIndicators:
        """
        Calculate technical indicators from market data.

        Args:
            market_data: List of OHLCV data

        Returns:
            TechnicalIndicators with calculated values
        """
        pass

    @abstractmethod
    async def get_indicators(
        self,
        ticker: str,
        interval: str = "minute60",
    ) -> TechnicalIndicators:
        """
        Get pre-calculated technical indicators.

        Args:
            ticker: Trading pair
            interval: Time interval

        Returns:
            TechnicalIndicators for the ticker
        """
        pass

    # --- Orderbook ---

    @abstractmethod
    async def get_orderbook(
        self,
        ticker: str,
        depth: int = 15,
    ) -> Dict[str, Any]:
        """
        Get orderbook data.

        Args:
            ticker: Trading pair
            depth: Number of levels to fetch

        Returns:
            Orderbook with bids and asks
        """
        pass

    @abstractmethod
    async def get_spread(self, ticker: str) -> Decimal:
        """
        Get bid-ask spread.

        Args:
            ticker: Trading pair

        Returns:
            Spread as Decimal
        """
        pass

    # --- Multiple Tickers ---

    @abstractmethod
    async def get_all_tickers(self) -> List[str]:
        """
        Get list of all available tickers.

        Returns:
            List of ticker symbols
        """
        pass

    @abstractmethod
    async def get_top_volume_tickers(
        self,
        count: int = 10,
        quote_currency: str = "KRW",
    ) -> List[str]:
        """
        Get top tickers by trading volume.

        Args:
            count: Number of tickers to return
            quote_currency: Quote currency filter

        Returns:
            List of ticker symbols sorted by volume
        """
        pass

    # --- Historical Data ---

    @abstractmethod
    async def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day",
    ) -> List[MarketData]:
        """
        Get historical market data.

        Args:
            ticker: Trading pair
            start_date: Start of date range
            end_date: End of date range
            interval: Time interval

        Returns:
            List of historical MarketData
        """
        pass

    # --- Utility ---

    @abstractmethod
    async def is_ticker_valid(self, ticker: str) -> bool:
        """
        Check if ticker is valid and tradeable.

        Args:
            ticker: Trading pair

        Returns:
            True if ticker is valid
        """
        pass

    @abstractmethod
    async def get_min_order_size(self, ticker: str) -> Decimal:
        """
        Get minimum order size for a ticker.

        Args:
            ticker: Trading pair

        Returns:
            Minimum order size in base currency
        """
        pass
