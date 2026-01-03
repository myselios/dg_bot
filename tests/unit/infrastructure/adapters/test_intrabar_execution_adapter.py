"""
IntrabarExecutionAdapter 테스트

TDD: Red → Green → Refactor

봉 내(Intrabar) 스탑로스/익절 체결을 현실적으로 시뮬레이션.
문서 03_backtesting_volatility_breakout.md의 "치명적 한계" 해결.
"""
import pytest
from datetime import datetime
from decimal import Decimal

from src.infrastructure.adapters.execution.intrabar_execution_adapter import (
    IntrabarExecutionAdapter,
)
from src.application.ports.outbound.execution_port import CandleData, ExecutionResult
from src.domain.entities import OrderSide
from src.domain.value_objects import Money


class TestIntrabarStopLoss:
    """Intrabar 스탑로스 테스트"""

    @pytest.fixture
    def adapter(self):
        return IntrabarExecutionAdapter()

    def test_stop_loss_triggered_when_low_reaches_stop(self, adapter):
        """Given: 캔들 저점이 스탑가 이하
        When: check_stop_loss_triggered 호출
        Then: True 반환"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(50500000),
            low=Money.krw(48500000),  # 스탑가(49000000)보다 낮음
            close=Money.krw(49000000),
            volume=Decimal("100.5")
        )
        stop_price = Money.krw(49000000)

        assert adapter.check_stop_loss_triggered(stop_price, candle) is True

    def test_stop_loss_not_triggered_when_low_above_stop(self, adapter):
        """Given: 캔들 저점이 스탑가 위
        When: check_stop_loss_triggered 호출
        Then: False 반환"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49500000),  # 스탑가(49000000)보다 높음
            close=Money.krw(50500000),
            volume=Decimal("100.5")
        )
        stop_price = Money.krw(49000000)

        assert adapter.check_stop_loss_triggered(stop_price, candle) is False

    def test_stop_loss_execution_price_normal(self, adapter):
        """Given: 갭 없이 스탑 도달
        When: get_stop_loss_execution_price 호출
        Then: 스탑가로 체결"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),  # 시가 > 스탑가
            high=Money.krw(50500000),
            low=Money.krw(48500000),
            close=Money.krw(49000000),
            volume=Decimal("100.5")
        )
        stop_price = Money.krw(49000000)

        execution_price = adapter.get_stop_loss_execution_price(stop_price, candle)

        assert execution_price == Money.krw(49000000)  # 스탑가로 체결

    def test_stop_loss_execution_price_gap_down(self, adapter):
        """Given: 갭 하락으로 시가가 스탑가보다 낮음
        When: get_stop_loss_execution_price 호출
        Then: 시가로 체결 (더 나쁜 가격)"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(48000000),  # 시가 < 스탑가 (갭 하락)
            high=Money.krw(48500000),
            low=Money.krw(47000000),
            close=Money.krw(47500000),
            volume=Decimal("100.5")
        )
        stop_price = Money.krw(49000000)

        execution_price = adapter.get_stop_loss_execution_price(stop_price, candle)

        # 갭 하락 시 시가로 체결 (더 나쁜 가격)
        assert execution_price == Money.krw(48000000)


class TestIntrabarTakeProfit:
    """Intrabar 익절 테스트"""

    @pytest.fixture
    def adapter(self):
        return IntrabarExecutionAdapter()

    def test_take_profit_triggered_when_high_reaches_tp(self, adapter):
        """Given: 캔들 고점이 익절가 이상
        When: check_take_profit_triggered 호출
        Then: True 반환"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(52500000),  # 익절가(52000000)보다 높음
            low=Money.krw(49500000),
            close=Money.krw(52000000),
            volume=Decimal("100.5")
        )
        take_profit = Money.krw(52000000)

        assert adapter.check_take_profit_triggered(take_profit, candle) is True

    def test_take_profit_not_triggered_when_high_below_tp(self, adapter):
        """Given: 캔들 고점이 익절가 미만
        When: check_take_profit_triggered 호출
        Then: False 반환"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51500000),  # 익절가(52000000)보다 낮음
            low=Money.krw(49500000),
            close=Money.krw(51000000),
            volume=Decimal("100.5")
        )
        take_profit = Money.krw(52000000)

        assert adapter.check_take_profit_triggered(take_profit, candle) is False

    def test_take_profit_execution_price_normal(self, adapter):
        """Given: 갭 없이 익절 도달
        When: get_take_profit_execution_price 호출
        Then: 익절가로 체결"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(51000000),  # 시가 < 익절가
            high=Money.krw(53000000),
            low=Money.krw(50500000),
            close=Money.krw(52500000),
            volume=Decimal("100.5")
        )
        take_profit = Money.krw(52000000)

        execution_price = adapter.get_take_profit_execution_price(take_profit, candle)

        assert execution_price == Money.krw(52000000)  # 익절가로 체결

    def test_take_profit_execution_price_gap_up(self, adapter):
        """Given: 갭 상승으로 시가가 익절가보다 높음
        When: get_take_profit_execution_price 호출
        Then: 시가로 체결 (더 좋은 가격)"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(53000000),  # 시가 > 익절가 (갭 상승)
            high=Money.krw(54000000),
            low=Money.krw(52500000),
            close=Money.krw(53500000),
            volume=Decimal("100.5")
        )
        take_profit = Money.krw(52000000)

        execution_price = adapter.get_take_profit_execution_price(take_profit, candle)

        # 갭 상승 시 시가로 체결 (더 좋은 가격)
        assert execution_price == Money.krw(53000000)


