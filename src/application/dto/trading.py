"""
Trading DTOs for order execution and position management.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from src.domain.entities.trade import OrderSide, OrderType, OrderStatus
from src.domain.value_objects.money import Money, Currency


@dataclass(frozen=True)
class SignalDecisionDTO:
    """
    SignalAnalyzer 결과를 담는 Application 계층 DTO.

    생성: AnalysisStage.execute() 내 from_signal_analysis() 호출
    소비: ExecutionStage (주문 결정), DecisionRecordPort (저장)

    Note: Stage는 Adapter에 직접 접근하지 않음.
          반드시 Application Service → Port 경로 사용.
    """
    # 결정 결과
    decision: str                    # "buy" | "hold" | "sell"
    confidence: str                  # "high" | "medium" | "low" | "very_low"
    reason: str                      # 판단 근거 요약

    # 신호 상세 (로깅/추적용)
    raw_decision: str                # 원본: "strong_buy" | "buy" | "hold" | "sell" | "strong_sell"
    total_score: float               # buy_score - sell_score
    buy_score: float
    sell_score: float
    signal_strength: float           # abs(total_score)
    signals: List[str]               # 개별 신호 목록 (최대 10개)

    # 메타데이터
    ticker: str
    current_price: Decimal
    timestamp: datetime

    @classmethod
    def from_signal_analysis(
        cls,
        ticker: str,
        price: Decimal,
        analysis: Dict[str, Any],
        timestamp: datetime,  # 외부에서 주입 (TimeProviderPort 사용)
    ) -> "SignalDecisionDTO":
        """
        SignalAnalyzer.analyze_signals() 결과에서 생성.

        Note: timestamp는 datetime.now() 직접 호출 대신
              TimeProviderPort.now()를 통해 호출자가 주입해야 함.
              이는 테스트 재현성과 시간 의존성 분리를 위함.

        Args:
            ticker: 티커 심볼 (e.g., "KRW-BTC")
            price: 현재가
            analysis: SignalAnalyzer.analyze_signals() 결과
            timestamp: 결정 시점 (TimeProviderPort에서 주입)

        Returns:
            SignalDecisionDTO 인스턴스
        """
        raw_decision = analysis["decision"]

        # strong_buy/buy → buy, strong_sell/sell → sell (동일 비용 처리)
        if raw_decision in ("strong_buy", "buy"):
            decision = "buy"
        elif raw_decision in ("strong_sell", "sell"):
            decision = "sell"
        else:
            decision = "hold"

        return cls(
            decision=decision,
            confidence=analysis["confidence"],
            reason=f"Signal: {raw_decision} (score: {analysis['total_score']:.1f})",
            raw_decision=raw_decision,
            total_score=analysis["total_score"],
            buy_score=analysis["buy_score"],
            sell_score=analysis["sell_score"],
            signal_strength=analysis["signal_strength"],
            signals=analysis["signals"][:10],  # 최대 10개
            ticker=ticker,
            current_price=price,
            timestamp=timestamp,
        )

    def is_buy_signal(self) -> bool:
        """매수 신호인지 확인."""
        return self.decision == "buy"

    def is_sell_signal(self) -> bool:
        """매도 신호인지 확인."""
        return self.decision == "sell"

    def is_hold_signal(self) -> bool:
        """홀드 신호인지 확인."""
        return self.decision == "hold"

    def get_effective_confidence(self) -> str:
        """
        ExecutionStage 호환용 confidence 반환.
        very_low는 low로 downgrade (로그/DB에는 원본 유지).
        """
        if self.confidence == "very_low":
            return "low"
        return self.confidence


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
