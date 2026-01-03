"""
IntrabarExecutionAdapter - 봉 내 체결 어댑터

Clean Architecture: Infrastructure Layer (Adapter)

문서 03_backtesting_volatility_breakout.md의 "치명적 한계" 해결:
- 봉 내(Intrabar) 스탑로스/익절 체결 시뮬레이션
- 갭 하락/상승 시 체결 가격 현실화
- 스탑/익절 동시 도달 시 worst-case 가정

주요 특징:
1. 캔들 저점이 스탑가에 도달하면 스탑 트리거 (종가 무관)
2. 갭 하락 시 시가로 체결 (더 나쁜 가격)
3. 스탑과 익절 동시 도달 시 스탑 우선 (보수적 가정)
"""
from decimal import Decimal
from typing import Literal

from src.application.ports.outbound.execution_port import (
    ExecutionPort,
    ExecutionResult,
    CandleData,
)
from src.domain.entities import OrderSide
from src.domain.value_objects import Money


class IntrabarExecutionAdapter(ExecutionPort):
    """
    봉 내(Intrabar) 체결 어댑터

    캔들의 high/low를 사용하여 봉 내 가격 도달을 시뮬레이션합니다.
    변동성돌파 전략의 리스크를 현실적으로 평가할 수 있습니다.

    Intrabar 시뮬레이션 원칙:
    1. 스탑로스: candle.low <= stop_price 이면 트리거
    2. 익절: candle.high >= take_profit 이면 트리거
    3. 갭: 시가가 스탑/익절을 넘어가면 시가로 체결
    4. 동시 도달: worst-case (스탑 우선)
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
        스탑로스 트리거 확인 (Intrabar)

        캔들 저점이 스탑가 이하면 트리거.
        종가와 무관하게 봉 중간에 스탑에 걸리면 체결됨.

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
        익절 트리거 확인 (Intrabar)

        캔들 고점이 익절가 이상이면 트리거.
        종가와 무관하게 봉 중간에 익절에 걸리면 체결됨.

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

        시나리오:
        1. candle.open < stop_price (갭 하락)
           → 시가로 체결 (스탑가보다 더 나쁜 가격)
        2. candle.open >= stop_price (정상)
           → 스탑가로 체결

        Args:
            stop_price: 스탑로스 가격
            candle: 현재 캔들 데이터

        Returns:
            Money: 실제 체결 가격
        """
        if candle.open < stop_price:
            # 갭 하락: 시가가 이미 스탑가보다 낮음
            # 실제로는 스탑가에 체결되지 않고 시가(더 나쁜 가격)로 체결
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

        시나리오:
        1. candle.open > take_profit_price (갭 상승)
           → 시가로 체결 (익절가보다 더 좋은 가격)
        2. candle.open <= take_profit_price (정상)
           → 익절가로 체결

        Args:
            take_profit_price: 익절 가격
            candle: 현재 캔들 데이터

        Returns:
            Money: 실제 체결 가격
        """
        if candle.open > take_profit_price:
            # 갭 상승: 시가가 이미 익절가보다 높음
            # 실제로는 익절가에 체결되지 않고 시가(더 좋은 가격)로 체결
            return candle.open
        else:
            # 정상: 익절가로 체결
            return take_profit_price

    def get_exit_priority(
        self,
        stop_price: Money,
        take_profit_price: Money,
        candle: CandleData
    ) -> Literal["stop_loss", "take_profit", "none"]:
        """
        스탑과 익절 동시 도달 시 우선순위 결정

        Worst-case 가정: 스탑로스 우선.

        실제 시장에서는 캔들 내 가격 순서를 알 수 없으므로,
        보수적으로 손실이 먼저 발생한다고 가정합니다.

        참고: 더 정교한 시뮬레이션을 위해서는
        tick 데이터가 필요합니다.

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

    def simulate_intrabar_exit(
        self,
        entry_price: Money,
        stop_price: Money,
        take_profit_price: Money,
        candle: CandleData,
        size: Decimal
    ) -> ExecutionResult:
        """
        봉 내 청산 시뮬레이션

        스탑/익절 트리거를 확인하고 적절한 가격으로 청산합니다.

        Args:
            entry_price: 진입 가격
            stop_price: 스탑로스 가격
            take_profit_price: 익절 가격
            candle: 현재 캔들 데이터
            size: 포지션 크기

        Returns:
            ExecutionResult: 청산 결과 (트리거 안 되면 success=False)
        """
        priority = self.get_exit_priority(stop_price, take_profit_price, candle)

        if priority == "stop_loss":
            execution_price = self.get_stop_loss_execution_price(stop_price, candle)
            slippage = entry_price - execution_price  # 손실 방향
            return ExecutionResult(
                success=True,
                executed_price=execution_price,
                executed_size=size,
                slippage=Money(abs(slippage.amount), slippage.currency),
                timestamp=candle.timestamp
            )

        elif priority == "take_profit":
            execution_price = self.get_take_profit_execution_price(
                take_profit_price, candle
            )
            slippage = execution_price - entry_price  # 이익 방향
            return ExecutionResult(
                success=True,
                executed_price=execution_price,
                executed_size=size,
                slippage=Money(abs(slippage.amount), slippage.currency),
                timestamp=candle.timestamp
            )

        else:
            # 트리거 안 됨
            return ExecutionResult.failed(
                timestamp=candle.timestamp,
                reason="No exit triggered"
            )
