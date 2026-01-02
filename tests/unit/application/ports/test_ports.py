"""
Tests for Application Ports.

These tests verify that port interfaces are correctly defined as ABCs
and that mock implementations can properly implement them.
"""
import pytest
from abc import ABC
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import uuid4

from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.ports.outbound.ai_port import AIPort
from src.application.ports.outbound.market_data_port import MarketDataPort
from src.application.ports.outbound.persistence_port import PersistencePort
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
from src.domain.entities.trade import Trade, Order, Position, OrderSide
from src.domain.value_objects.money import Money, Currency


class TestExchangePort:
    """Tests for ExchangePort interface."""

    def test_exchange_port_is_abstract(self):
        """ExchangePort should be an abstract base class."""
        assert issubclass(ExchangePort, ABC)

    def test_cannot_instantiate_exchange_port(self):
        """Should not be able to instantiate ExchangePort directly."""
        with pytest.raises(TypeError):
            ExchangePort()

    def test_mock_exchange_adapter_can_implement(self):
        """Mock adapter should be able to implement ExchangePort."""

        class MockExchangeAdapter(ExchangePort):
            """Mock implementation for testing."""

            async def get_balance(self, currency: str) -> BalanceInfo:
                return BalanceInfo(
                    currency=currency,
                    total=Money.krw(1000000),
                    available=Money.krw(1000000),
                    locked=Money.zero(Currency.KRW),
                )

            async def get_all_balances(self) -> List[BalanceInfo]:
                return []

            async def execute_order(self, request: OrderRequest) -> OrderResponse:
                return OrderResponse.success_response(
                    ticker=request.ticker,
                    side=request.side,
                    order_id="mock-123",
                    executed_price=Money.krw(50000000),
                    executed_volume=Decimal("0.002"),
                    fee=Money.krw(50),
                )

            async def execute_market_buy(
                self, ticker: str, amount: Money
            ) -> OrderResponse:
                return OrderResponse.success_response(
                    ticker=ticker,
                    side=OrderSide.BUY,
                    order_id="mock-123",
                    executed_price=Money.krw(50000000),
                    executed_volume=Decimal("0.002"),
                    fee=Money.krw(50),
                )

            async def execute_market_sell(
                self, ticker: str, volume: Decimal
            ) -> OrderResponse:
                return OrderResponse.success_response(
                    ticker=ticker,
                    side=OrderSide.SELL,
                    order_id="mock-123",
                    executed_price=Money.krw(50000000),
                    executed_volume=volume,
                    fee=Money.krw(50),
                )

            async def cancel_order(self, order_id: str) -> bool:
                return True

            async def get_order_status(self, order_id: str) -> OrderResponse:
                return OrderResponse.success_response(
                    ticker="KRW-BTC",
                    side=OrderSide.BUY,
                    order_id=order_id,
                    executed_price=Money.krw(50000000),
                    executed_volume=Decimal("0.002"),
                    fee=Money.krw(50),
                )

            async def get_position(self, ticker: str) -> Optional[PositionInfo]:
                return None

            async def get_all_positions(self) -> List[PositionInfo]:
                return []

            async def get_current_price(self, ticker: str) -> Money:
                return Money.krw(50000000)

            async def get_orderbook(self, ticker: str) -> dict:
                return {"bids": [], "asks": []}

            async def is_market_open(self, ticker: str) -> bool:
                return True

            async def get_min_order_amount(self, ticker: str) -> Money:
                return Money.krw(5000)

        # Should be able to instantiate
        adapter = MockExchangeAdapter()
        assert isinstance(adapter, ExchangePort)


class TestAIPort:
    """Tests for AIPort interface."""

    def test_ai_port_is_abstract(self):
        """AIPort should be an abstract base class."""
        assert issubclass(AIPort, ABC)

    def test_cannot_instantiate_ai_port(self):
        """Should not be able to instantiate AIPort directly."""
        with pytest.raises(TypeError):
            AIPort()

    def test_mock_ai_adapter_can_implement(self):
        """Mock adapter should be able to implement AIPort."""

        class MockAIAdapter(AIPort):
            """Mock implementation for testing."""

            async def analyze(self, request: AnalysisRequest) -> TradingDecision:
                return TradingDecision(
                    decision=DecisionType.HOLD,
                    confidence=Decimal("0.8"),
                    reasoning="Mock analysis",
                )

            async def analyze_entry(
                self, request: AnalysisRequest
            ) -> TradingDecision:
                return TradingDecision(
                    decision=DecisionType.BUY,
                    confidence=Decimal("0.75"),
                    reasoning="Good entry point",
                )

            async def analyze_exit(
                self, request: AnalysisRequest
            ) -> TradingDecision:
                return TradingDecision(
                    decision=DecisionType.HOLD,
                    confidence=Decimal("0.6"),
                    reasoning="Hold position",
                )

            async def get_market_sentiment(
                self, ticker: str, news_context: Optional[str] = None
            ) -> str:
                return "neutral"

            async def validate_signal(
                self, request: AnalysisRequest, proposed_action: str
            ) -> bool:
                return True

            async def is_available(self) -> bool:
                return True

            async def get_remaining_quota(self) -> Optional[int]:
                return 1000

        adapter = MockAIAdapter()
        assert isinstance(adapter, AIPort)


