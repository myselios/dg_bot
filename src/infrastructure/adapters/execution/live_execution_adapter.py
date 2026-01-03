"""
LiveExecutionAdapter - 실시간 거래용 체결 어댑터

Clean Architecture: Infrastructure Layer (Adapter)

실시간 거래를 위한 ExecutionPort 구현체.
ExchangePort를 통해 실제 거래소 API를 호출합니다.

주요 특징:
1. ExecutionPort 인터페이스 구현 (백테스트와 동일 인터페이스)
2. 실시간 가격 기반 스탑/익절 트리거 확인
3. ExchangePort를 통한 실제 주문 실행
4. 슬리피지 계산 및 반영

사용 예:
```python
from src.container import Container

container = Container()
exchange_port = container.get_exchange_port()
execution_adapter = LiveExecutionAdapter(exchange_port=exchange_port)

# 실시간 스탑로스 확인
if await execution_adapter.check_stop_loss_triggered_realtime(ticker, stop_price):
    await execution_adapter.execute_market_sell_realtime(ticker, volume)
```
"""
from decimal import Decimal
from typing import Literal

from src.application.ports.outbound.execution_port import (
    ExecutionPort,
    ExecutionResult,
    CandleData,
)
from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.dto.trading import OrderResponse
from src.domain.entities import OrderSide
from src.domain.value_objects import Money


