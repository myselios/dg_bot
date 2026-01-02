"""
UpbitMarketDataAdapter - Upbit implementation of MarketDataPort.

This adapter wraps pyupbit for market data collection.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

import pyupbit
import pandas as pd

from src.application.ports.outbound.market_data_port import MarketDataPort
from src.application.dto.analysis import MarketData, TechnicalIndicators
from src.config.settings import DataConfig


class UpbitMarketDataAdapter(MarketDataPort):
    """
    Upbit market data adapter implementing MarketDataPort.

    Uses pyupbit for data collection and pandas for indicator calculation.
    """

    # --- OHLCV Data ---

    async def get_ohlcv(
        self,
        ticker: str,
        interval: str = "minute60",
        count: int = 200,
    ) -> List[MarketData]:
        """Get OHLCV (candlestick) data."""
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)

            if df is None or df.empty:
                return []

            result = []
            for idx, row in df.iterrows():
                result.append(MarketData(
                    ticker=ticker,
                    timestamp=idx if isinstance(idx, datetime) else datetime.now(),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                ))

            return result

        except Exception:
            return []

    async def get_current_price(self, ticker: str) -> Decimal:
        """Get current market price."""
        try:
            price = pyupbit.get_current_price(ticker)
            return Decimal(str(price or 0))
        except Exception:
            return Decimal("0")

    async def get_ticker_info(self, ticker: str) -> Dict[str, Any]:
        """Get ticker information including 24h stats."""
        try:
            tickers = pyupbit.get_tickers()
            if ticker not in tickers:
                return {}

            current_price = pyupbit.get_current_price(ticker)
            ohlcv = pyupbit.get_ohlcv(ticker, interval="day", count=2)

            if ohlcv is not None and len(ohlcv) >= 2:
                prev_close = float(ohlcv.iloc[-2]["close"])
                change = ((current_price - prev_close) / prev_close) * 100
                volume_24h = float(ohlcv.iloc[-1]["volume"])
            else:
                change = 0
                volume_24h = 0

            return {
                "ticker": ticker,
                "price": current_price,
                "change_24h": change,
                "volume_24h": volume_24h,
            }
        except Exception:
            return {}

    # --- Technical Indicators ---

    async def calculate_indicators(
        self,
        market_data: List[MarketData],
    ) -> TechnicalIndicators:
        """Calculate technical indicators from market data."""
        if not market_data:
            return TechnicalIndicators()

        try:
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    "open": float(m.open),
                    "high": float(m.high),
                    "low": float(m.low),
                    "close": float(m.close),
                    "volume": float(m.volume),
                }
                for m in market_data
            ])

            return self._calculate_indicators_from_df(df)

        except Exception:
            return TechnicalIndicators()

    async def get_indicators(
        self,
        ticker: str,
        interval: str = "minute60",
    ) -> TechnicalIndicators:
        """Get pre-calculated technical indicators."""
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=200)
            if df is None or df.empty:
                return TechnicalIndicators()

            return self._calculate_indicators_from_df(df)

        except Exception:
            return TechnicalIndicators()

    def _calculate_indicators_from_df(self, df: pd.DataFrame) -> TechnicalIndicators:
        """Calculate indicators from pandas DataFrame."""
        try:
            close = df["close"]
            high = df["high"]
            low = df["low"]
            volume = df["volume"]

            # RSI (14-period)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_value = rsi.iloc[-1] if not rsi.empty else None

            # MACD
            ema_12 = close.ewm(span=12, adjust=False).mean()
            ema_26 = close.ewm(span=26, adjust=False).mean()
            macd = ema_12 - ema_26
            macd_signal = macd.ewm(span=9, adjust=False).mean()
            macd_histogram = macd - macd_signal

            # Bollinger Bands
            sma_20 = close.rolling(window=20).mean()
            std_20 = close.rolling(window=20).std()
            bb_upper = sma_20 + (std_20 * 2)
            bb_lower = sma_20 - (std_20 * 2)

            # SMA
            sma_50 = close.rolling(window=50).mean()

            # ATR
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()

            # Volume SMA
            volume_sma = volume.rolling(window=20).mean()

            return TechnicalIndicators(
                rsi=Decimal(str(rsi_value)) if pd.notna(rsi_value) else None,
                macd=Decimal(str(macd.iloc[-1])) if not macd.empty else None,
                macd_signal=Decimal(str(macd_signal.iloc[-1])) if not macd_signal.empty else None,
                macd_histogram=Decimal(str(macd_histogram.iloc[-1])) if not macd_histogram.empty else None,
                bb_upper=Decimal(str(bb_upper.iloc[-1])) if not bb_upper.empty and pd.notna(bb_upper.iloc[-1]) else None,
                bb_middle=Decimal(str(sma_20.iloc[-1])) if not sma_20.empty and pd.notna(sma_20.iloc[-1]) else None,
                bb_lower=Decimal(str(bb_lower.iloc[-1])) if not bb_lower.empty and pd.notna(bb_lower.iloc[-1]) else None,
                sma_20=Decimal(str(sma_20.iloc[-1])) if not sma_20.empty and pd.notna(sma_20.iloc[-1]) else None,
                sma_50=Decimal(str(sma_50.iloc[-1])) if not sma_50.empty and pd.notna(sma_50.iloc[-1]) else None,
                ema_12=Decimal(str(ema_12.iloc[-1])) if not ema_12.empty else None,
                ema_26=Decimal(str(ema_26.iloc[-1])) if not ema_26.empty else None,
                atr=Decimal(str(atr.iloc[-1])) if not atr.empty and pd.notna(atr.iloc[-1]) else None,
                volume_sma=Decimal(str(volume_sma.iloc[-1])) if not volume_sma.empty and pd.notna(volume_sma.iloc[-1]) else None,
            )

        except Exception:
            return TechnicalIndicators()

    # --- Orderbook ---

    async def get_orderbook(
        self,
        ticker: str,
        depth: int = 15,
    ) -> Dict[str, Any]:
        """Get orderbook data."""
        try:
            orderbook = pyupbit.get_orderbook(ticker)
            if orderbook and len(orderbook) > 0:
                data = orderbook[0]
                return {
                    "bids": data.get("orderbook_units", [])[:depth],
                    "asks": data.get("orderbook_units", [])[:depth],
                    "total_ask_size": data.get("total_ask_size", 0),
                    "total_bid_size": data.get("total_bid_size", 0),
                }
            return {"bids": [], "asks": []}
        except Exception:
            return {"bids": [], "asks": []}

    async def get_spread(self, ticker: str) -> Decimal:
        """Get bid-ask spread."""
        try:
            orderbook = await self.get_orderbook(ticker, depth=1)
            if orderbook.get("bids") and orderbook.get("asks"):
                best_bid = orderbook["bids"][0].get("bid_price", 0)
                best_ask = orderbook["asks"][0].get("ask_price", 0)
                return Decimal(str(best_ask - best_bid))
            return Decimal("0")
        except Exception:
            return Decimal("0")

    # --- Multiple Tickers ---

    async def get_all_tickers(self) -> List[str]:
        """Get list of all available tickers."""
        try:
            tickers = pyupbit.get_tickers(fiat="KRW")
            return tickers or []
        except Exception:
            return []

    async def get_top_volume_tickers(
        self,
        count: int = 10,
        quote_currency: str = "KRW",
    ) -> List[str]:
        """Get top tickers by trading volume."""
        try:
            tickers = pyupbit.get_tickers(fiat=quote_currency)
            if not tickers:
                return []

            # Get 24h volume for each ticker
            volumes = []
            for ticker in tickers[:50]:  # Limit to prevent rate limiting
                try:
                    ohlcv = pyupbit.get_ohlcv(ticker, interval="day", count=1)
                    if ohlcv is not None and not ohlcv.empty:
                        volume = float(ohlcv.iloc[-1]["volume"])
                        price = float(ohlcv.iloc[-1]["close"])
                        volumes.append((ticker, volume * price))
                except Exception:
                    continue

            # Sort by volume and return top N
            volumes.sort(key=lambda x: x[1], reverse=True)
            return [t[0] for t in volumes[:count]]

        except Exception:
            return []

    # --- Historical Data ---

    async def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day",
    ) -> List[MarketData]:
        """Get historical market data."""
        try:
            df = pyupbit.get_ohlcv(
                ticker,
                interval=interval,
                to=end_date.strftime("%Y-%m-%d %H:%M:%S"),
                count=365,  # Max count
            )

            if df is None or df.empty:
                return []

            # Filter by date range
            df = df[(df.index >= start_date) & (df.index <= end_date)]

            result = []
            for idx, row in df.iterrows():
                result.append(MarketData(
                    ticker=ticker,
                    timestamp=idx if isinstance(idx, datetime) else datetime.now(),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                ))

            return result

        except Exception:
            return []

    # --- Utility ---

    async def is_ticker_valid(self, ticker: str) -> bool:
        """Check if ticker is valid and tradeable."""
        try:
            tickers = pyupbit.get_tickers()
            return ticker in (tickers or [])
        except Exception:
            return False

    async def get_min_order_size(self, ticker: str) -> Decimal:
        """Get minimum order size for a ticker."""
        # Upbit minimum is typically defined by KRW amount, not volume
        # Return a reasonable default
        return Decimal("0.0001")
