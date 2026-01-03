"""
SimpleExecutionAdapter - 기존 방식의 체결 어댑터

Clean Architecture: Infrastructure Layer (Adapter)

기존 백테스팅 로직과 동일한 방식:
- 시가/종가로만 체결
- 봉 내 스탑/익절 무시 (종가 기준)

한계:
- 봉 중간에 스탑에 걸렸어도 종가가 스탑 위면 무시
- 변동성돌파 전략의 리스크 과소평가
"""
from decimal import Decimal

from src.application.ports.outbound.execution_port import (
    ExecutionPort,
    ExecutionResult,
    CandleData,
)
from src.domain.entities import OrderSide
from src.domain.value_objects import Money


class SimpleExecutionAdapter(ExecutionPort):
    """
    기존 방식의 체결 어댑터

    종가 기준으로만 스탑/익절을 판단합니다.
    봉 내 가격 변동은 무시됩니다.
    """

    def execute_market_order(
        self,
        side: OrderSide,
        size: Decimal,
        expected_price: Money,
        candle: CandleData,
        slippage_pct: Decimal = Decimal("0.0001")
    ) -> ExecutionResult:
        """
        시장가 주문 체결

        시가로 체결하고 슬리피지를 적용합니다.
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
        스탑로스 트리거 확인 (종가 기준)

        기존 방식: 종가가 스탑가 이하일 때만 트리거.
        봉 중간에 스탑에 걸렸어도 종가가 회복되면 무시.
        """
        return candle.close <= stop_price

    def check_take_profit_triggered(
        self,
        take_profit_price: Money,
        candle: CandleData
    ) -> bool:
        """
        익절 트리거 확인 (종가 기준)

        기존 방식: 종가가 익절가 이상일 때만 트리거.
        """
        return candle.close >= take_profit_price

    def get_stop_loss_execution_price(
        self,
        stop_price: Money,
        candle: CandleData
    ) -> Money:
        """
        스탑로스 체결 가격 (종가)

        기존 방식: 단순히 종가로 체결.
        """
        return candle.close

    def get_take_profit_execution_price(
        self,
        take_profit_price: Money,
        candle: CandleData
    ) -> Money:
        """
        익절 체결 가격 (종가)

        기존 방식: 단순히 종가로 체결.
        """
        return candle.close