class LiveExecutionAdapter(ExecutionPort):
    """
    실시간 거래용 체결 어댑터

    ExecutionPort 인터페이스를 구현하며, ExchangePort를 통해
    실제 거래소 API를 호출합니다.

    백테스트의 IntrabarExecutionAdapter와 동일한 인터페이스를 제공하여
    라이브/백테스트 간 전환이 용이합니다.

    Attributes:
        _exchange: ExchangePort 인스턴스 (실제 거래소 연동)
    """

    def __init__(self, exchange_port: ExchangePort):
        """
        초기화

        Args:
            exchange_port: 거래소 포트 (실제 API 연동)
        """
        self._exchange = exchange_port

    # ============================================================
    # ExecutionPort 인터페이스 구현 (백테스트 호환)
    # ============================================================

    def execute_market_order(
        self,
        side: OrderSide,
        size: Decimal,
        expected_price: Money,
        candle: CandleData,
        slippage_pct: Decimal = Decimal("0.0001")
    ) -> ExecutionResult:
        """
        시장가 주문 체결 (백테스트 호환 인터페이스)

        라이브에서는 캔들 데이터가 현재 상태를 나타냅니다.
        시가를 기준으로 슬리피지를 적용합니다.

        Args:
            side: 주문 방향 (BUY/SELL)
            size: 주문 수량
            expected_price: 예상 체결가
            candle: 현재 상태 캔들 (시가=현재가)
            slippage_pct: 슬리피지 비율 (기본 0.01%)

        Returns:
            ExecutionResult: 체결 결과
        """
        base_price = candle.open

        if side == OrderSide.BUY:
            # 매수: 슬리피지로 인해 더 높은 가격
            executed_price = Money(
                base_price.amount * (1 + slippage_pct),
                base_price.currency
            )
        else:
            # 매도: 슬리피지로 인해 더 낮은 가격
            executed_price = Money(
                base_price.amount * (1 - slippage_pct),
                base_price.currency
            )

        slippage = Money(
            abs(executed_price.amount - expected_price.amount),
            expected_price.currency
        )

        return ExecutionResult(
            success=True,
            executed_price=executed_price,
            executed_size=size,
            slippage=slippage,
            timestamp=candle.timestamp
        )

    def check_stop_loss_triggered(
        self,
        stop_price: Money,
        candle: CandleData
    ) -> bool:
        """
        스탑로스 트리거 확인 (캔들 기반)

        캔들 저점이 스탑가 이하면 트리거.
        IntrabarExecutionAdapter와 동일한 로직.

        Args:
            stop_price: 스탑로스 가격
            candle: 현재 캔들 데이터

        Returns:
            bool: 트리거 여부
        """
        return candle.low <= stop_price

    def check_take_profit_triggered(
        self,
        take_profit_price: Money,
        candle: CandleData
    ) -> bool:
        """
        익절 트리거 확인 (캔들 기반)

        캔들 고점이 익절가 이상이면 트리거.
        IntrabarExecutionAdapter와 동일한 로직.

        Args:
            take_profit_price: 익절 가격
            candle: 현재 캔들 데이터

        Returns:
            bool: 트리거 여부
        """
        return candle.high >= take_profit_price

    def get_stop_loss_execution_price(
        self,
        stop_price: Money,
        candle: CandleData
    ) -> Money:
        """
        스탑로스 체결 가격 계산

        갭 하락 시 시가로 체결 (더 나쁜 가격).
        정상적인 경우 스탑가로 체결.

        Args:
            stop_price: 스탑로스 가격
            candle: 현재 캔들 데이터

        Returns:
            Money: 실제 체결 가격
        """
        if candle.open < stop_price:
            # 갭 하락: 시가가 이미 스탑가보다 낮음
            return candle.open
        else:
            # 정상: 스탑가로 체결
            return stop_price

    def get_take_profit_execution_price(
        self,
        take_profit_price: Money,
        candle: CandleData
    ) -> Money:
        """
        익절 체결 가격 계산

        갭 상승 시 시가로 체결 (더 좋은 가격).
        정상적인 경우 익절가로 체결.

        Args:
            take_profit_price: 익절 가격
            candle: 현재 캔들 데이터

        Returns:
            Money: 실제 체결 가격
        """
        if candle.open > take_profit_price:
            # 갭 상승: 시가가 이미 익절가보다 높음
            return candle.open
        else:
            # 정상: 익절가로 체결
            return take_profit_price

    # ============================================================
    # 실시간 거래 전용 메서드 (ExchangePort 활용)
    # ============================================================

    async def check_stop_loss_triggered_realtime(
        self,
        ticker: str,
        stop_price: Money
    ) -> bool:
        """
        실시간 가격 기반 스탑로스 트리거 확인

        ExchangePort를 통해 현재가를 조회하고
        스탑가와 비교합니다.

        Args:
            ticker: 거래쌍 (예: "KRW-BTC")
            stop_price: 스탑로스 가격

        Returns:
            bool: 트리거 여부 (현재가 <= 스탑가)
        """
        current_price = await self._exchange.get_current_price(ticker)
        return current_price <= stop_price

    async def check_take_profit_triggered_realtime(
        self,
        ticker: str,
        take_profit_price: Money
    ) -> bool:
        """
        실시간 가격 기반 익절 트리거 확인

        ExchangePort를 통해 현재가를 조회하고
        익절가와 비교합니다.

        Args:
            ticker: 거래쌍 (예: "KRW-BTC")
            take_profit_price: 익절 가격

        Returns:
            bool: 트리거 여부 (현재가 >= 익절가)
        """
        current_price = await self._exchange.get_current_price(ticker)
        return current_price >= take_profit_price

    async def execute_market_buy_realtime(
        self,
        ticker: str,
        amount: Money
    ) -> OrderResponse:
        """
        실시간 시장가 매수 실행

        ExchangePort를 통해 실제 거래소에
        시장가 매수 주문을 전송합니다.

        Args:
            ticker: 거래쌍 (예: "KRW-BTC")
            amount: 매수 금액 (KRW)

        Returns:
            OrderResponse: 주문 응답
        """
        return await self._exchange.execute_market_buy(ticker, amount)

    async def execute_market_sell_realtime(
        self,
        ticker: str,
        volume: Decimal
    ) -> OrderResponse:
        """
        실시간 시장가 매도 실행

        ExchangePort를 통해 실제 거래소에
        시장가 매도 주문을 전송합니다.

        Args:
            ticker: 거래쌍 (예: "KRW-BTC")
            volume: 매도 수량

        Returns:
            OrderResponse: 주문 응답
        """
        return await self._exchange.execute_market_sell(ticker, volume)

    async def get_current_price(self, ticker: str) -> Money:
        """
        현재가 조회

        Args:
            ticker: 거래쌍 (예: "KRW-BTC")

        Returns:
            Money: 현재가
        """
        return await self._exchange.get_current_price(ticker)

    def get_exit_priority(
        self,
        stop_price: Money,
        take_profit_price: Money,
        candle: CandleData
    ) -> Literal["stop_loss", "take_profit", "none"]:
        """
        스탑과 익절 동시 도달 시 우선순위 결정

        Worst-case 가정: 스탑로스 우선.

        Args:
            stop_price: 스탑로스 가격
            take_profit_price: 익절 가격
            candle: 현재 캔들 데이터

        Returns:
            "stop_loss": 스탑 우선
            "take_profit": 익절 우선
            "none": 둘 다 트리거 안 됨
        """
        stop_triggered = self.check_stop_loss_triggered(stop_price, candle)
        tp_triggered = self.check_take_profit_triggered(take_profit_price, candle)

        if stop_triggered and tp_triggered:
            # 둘 다 트리거: worst-case 가정 (스탑 우선)
            return "stop_loss"
        elif stop_triggered:
            return "stop_loss"
        elif tp_triggered:
            return "take_profit"
        else:
            return "none"
