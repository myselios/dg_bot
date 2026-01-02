"""
Mock adapters for testing.

These adapters implement port interfaces with predictable behavior for testing.
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.ports.outbound.ai_port import AIPort
from src.application.ports.outbound.market_data_port import MarketDataPort
from src.application.dto.trading import (
    OrderRequest,
    OrderResponse,
    BalanceInfo,
    PositionInfo,
)
from src.application.dto.analysis import (
    AnalysisRequest,
    TradingDecision,
    DecisionType,
    MarketData,
    TechnicalIndicators,
)
from src.domain.entities.trade import OrderSide, OrderStatus
from src.domain.value_objects.money import Money, Currency


class MockExchangeAdapter(ExchangePort):
    """Mock exchange adapter for testing."""

    def __init__(self):
        self._balances: Dict[str, BalanceInfo] = {
            "KRW": BalanceInfo(
                currency="KRW",
                total=Money.krw(Decimal("1000000")),
                available=Money.krw(Decimal("1000000")),
                locked=Money.zero(Currency.KRW),
            )
        }
        self._positions: Dict[str, PositionInfo] = {}
        self._current_prices: Dict[str, Decimal] = {
            "KRW-BTC": Decimal("50000000"),
            "KRW-ETH": Decimal("3000000"),
        }

    async def get_balance(self, currency: str) -> BalanceInfo:
        return self._balances.get(currency, BalanceInfo(
            currency=currency,
            total=Money.zero(Currency.KRW),
            available=Money.zero(Currency.KRW),
            locked=Money.zero(Currency.KRW),
        ))

    async def get_all_balances(self) -> List[BalanceInfo]:
        return list(self._balances.values())

    async def execute_order(self, request: OrderRequest) -> OrderResponse:
        if request.side == OrderSide.BUY and request.amount:
            return await self.execute_market_buy(request.ticker, request.amount)
        elif request.side == OrderSide.SELL and request.volume:
            return await self.execute_market_sell(request.ticker, request.volume)
        return OrderResponse.failure_response(
            ticker=request.ticker,
            side=request.side,
            error_message="Invalid order request",
        )

    async def execute_market_buy(self, ticker: str, amount: Money) -> OrderResponse:
        price = self._current_prices.get(ticker, Decimal("50000000"))
        volume = amount.amount / price
        fee = amount.amount * Decimal("0.0005")

        return OrderResponse.success_response(
            ticker=ticker,
            side=OrderSide.BUY,
            order_id="mock-order-123",
            executed_price=Money.krw(price),
            executed_volume=volume,
            fee=Money.krw(fee),
        )

    async def execute_market_sell(self, ticker: str, volume: Decimal) -> OrderResponse:
        price = self._current_prices.get(ticker, Decimal("50000000"))
        fee = volume * price * Decimal("0.0005")

        return OrderResponse.success_response(
            ticker=ticker,
            side=OrderSide.SELL,
            order_id="mock-order-456",
            executed_price=Money.krw(price),
            executed_volume=volume,
            fee=Money.krw(fee),
        )

    async def cancel_order(self, order_id: str) -> bool:
        return True

    async def get_order_status(self, order_id: str) -> OrderResponse:
        return OrderResponse(
            success=True,
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_id=order_id,
            status=OrderStatus.FILLED,
        )

    async def get_position(self, ticker: str) -> Optional[PositionInfo]:
        return self._positions.get(ticker)

    async def get_all_positions(self) -> List[PositionInfo]:
        return list(self._positions.values())

    async def get_current_price(self, ticker: str) -> Money:
        price = self._current_prices.get(ticker, Decimal("50000000"))
        return Money.krw(price)

    async def get_orderbook(self, ticker: str) -> dict:
        return {"bids": [], "asks": []}

    async def is_market_open(self, ticker: str) -> bool:
        return True

    async def get_min_order_amount(self, ticker: str) -> Money:
        return Money.krw(Decimal("5000"))

    # Test helpers
    def set_balance(self, currency: str, amount: Decimal):
        self._balances[currency] = BalanceInfo(
            currency=currency,
            total=Money.krw(amount),
            available=Money.krw(amount),
            locked=Money.zero(Currency.KRW),
        )

    def set_position(self, ticker: str, volume: Decimal, avg_price: Decimal):
        current_price = self._current_prices.get(ticker, avg_price)
        self._positions[ticker] = PositionInfo(
            ticker=ticker,
            symbol=ticker.split("-")[-1],
            volume=volume,
            avg_buy_price=Money.krw(avg_price),
            current_price=Money.krw(current_price),
            profit_loss=Money.krw((current_price - avg_price) * volume),
            profit_rate=(current_price - avg_price) / avg_price * 100 if avg_price > 0 else Decimal("0"),
            total_cost=Money.krw(avg_price * volume),
            current_value=Money.krw(current_price * volume),
        )


class MockAIAdapter(AIPort):
    """Mock AI adapter for testing."""

    def __init__(self):
        self._default_decision = TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0.7"),
            reasoning="Mock analysis result",
        )
        self._is_available = True

    async def analyze(self, request: AnalysisRequest) -> TradingDecision:
        return self._default_decision

    async def analyze_entry(self, request: AnalysisRequest) -> TradingDecision:
        return self._default_decision

    async def analyze_exit(self, request: AnalysisRequest) -> TradingDecision:
        return self._default_decision

    async def get_market_sentiment(
        self,
        ticker: str,
        news_context: Optional[str] = None,
    ) -> str:
        return "neutral"

    async def validate_signal(
        self,
        request: AnalysisRequest,
        proposed_action: str,
    ) -> bool:
        return True

    async def is_available(self) -> bool:
        return self._is_available

    async def get_remaining_quota(self) -> Optional[int]:
        return 1000

    # Test helpers
    def set_decision(self, decision: TradingDecision):
        self._default_decision = decision

    def set_available(self, available: bool):
        self._is_available = available


class MockMarketDataAdapter(MarketDataPort):
    """Mock market data adapter for testing."""

    def __init__(self):
        self._current_prices: Dict[str, Decimal] = {
            "KRW-BTC": Decimal("50000000"),
            "KRW-ETH": Decimal("3000000"),
        }

    async def get_ohlcv(
        self,
        ticker: str,
        interval: str = "minute60",
        count: int = 200,
    ) -> List[MarketData]:
        price = self._current_prices.get(ticker, Decimal("50000000"))
        return [
            MarketData(
                ticker=ticker,
                timestamp=datetime.now(),
                open=price * Decimal("0.99"),
                high=price * Decimal("1.01"),
                low=price * Decimal("0.98"),
                close=price,
                volume=Decimal("100"),
            )
            for _ in range(count)
        ]

    async def get_current_price(self, ticker: str) -> Decimal:
        return self._current_prices.get(ticker, Decimal("50000000"))

    async def get_ticker_info(self, ticker: str) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "price": float(self._current_prices.get(ticker, 50000000)),
            "change_24h": 2.5,
            "volume_24h": 1000000,
        }

    async def calculate_indicators(
        self,
        market_data: List[MarketData],
    ) -> TechnicalIndicators:
        return TechnicalIndicators(
            rsi=Decimal("50"),
            macd=Decimal("100"),
            macd_signal=Decimal("90"),
            bb_upper=Decimal("52000000"),
            bb_middle=Decimal("50000000"),
            bb_lower=Decimal("48000000"),
        )

    async def get_indicators(
        self,
        ticker: str,
        interval: str = "minute60",
    ) -> TechnicalIndicators:
        return await self.calculate_indicators([])

    async def get_orderbook(
        self,
        ticker: str,
        depth: int = 15,
    ) -> Dict[str, Any]:
        return {"bids": [], "asks": []}

    async def get_spread(self, ticker: str) -> Decimal:
        return Decimal("1000")

    async def get_all_tickers(self) -> List[str]:
        return list(self._current_prices.keys())

    async def get_top_volume_tickers(
        self,
        count: int = 10,
        quote_currency: str = "KRW",
    ) -> List[str]:
        return list(self._current_prices.keys())[:count]

    async def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day",
    ) -> List[MarketData]:
        return await self.get_ohlcv(ticker, interval, 30)

    async def is_ticker_valid(self, ticker: str) -> bool:
        return ticker in self._current_prices

    async def get_min_order_size(self, ticker: str) -> Decimal:
        return Decimal("0.0001")

    # Test helpers
    def set_price(self, ticker: str, price: Decimal):
        self._current_prices[ticker] = price
