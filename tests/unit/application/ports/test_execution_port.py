"""
ExecutionPort 인터페이스 테스트

TDD: Red → Green → Refactor

백테스팅 체결 모델의 핵심 포트.
다양한 체결 어댑터 (Simple, Intrabar) 교체 가능.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass

from src.application.ports.outbound.execution_port import (
    ExecutionPort,
    ExecutionResult,
    CandleData,
)
from src.domain.entities import OrderSide
from src.domain.value_objects import Money


class TestCandleData:
    """CandleData DTO 테스트"""

    def test_create_candle_data(self):
        """Given: OHLCV 데이터
        When: CandleData 생성
        Then: 올바른 속성 설정"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49000000),
            close=Money.krw(50500000),
            volume=Decimal("100.5")
        )

        assert candle.timestamp == datetime(2026, 1, 3, 10, 0, 0)
        assert candle.open == Money.krw(50000000)
        assert candle.high == Money.krw(51000000)
        assert candle.low == Money.krw(49000000)
        assert candle.close == Money.krw(50500000)
        assert candle.volume == Decimal("100.5")

    def test_candle_range(self):
        """Given: 캔들 데이터
        When: range 계산
        Then: high - low 반환"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49000000),
            close=Money.krw(50500000),
            volume=Decimal("100.5")
        )

        assert candle.range == Money.krw(2000000)

    def test_candle_is_bullish(self):
        """Given: 상승 캔들 (close > open)
        When: is_bullish 확인
        Then: True 반환"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49000000),
            close=Money.krw(50500000),  # close > open
            volume=Decimal("100.5")
        )

        assert candle.is_bullish is True
        assert candle.is_bearish is False

    def test_candle_is_bearish(self):
        """Given: 하락 캔들 (close < open)
        When: is_bearish 확인
        Then: True 반환"""
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50500000),
            high=Money.krw(51000000),
            low=Money.krw(49000000),
            close=Money.krw(50000000),  # close < open
            volume=Decimal("100.5")
        )

        assert candle.is_bullish is False
        assert candle.is_bearish is True


class TestExecutionResult:
    """ExecutionResult DTO 테스트"""

    def test_successful_execution(self):
        """Given: 체결 성공 파라미터
        When: ExecutionResult 생성
        Then: 성공 상태"""
        result = ExecutionResult(
            success=True,
            executed_price=Money.krw(50100000),
            executed_size=Decimal("0.001"),
            slippage=Money.krw(100000),
            timestamp=datetime(2026, 1, 3, 10, 0, 0)
        )

        assert result.success is True
        assert result.executed_price == Money.krw(50100000)
        assert result.executed_size == Decimal("0.001")
        assert result.slippage == Money.krw(100000)
        assert result.failure_reason is None

    def test_failed_execution(self):
        """Given: 체결 실패 파라미터
        When: ExecutionResult 생성
        Then: 실패 상태 및 이유"""
        result = ExecutionResult(
            success=False,
            executed_price=None,
            executed_size=None,
            slippage=None,
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            failure_reason="Insufficient funds"
        )

        assert result.success is False
        assert result.executed_price is None
        assert result.failure_reason == "Insufficient funds"


class TestExecutionPort:
    """ExecutionPort 인터페이스 테스트 (Mock 구현)"""

    def test_execution_port_is_abstract(self):
        """Given: ExecutionPort 추상 클래스
        When: 직접 인스턴스화 시도
        Then: TypeError 발생"""
        with pytest.raises(TypeError):
            ExecutionPort()

    def test_execute_market_order_interface(self):
        """Given: ExecutionPort 구현체
        When: execute_market_order 호출
        Then: ExecutionResult 반환"""

        class MockExecutionAdapter(ExecutionPort):
            def execute_market_order(
                self,
                side: OrderSide,
                size: Decimal,
                expected_price: Money,
                candle: CandleData,
                slippage_pct: Decimal = Decimal("0.0001")
            ) -> ExecutionResult:
                # 간단한 mock: 시가로 체결
                executed_price = candle.open
                if side == OrderSide.BUY:
                    executed_price = Money(
                        candle.open.amount * (1 + slippage_pct),
                        candle.open.currency
                    )
                else:
                    executed_price = Money(
                        candle.open.amount * (1 - slippage_pct),
                        candle.open.currency
                    )

                return ExecutionResult(
                    success=True,
                    executed_price=executed_price,
                    executed_size=size,
                    slippage=Money(
                        abs(executed_price.amount - expected_price.amount),
                        expected_price.currency
                    ),
                    timestamp=candle.timestamp
                )

            def check_stop_loss_triggered(
                self,
                stop_price: Money,
                candle: CandleData
            ) -> bool:
                return candle.low <= stop_price

            def check_take_profit_triggered(
                self,
                take_profit_price: Money,
                candle: CandleData
            ) -> bool:
                return candle.high >= take_profit_price

            def get_stop_loss_execution_price(
                self,
                stop_price: Money,
                candle: CandleData
            ) -> Money:
                if candle.open < stop_price:
                    return candle.open  # 갭 하락 시 시가로 체결
                return stop_price

            def get_take_profit_execution_price(
                self,
                take_profit_price: Money,
                candle: CandleData
            ) -> Money:
                if candle.open > take_profit_price:
                    return candle.open  # 갭 상승 시 시가로 체결
                return take_profit_price

        adapter = MockExecutionAdapter()
        candle = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49000000),
            close=Money.krw(50500000),
            volume=Decimal("100.5")
        )

        result = adapter.execute_market_order(
            side=OrderSide.BUY,
            size=Decimal("0.001"),
            expected_price=Money.krw(50000000),
            candle=candle
        )

        assert result.success is True
        assert result.executed_size == Decimal("0.001")

    def test_check_stop_loss_triggered(self):
        """Given: 스탑로스 가격과 캔들
        When: check_stop_loss_triggered 호출
        Then: 트리거 여부 반환"""

        class MockExecutionAdapter(ExecutionPort):
            def execute_market_order(self, *args, **kwargs):
                pass

            def check_stop_loss_triggered(
                self,
                stop_price: Money,
                candle: CandleData
            ) -> bool:
                # 캔들 저점이 스탑 가격 이하면 트리거
                return candle.low <= stop_price

            def check_take_profit_triggered(self, *args, **kwargs):
                pass

            def get_stop_loss_execution_price(self, *args, **kwargs):
                pass

            def get_take_profit_execution_price(self, *args, **kwargs):
                pass

        adapter = MockExecutionAdapter()

        # 스탑로스 트리거되는 캔들
        candle_triggered = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(50500000),
            low=Money.krw(48500000),  # 스탑가보다 낮음
            close=Money.krw(49000000),
            volume=Decimal("100.5")
        )

        # 스탑로스 트리거 안 되는 캔들
        candle_not_triggered = CandleData(
            timestamp=datetime(2026, 1, 3, 10, 0, 0),
            open=Money.krw(50000000),
            high=Money.krw(51000000),
            low=Money.krw(49500000),  # 스탑가보다 높음
            close=Money.krw(50500000),
            volume=Decimal("100.5")
        )

        stop_price = Money.krw(49000000)

        assert adapter.check_stop_loss_triggered(stop_price, candle_triggered) is True
        assert adapter.check_stop_loss_triggered(stop_price, candle_not_triggered) is False