class TestIntrabarBothTriggered:
    """스탑과 익절이 동시에 도달하는 경우 (Worst-case)"""

    @pytest.fixture
    def adapter(self):
        return IntrabarExecutionAdapter()

    def test_both_triggered_stop_takes_priority(self, adapter):
        """Given: 스탑과 익절 모두 도달 가능한 큰 변동
        When: 어떤 것이 먼저 체결되는지 확인
        Then: 스탑로스 우선 (Worst-case 가정)"""
        # 매우 큰 변동폭 캔들 - 스탑과 익절 모두 도달
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(53000000),  # 익절가 52000000 도달
            low=Money.krw(48000000),   # 스탑가 49000000 도달
            close=Money.krw(51000000),
            volume=Decimal("200.0")
        )
        stop_price = Money.krw(49000000)
        take_profit = Money.krw(52000000)

        # 둘 다 트리거됨
        stop_triggered = adapter.check_stop_loss_triggered(stop_price, candle)
        tp_triggered = adapter.check_take_profit_triggered(take_profit, candle)

        assert stop_triggered is True
        assert tp_triggered is True

        # Worst-case: 스탑이 먼저 체결된다고 가정
        priority = adapter.get_exit_priority(stop_price, take_profit, candle)
        assert priority == "stop_loss"


class TestMarketOrderExecution:
    """시장가 주문 체결 테스트"""

    @pytest.fixture
    def adapter(self):
        return IntrabarExecutionAdapter()

    def test_buy_market_order_with_slippage(self, adapter):
        """Given: 매수 시장가 주문
        When: execute_market_order 호출
        Then: 슬리피지 적용된 가격으로 체결"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49500000),
            close=Money.krw(50500000),
            volume=Decimal("100.5")
        )

        result = adapter.execute_market_order(
            side=OrderSide.BUY,
            size=Decimal("0.001"),
            expected_price=Money.krw(50000000),
            candle=candle,
            slippage_pct=Decimal("0.001")  # 0.1%
        )

        assert result.success is True
        assert result.executed_size == Decimal("0.001")
        # 매수 시 슬리피지로 인해 더 높은 가격에 체결
        assert result.executed_price > Money.krw(50000000)

    def test_sell_market_order_with_slippage(self, adapter):
        """Given: 매도 시장가 주문
        When: execute_market_order 호출
        Then: 슬리피지 적용된 가격으로 체결"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49500000),
            close=Money.krw(50500000),
            volume=Decimal("100.5")
        )

        result = adapter.execute_market_order(
            side=OrderSide.SELL,
            size=Decimal("0.001"),
            expected_price=Money.krw(50000000),
            candle=candle,
            slippage_pct=Decimal("0.001")  # 0.1%
        )

        assert result.success is True
        # 매도 시 슬리피지로 인해 더 낮은 가격에 체결
        assert result.executed_price < Money.krw(50000000)


class TestSimpleExecutionAdapter:
    """기존 방식(SimpleExecutionAdapter) 비교 테스트"""

    def test_simple_adapter_ignores_intrabar_stop(self):
        """Given: 기존 Simple 어댑터
        When: 봉 내 스탑 도달했지만 종가는 스탑 위
        Then: 스탑 트리거 안 됨 (기존 방식의 한계)

        이 테스트는 IntrabarExecutionAdapter의 필요성을 보여줍니다.
        기존 방식에서는 종가로만 체결을 판단하므로
        봉 중간에 스탑에 걸렸어도 무시됩니다.
        """
        from src.infrastructure.adapters.execution.simple_execution_adapter import (
            SimpleExecutionAdapter,
        )

        adapter = SimpleExecutionAdapter()

        # 봉 중간에 스탑 도달했지만 종가는 스탑 위
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(50500000),
            low=Money.krw(48500000),  # 스탑가 49000000 아래로 내려감!
            close=Money.krw(50000000),  # 하지만 종가는 스탑 위로 회복
            volume=Decimal("100.5")
        )
        stop_price = Money.krw(49000000)

        # Simple 어댑터는 종가 기준이므로 스탑 트리거 안 됨
        assert adapter.check_stop_loss_triggered(stop_price, candle) is False

        # 반면 Intrabar 어댑터는 트리거됨
        intrabar_adapter = IntrabarExecutionAdapter()
        assert intrabar_adapter.check_stop_loss_triggered(stop_price, candle) is True
