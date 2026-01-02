"""
Legacy Bridge Adapters.

These adapters wrap existing legacy services to implement Clean Architecture ports,
enabling gradual migration from old code to new architecture.

Usage:
    # Wrap existing TradingService as ExchangePort
    legacy_exchange = LegacyExchangeAdapter(upbit_client)

    # Wrap existing AIService as AIPort
    legacy_ai = LegacyAIAdapter(ai_service)

    # Use with Container
    container = Container(
        exchange_port=legacy_exchange,
        ai_port=legacy_ai,
    )
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any

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


class LegacyExchangeAdapter(ExchangePort):
    """
    Wraps legacy UpbitClient to implement ExchangePort.

    This adapter allows gradual migration by using existing UpbitClient
    while conforming to the new port interface.
    """

    def __init__(self, upbit_client):
        """
        Initialize with legacy UpbitClient.

        Args:
            upbit_client: Existing UpbitClient instance
        """
        self._client = upbit_client

    async def get_balance(self, currency: str) -> BalanceInfo:
        """Get balance using legacy client."""
        try:
            balance = self._client.get_balance(currency)
            balance_decimal = Decimal(str(balance or 0))

            return BalanceInfo(
                currency=currency,
                total=Money.krw(balance_decimal),
                available=Money.krw(balance_decimal),
                locked=Money.zero(Currency.KRW),
            )
        except Exception:
            return BalanceInfo(
                currency=currency,
                total=Money.zero(Currency.KRW),
                available=Money.zero(Currency.KRW),
                locked=Money.zero(Currency.KRW),
            )

    async def get_all_balances(self) -> List[BalanceInfo]:
        """Get all balances using legacy client."""
        try:
            balances = self._client.get_balances()
            result = []
            for bal in balances or []:
                currency = bal.get("currency", "")
                total = Decimal(str(bal.get("balance", 0)))
                if total > 0:
                    result.append(BalanceInfo(
                        currency=currency,
                        total=Money.krw(total),
                        available=Money.krw(total),
                        locked=Money.zero(Currency.KRW),
                    ))
            return result
        except Exception:
            return []

    async def execute_order(self, request: OrderRequest) -> OrderResponse:
        """Execute order using legacy client."""
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
        """Execute market buy using legacy client."""
        try:
            result = self._client.buy_market_order(ticker, float(amount.amount))
            if result:
                return OrderResponse.success_response(
                    ticker=ticker,
                    side=OrderSide.BUY,
                    order_id=result.get("uuid", ""),
                    executed_price=amount,
                    executed_volume=Decimal(str(result.get("volume", 0))),
                    fee=Money.krw(amount.amount * Decimal("0.0005")),
                )
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.BUY,
                error_message="Order returned None",
            )
        except Exception as e:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.BUY,
                error_message=str(e),
            )

    async def execute_market_sell(self, ticker: str, volume: Decimal) -> OrderResponse:
        """Execute market sell using legacy client."""
        try:
            result = self._client.sell_market_order(ticker, float(volume))
            if result:
                current_price = await self.get_current_price(ticker)
                return OrderResponse.success_response(
                    ticker=ticker,
                    side=OrderSide.SELL,
                    order_id=result.get("uuid", ""),
                    executed_price=current_price,
                    executed_volume=volume,
                    fee=Money.krw(current_price.amount * volume * Decimal("0.0005")),
                )
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message="Order returned None",
            )
        except Exception as e:
            return OrderResponse.failure_response(
                ticker=ticker,
                side=OrderSide.SELL,
                error_message=str(e),
            )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order using legacy client."""
        try:
            result = self._client.cancel_order(order_id)
            return result is not None
        except Exception:
            return False

    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get order status using legacy client."""
        try:
            result = self._client.get_order(order_id)
            if result:
                return OrderResponse(
                    success=True,
                    ticker=result.get("market", ""),
                    side=OrderSide.BUY,
                    order_id=order_id,
                    status=OrderStatus.FILLED,
                )
            return OrderResponse.failure_response(
                ticker="",
                side=OrderSide.BUY,
                error_message="Order not found",
            )
        except Exception as e:
            return OrderResponse.failure_response(
                ticker="",
                side=OrderSide.BUY,
                error_message=str(e),
            )

    async def get_position(self, ticker: str) -> Optional[PositionInfo]:
        """Get position using legacy client."""
        try:
            symbol = ticker.split("-")[-1] if "-" in ticker else ticker
            balance = self._client.get_balance(symbol)
            avg_price = self._client.get_avg_buy_price(symbol)

            if not balance or float(balance) == 0:
                return None

            volume = Decimal(str(balance))
            avg_buy_price = Decimal(str(avg_price or 0))
            current_price = await self.get_current_price(ticker)

            return PositionInfo(
                ticker=ticker,
                symbol=symbol,
                volume=volume,
                avg_buy_price=Money.krw(avg_buy_price),
                current_price=current_price,
                profit_loss=Money.krw((current_price.amount - avg_buy_price) * volume),
                profit_rate=((current_price.amount - avg_buy_price) / avg_buy_price * 100)
                    if avg_buy_price > 0 else Decimal("0"),
                total_cost=Money.krw(avg_buy_price * volume),
                current_value=Money.krw(current_price.amount * volume),
            )
        except Exception:
            return None

    async def get_all_positions(self) -> List[PositionInfo]:
        """Get all positions using legacy client."""
        positions = []
        balances = await self.get_all_balances()
        for balance in balances:
            if balance.currency == "KRW":
                continue
            ticker = f"KRW-{balance.currency}"
            position = await self.get_position(ticker)
            if position:
                positions.append(position)
        return positions

    async def get_current_price(self, ticker: str) -> Money:
        """Get current price using legacy client."""
        try:
            price = self._client.get_current_price(ticker)
            return Money.krw(Decimal(str(price or 0)))
        except Exception:
            return Money.zero(Currency.KRW)

    async def get_orderbook(self, ticker: str) -> dict:
        """Get orderbook using legacy client."""
        try:
            return self._client.get_orderbook(ticker) or {"bids": [], "asks": []}
        except Exception:
            return {"bids": [], "asks": []}

    async def is_market_open(self, ticker: str) -> bool:
        """Check if market is open."""
        try:
            price = self._client.get_current_price(ticker)
            return price is not None and price > 0
        except Exception:
            return False

    async def get_min_order_amount(self, ticker: str) -> Money:
        """Get minimum order amount."""
        return Money.krw(Decimal("5000"))


class LegacyAIAdapter(AIPort):
    """
    Wraps legacy AIService to implement AIPort.

    This adapter allows gradual migration by using existing AIService
    while conforming to the new port interface.
    """

    def __init__(self, ai_service):
        """
        Initialize with legacy AIService.

        Args:
            ai_service: Existing AIService instance
        """
        self._service = ai_service

    async def analyze(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze using legacy AIService."""
        try:
            # Convert request to legacy format
            analysis_data = self._prepare_analysis_data(request)

            # Call legacy analyze method
            result = self._service.analyze(analysis_data)

            # Convert result to TradingDecision
            return self._convert_result(result)
        except Exception as e:
            return TradingDecision(
                decision=DecisionType.HOLD,
                confidence=Decimal("0"),
                reasoning=f"Analysis failed: {str(e)}",
            )

    async def analyze_entry(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze entry using legacy AIService."""
        return await self.analyze(request)

    async def analyze_exit(self, request: AnalysisRequest) -> TradingDecision:
        """Analyze exit using legacy AIService."""
        return await self.analyze(request)

    async def get_market_sentiment(
        self,
        ticker: str,
        news_context: Optional[str] = None,
    ) -> str:
        """Get market sentiment."""
        return "neutral"

    async def validate_signal(
        self,
        request: AnalysisRequest,
        proposed_action: str,
    ) -> bool:
        """Validate signal using legacy AIService."""
        try:
            decision = await self.analyze(request)
            if proposed_action.lower() == "buy":
                return decision.decision == DecisionType.BUY
            elif proposed_action.lower() == "sell":
                return decision.decision == DecisionType.SELL
            return False
        except Exception:
            return False

    async def is_available(self) -> bool:
        """Check if AI service is available."""
        return True

    async def get_remaining_quota(self) -> Optional[int]:
        """Get remaining quota."""
        return None

    def _prepare_analysis_data(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Convert AnalysisRequest to legacy format."""
        data = {
            "ticker": request.ticker,
            "current_price": float(request.current_price) if request.current_price else 0,
        }

        if request.indicators:
            data["indicators"] = {
                "rsi": float(request.indicators.rsi) if request.indicators.rsi else None,
                "macd": float(request.indicators.macd) if request.indicators.macd else None,
            }

        if request.position_info:
            data["position"] = request.position_info

        return data

    def _convert_result(self, result: Dict[str, Any]) -> TradingDecision:
        """Convert legacy result to TradingDecision."""
        decision_str = result.get("decision", "hold").lower()
        decision_map = {
            "buy": DecisionType.BUY,
            "sell": DecisionType.SELL,
            "hold": DecisionType.HOLD,
        }
        decision = decision_map.get(decision_str, DecisionType.HOLD)

        confidence_str = result.get("confidence", "medium")
        confidence_map = {
            "high": Decimal("0.9"),
            "medium": Decimal("0.6"),
            "low": Decimal("0.3"),
        }
        confidence = confidence_map.get(confidence_str.lower(), Decimal("0.5"))

        return TradingDecision(
            decision=decision,
            confidence=confidence,
            reasoning=result.get("reason", ""),
            risk_assessment=result.get("risk_assessment", "medium"),
        )


class LegacyMarketDataAdapter(MarketDataPort):
    """
    Wraps legacy DataCollector to implement MarketDataPort.
    """

    def __init__(self, data_collector):
        """
        Initialize with legacy DataCollector.

        Args:
            data_collector: Existing DataCollector instance
        """
        self._collector = data_collector

    async def get_ohlcv(
        self,
        ticker: str,
        interval: str = "minute60",
        count: int = 200,
    ) -> List[MarketData]:
        """Get OHLCV using legacy collector."""
        try:
            from datetime import datetime
            df = self._collector.collect_chart_data(
                ticker=ticker,
                interval=interval,
                count=count,
            )
            if df is None or df.empty:
                return []

            result = []
            for idx, row in df.iterrows():
                result.append(MarketData(
                    ticker=ticker,
                    timestamp=idx if isinstance(idx, datetime) else datetime.now(),
                    open=Decimal(str(row.get("open", 0))),
                    high=Decimal(str(row.get("high", 0))),
                    low=Decimal(str(row.get("low", 0))),
                    close=Decimal(str(row.get("close", 0))),
                    volume=Decimal(str(row.get("volume", 0))),
                ))
            return result
        except Exception:
            return []

    async def get_current_price(self, ticker: str) -> Decimal:
        """Get current price."""
        try:
            import pyupbit
            price = pyupbit.get_current_price(ticker)
            return Decimal(str(price or 0))
        except Exception:
            return Decimal("0")

    async def get_ticker_info(self, ticker: str) -> Dict[str, Any]:
        """Get ticker info."""
        return {"ticker": ticker}

    async def calculate_indicators(
        self,
        market_data: List[MarketData],
    ) -> TechnicalIndicators:
        """Calculate indicators."""
        return TechnicalIndicators()

    async def get_indicators(
        self,
        ticker: str,
        interval: str = "minute60",
    ) -> TechnicalIndicators:
        """Get indicators."""
        return TechnicalIndicators()

    async def get_orderbook(
        self,
        ticker: str,
        depth: int = 15,
    ) -> Dict[str, Any]:
        """Get orderbook."""
        try:
            return self._collector.get_orderbook(ticker) or {"bids": [], "asks": []}
        except Exception:
            return {"bids": [], "asks": []}

    async def get_spread(self, ticker: str) -> Decimal:
        """Get spread."""
        return Decimal("0")

    async def get_all_tickers(self) -> List[str]:
        """Get all tickers."""
        try:
            import pyupbit
            return pyupbit.get_tickers(fiat="KRW") or []
        except Exception:
            return []

    async def get_top_volume_tickers(
        self,
        count: int = 10,
        quote_currency: str = "KRW",
    ) -> List[str]:
        """Get top volume tickers."""
        return []

    async def get_historical_data(
        self,
        ticker: str,
        start_date: Any,
        end_date: Any,
        interval: str = "day",
    ) -> List[MarketData]:
        """Get historical data."""
        return await self.get_ohlcv(ticker, interval, 365)

    async def is_ticker_valid(self, ticker: str) -> bool:
        """Check if ticker is valid."""
        tickers = await self.get_all_tickers()
        return ticker in tickers

    async def get_min_order_size(self, ticker: str) -> Decimal:
        """Get minimum order size."""
        return Decimal("0.0001")