class TestMarketDataPort:
    """Tests for MarketDataPort interface."""

    def test_market_data_port_is_abstract(self):
        """MarketDataPort should be an abstract base class."""
        assert issubclass(MarketDataPort, ABC)

    def test_cannot_instantiate_market_data_port(self):
        """Should not be able to instantiate MarketDataPort directly."""
        with pytest.raises(TypeError):
            MarketDataPort()

    def test_mock_market_data_adapter_can_implement(self):
        """Mock adapter should be able to implement MarketDataPort."""

        class MockMarketDataAdapter(MarketDataPort):
            """Mock implementation for testing."""

            async def get_ohlcv(
                self, ticker: str, interval: str = "minute60", count: int = 200
            ) -> List[MarketData]:
                return []

            async def get_current_price(self, ticker: str) -> Decimal:
                return Decimal("50000000")

            async def get_ticker_info(self, ticker: str) -> Dict[str, Any]:
                return {"price": 50000000, "volume": 1000}

            async def calculate_indicators(
                self, market_data: List[MarketData]
            ) -> TechnicalIndicators:
                return TechnicalIndicators()

            async def get_indicators(
                self, ticker: str, interval: str = "minute60"
            ) -> TechnicalIndicators:
                return TechnicalIndicators()

            async def get_orderbook(
                self, ticker: str, depth: int = 15
            ) -> Dict[str, Any]:
                return {"bids": [], "asks": []}

            async def get_spread(self, ticker: str) -> Decimal:
                return Decimal("1000")

            async def get_all_tickers(self) -> List[str]:
                return ["KRW-BTC", "KRW-ETH"]

            async def get_top_volume_tickers(
                self, count: int = 10, quote_currency: str = "KRW"
            ) -> List[str]:
                return ["KRW-BTC", "KRW-ETH"]

            async def get_historical_data(
                self,
                ticker: str,
                start_date: datetime,
                end_date: datetime,
                interval: str = "day",
            ) -> List[MarketData]:
                return []

            async def is_ticker_valid(self, ticker: str) -> bool:
                return True

            async def get_min_order_size(self, ticker: str) -> Decimal:
                return Decimal("0.0001")

        adapter = MockMarketDataAdapter()
        assert isinstance(adapter, MarketDataPort)


class TestPersistencePort:
    """Tests for PersistencePort interface."""

    def test_persistence_port_is_abstract(self):
        """PersistencePort should be an abstract base class."""
        assert issubclass(PersistencePort, ABC)

    def test_cannot_instantiate_persistence_port(self):
        """Should not be able to instantiate PersistencePort directly."""
        with pytest.raises(TypeError):
            PersistencePort()

    def test_mock_persistence_adapter_can_implement(self):
        """Mock adapter should be able to implement PersistencePort."""

        class MockPersistenceAdapter(PersistencePort):
            """Mock implementation for testing."""

            async def save_trade(self, trade: Trade) -> Trade:
                return trade

            async def get_trade(self, trade_id) -> Optional[Trade]:
                return None

            async def get_trades_by_ticker(
                self, ticker: str, limit: int = 100
            ) -> List[Trade]:
                return []

            async def get_trades_in_range(
                self,
                start_date: datetime,
                end_date: datetime,
                ticker: Optional[str] = None,
            ) -> List[Trade]:
                return []

            async def save_order(self, order: Order) -> Order:
                return order

            async def get_order(self, order_id) -> Optional[Order]:
                return None

            async def get_open_orders(
                self, ticker: Optional[str] = None
            ) -> List[Order]:
                return []

            async def update_order_status(
                self, order_id, status: str, **kwargs
            ) -> Optional[Order]:
                return None

            async def save_position(self, position: Position) -> Position:
                return position

            async def get_position(self, ticker: str) -> Optional[Position]:
                return None

            async def get_all_positions(self) -> List[Position]:
                return []

            async def close_position(self, ticker: str) -> bool:
                return True

            async def save_decision(
                self, ticker: str, decision: TradingDecision
            ) -> Dict[str, Any]:
                return {"id": 1, "ticker": ticker}

            async def get_recent_decisions(
                self, ticker: str, limit: int = 10
            ) -> List[Dict[str, Any]]:
                return []

            async def save_portfolio_snapshot(
                self, total_value: Decimal, positions: Dict[str, Any]
            ) -> Dict[str, Any]:
                return {"id": 1}

            async def get_portfolio_history(
                self, days: int = 30
            ) -> List[Dict[str, Any]]:
                return []

            async def get_trade_statistics(
                self, ticker: Optional[str] = None, days: int = 30
            ) -> Dict[str, Any]:
                return {"total_trades": 0, "win_rate": 0}

            async def get_daily_pnl(
                self, date: Optional[datetime] = None
            ) -> Decimal:
                return Decimal("0")

            async def get_weekly_pnl(self) -> Decimal:
                return Decimal("0")

            async def health_check(self) -> bool:
                return True

            async def cleanup_old_data(self, days: int = 90) -> int:
                return 0

        adapter = MockPersistenceAdapter()
        assert isinstance(adapter, PersistencePort)


