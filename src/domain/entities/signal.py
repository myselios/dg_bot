"""
Signal Entity - 거래 신호

백테스팅과 실거래 모두에서 사용되는 거래 신호 엔티티.
datetime.now() 대신 명시적인 timestamp를 사용하여 시간축 왜곡 방지.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Union

from src.domain.value_objects import Money, Currency, Percentage


class SignalAction(Enum):
    """거래 신호 액션 타입"""
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    HOLD = "hold"


@dataclass
class Signal:
    """
    거래 신호 엔티티

    Clean Architecture 원칙:
    - datetime.now() 사용 금지 (시간축 왜곡 방지)
    - timestamp는 외부에서 주입 (캔들 시간 또는 None)
    - Value Objects 사용 (Money, Percentage)

    Attributes:
        action: 거래 액션 (BUY, SELL, CLOSE, HOLD)
        price: 신호 발생 시점 가격
        size: 거래 수량 (옵션)
        stop_loss: 손절가 (옵션)
        take_profit: 익절가 (옵션)
        reason: 신호 발생 이유 (딕셔너리)
        timestamp: 신호 발생 시간 (캔들 시간, None=미지정)
        split_recommendation: 분할 주문 권장사항 (옵션)
        expected_slippage: 예상 슬리피지 (옵션)
    """
    action: SignalAction
    price: Money
    size: Optional[Decimal] = None
    stop_loss: Optional[Money] = None
    take_profit: Optional[Money] = None
    reason: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None  # 중요: datetime.now() 사용 안 함
    split_recommendation: Optional[Dict[str, Any]] = None
    expected_slippage: Optional[Percentage] = None

    # --- Computed Properties ---

    @property
    def risk_reward_ratio(self) -> Optional[Decimal]:
        """
        손익비 (Risk/Reward Ratio) 계산

        Returns:
            손익비 (예: 2.0 = 2:1), 계산 불가시 None
        """
        if self.stop_loss is None or self.take_profit is None:
            return None

        risk = self.price.amount - self.stop_loss.amount
        reward = self.take_profit.amount - self.price.amount

        if risk <= 0:
            return None

        return (reward / risk).quantize(Decimal("0.1"))

    @property
    def risk_percentage(self) -> Optional[Percentage]:
        """
        진입가 대비 리스크 비율 계산

        Returns:
            리스크 퍼센티지, 계산 불가시 None
        """
        if self.stop_loss is None or self.price.amount <= 0:
            return None

        risk_decimal = (self.price.amount - self.stop_loss.amount) / self.price.amount
        return Percentage.from_points(risk_decimal * 100)

    @property
    def reward_percentage(self) -> Optional[Percentage]:
        """
        진입가 대비 리워드 비율 계산

        Returns:
            리워드 퍼센티지, 계산 불가시 None
        """
        if self.take_profit is None or self.price.amount <= 0:
            return None

        reward_decimal = (self.take_profit.amount - self.price.amount) / self.price.amount
        return Percentage.from_points(reward_decimal * 100)

    # --- Factory Methods ---

    @classmethod
    def from_legacy(cls, data: Dict[str, Any]) -> Signal:
        """
        레거시 딕셔너리에서 Signal 생성

        기존 backtesting/strategy.py의 Signal과 호환.

        Args:
            data: 레거시 형식 딕셔너리
                {
                    "action": "buy",
                    "price": 50000000,
                    "stop_loss": 49000000,
                    "take_profit": 52000000,
                    "reason": {...}
                }

        Returns:
            Signal 객체
        """
        action_str = data.get("action", "hold").lower()
        action = SignalAction(action_str)

        price = Money.krw(data["price"]) if "price" in data else Money.krw(0)

        stop_loss = None
        if data.get("stop_loss") is not None:
            stop_loss = Money.krw(data["stop_loss"])

        take_profit = None
        if data.get("take_profit") is not None:
            take_profit = Money.krw(data["take_profit"])

        size = None
        if data.get("size") is not None:
            size = Decimal(str(data["size"]))

        reason = data.get("reason", {})

        timestamp = None
        if data.get("timestamp") is not None:
            ts = data["timestamp"]
            if isinstance(ts, datetime):
                timestamp = ts
            elif isinstance(ts, str):
                timestamp = datetime.fromisoformat(ts)

        return cls(
            action=action,
            price=price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            timestamp=timestamp
        )

    def to_legacy(self) -> Dict[str, Any]:
        """
        레거시 호환 딕셔너리로 변환

        기존 backtesting/strategy.py의 Signal과 호환.

        Returns:
            레거시 형식 딕셔너리
        """
        result: Dict[str, Any] = {
            "action": self.action.value,
            "price": int(self.price.amount) if self.price else 0,
        }

        if self.size is not None:
            result["size"] = float(self.size)

        if self.stop_loss is not None:
            result["stop_loss"] = int(self.stop_loss.amount)

        if self.take_profit is not None:
            result["take_profit"] = int(self.take_profit.amount)

        if self.reason:
            result["reason"] = self.reason

        if self.timestamp is not None:
            result["timestamp"] = self.timestamp

        return result

    # --- Static Factory Methods for Common Signals ---

    @classmethod
    def buy(
        cls,
        price: Union[Money, int, float],
        stop_loss: Optional[Union[Money, int, float]] = None,
        take_profit: Optional[Union[Money, int, float]] = None,
        size: Optional[Decimal] = None,
        reason: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Signal:
        """매수 신호 생성 헬퍼"""
        if not isinstance(price, Money):
            price = Money.krw(price)
        if stop_loss is not None and not isinstance(stop_loss, Money):
            stop_loss = Money.krw(stop_loss)
        if take_profit is not None and not isinstance(take_profit, Money):
            take_profit = Money.krw(take_profit)

        return cls(
            action=SignalAction.BUY,
            price=price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason or {},
            timestamp=timestamp
        )

    @classmethod
    def sell(
        cls,
        price: Union[Money, int, float],
        reason: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Signal:
        """매도 신호 생성 헬퍼"""
        if not isinstance(price, Money):
            price = Money.krw(price)

        return cls(
            action=SignalAction.SELL,
            price=price,
            reason=reason or {},
            timestamp=timestamp
        )

    @classmethod
    def close(
        cls,
        price: Union[Money, int, float],
        reason: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Signal:
        """청산 신호 생성 헬퍼"""
        if not isinstance(price, Money):
            price = Money.krw(price)

        return cls(
            action=SignalAction.CLOSE,
            price=price,
            reason=reason or {},
            timestamp=timestamp
        )

    @classmethod
    def hold(cls) -> Signal:
        """홀드 신호 생성 헬퍼"""
        return cls(
            action=SignalAction.HOLD,
            price=Money.krw(0)
        )

    # --- Utility Methods ---

    def is_buy(self) -> bool:
        """매수 신호 여부"""
        return self.action == SignalAction.BUY

    def is_sell(self) -> bool:
        """매도 신호 여부"""
        return self.action == SignalAction.SELL

    def is_close(self) -> bool:
        """청산 신호 여부"""
        return self.action == SignalAction.CLOSE

    def is_hold(self) -> bool:
        """홀드 신호 여부"""
        return self.action == SignalAction.HOLD

    def has_stop_loss(self) -> bool:
        """손절가 설정 여부"""
        return self.stop_loss is not None

    def has_take_profit(self) -> bool:
        """익절가 설정 여부"""
        return self.take_profit is not None

    def __str__(self) -> str:
        """문자열 표현"""
        parts = [f"{self.action.value.upper()} @ {self.price}"]
        if self.stop_loss:
            parts.append(f"SL: {self.stop_loss}")
        if self.take_profit:
            parts.append(f"TP: {self.take_profit}")
        return " | ".join(parts)