class TestDTOs:
    """Tests for Data Transfer Objects."""

    def test_order_request_market_buy(self):
        """Should create market buy order request."""
        request = OrderRequest.market_buy("KRW-BTC", Money.krw(100000))
        assert request.ticker == "KRW-BTC"
        assert request.side == OrderSide.BUY
        assert request.amount == Money.krw(100000)

    def test_order_request_market_sell(self):
        """Should create market sell order request."""
        request = OrderRequest.market_sell("KRW-BTC", Decimal("0.002"))
        assert request.ticker == "KRW-BTC"
        assert request.side == OrderSide.SELL
        assert request.volume == Decimal("0.002")

    def test_order_request_validation(self):
        """Should validate order request."""
        # Market buy without amount should fail
        with pytest.raises(ValueError, match="amount"):
            OrderRequest(
                ticker="KRW-BTC",
                side=OrderSide.BUY,
            )

    def test_order_response_success(self):
        """Should create success order response."""
        response = OrderResponse.success_response(
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_id="123",
            executed_price=Money.krw(50000000),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(50),
        )
        assert response.success is True
        assert response.order_id == "123"
        assert response.total_amount == Money.krw(100000)

    def test_order_response_failure(self):
        """Should create failure order response."""
        response = OrderResponse.failure_response(
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            error_message="Insufficient balance",
        )
        assert response.success is False
        assert response.error_message == "Insufficient balance"

    def test_trading_decision_is_actionable(self):
        """Should check if decision is actionable."""
        buy = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Test",
        )
        hold = TradingDecision(
            decision=DecisionType.HOLD,
            confidence=Decimal("0.8"),
            reasoning="Test",
        )
        assert buy.is_actionable() is True
        assert hold.is_actionable() is False

    def test_trading_decision_is_high_confidence(self):
        """Should check confidence level."""
        high = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="Test",
        )
        low = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.5"),
            reasoning="Test",
        )
        assert high.is_high_confidence() is True
        assert low.is_high_confidence() is False

    def test_market_data_from_ohlcv(self):
        """Should create MarketData from OHLCV dict."""
        data = MarketData.from_ohlcv(
            "KRW-BTC",
            {
                "open": 50000000,
                "high": 51000000,
                "low": 49000000,
                "close": 50500000,
                "volume": 100.5,
            },
        )
        assert data.ticker == "KRW-BTC"
        assert data.close == Decimal("50500000")

    def test_technical_indicators_from_dict(self):
        """Should create TechnicalIndicators from dict."""
        indicators = TechnicalIndicators.from_dict({
            "rsi": 45.5,
            "macd": 100.0,
        })
        assert indicators.rsi == Decimal("45.5")
        assert indicators.macd == Decimal("100.0")

    def test_balance_info_from_dict(self):
        """Should create BalanceInfo from dict."""
        balance = BalanceInfo.from_dict({
            "currency": "KRW",
            "total": 1000000,
            "available": 900000,
            "locked": 100000,
        })
        assert balance.currency == "KRW"
        assert balance.total.amount == Decimal("1000000")

    def test_position_info_from_dict(self):
        """Should create PositionInfo from dict."""
        position = PositionInfo.from_dict({
            "ticker": "KRW-BTC",
            "symbol": "BTC",
            "volume": "0.01",
            "avg_buy_price": 50000000,
            "current_price": 55000000,
        })
        assert position.ticker == "KRW-BTC"
        assert position.is_profitable() is True
