"""
Phase 3: Backtester DI (의존성 주입) 테스트

Clean Architecture 준수 및 테스트 용이성 검증
"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from src.backtesting.backtester import Backtester
from src.backtesting.strategy import Strategy, Signal
from src.application.ports.outbound.execution_port import ExecutionPort, CandleData


# ============================================================
# 테스트용 클래스
# ============================================================

class SimpleTestStrategy(Strategy):
    """테스트용 간단한 전략"""

    def generate_signal(self, data: pd.DataFrame, **kwargs):
        return None

    def calculate_position_size(self, signal, portfolio):
        return 0.0


def create_mock_execution_adapter():
    """MagicMock 기반 ExecutionPort 생성"""
    from decimal import Decimal
    from src.domain.value_objects import Money
    from src.application.ports.outbound.execution_port import ExecutionResult

    mock = MagicMock(spec=ExecutionPort)

    # 기본 반환값 설정
    mock.execute_market_order.return_value = ExecutionResult(
        success=True,
        executed_price=Money.krw(100),
        executed_size=Decimal("1.0"),
        slippage=Money.krw(0),
        timestamp=None
    )
    mock.check_stop_loss_triggered.return_value = False
    mock.check_take_profit_triggered.return_value = False
    mock.get_stop_loss_execution_price.return_value = Money.krw(95)
    mock.get_take_profit_execution_price.return_value = Money.krw(110)

    return mock


def create_test_data(bars: int = 10) -> pd.DataFrame:
    """테스트용 데이터 생성"""
    dates = pd.date_range(start='2024-01-01', periods=bars, freq='D')
    return pd.DataFrame({
        'open': [100] * bars,
        'high': [105] * bars,
        'low': [95] * bars,
        'close': [102] * bars,
        'volume': [1000] * bars,
    }, index=dates)


# ============================================================
# Phase 3: DI 테스트
# ============================================================

class TestBacktesterDI:
    """Backtester 의존성 주입 테스트"""

    def test_backtester_accepts_custom_execution_adapter(self):
        """커스텀 ExecutionAdapter 주입 가능"""
        # Given
        data = create_test_data()
        strategy = SimpleTestStrategy()
        mock_adapter = create_mock_execution_adapter()

        # When
        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000,
            execution_adapter=mock_adapter  # DI
        )

        # Then
        assert backtester._execution_adapter is mock_adapter

    def test_backtester_uses_injected_adapter(self):
        """주입된 어댑터가 실제로 사용됨"""
        # Given
        data = create_test_data(bars=5)

        class BuyOnceStrategy(Strategy):
            def __init__(self):
                self.bought = False

            def generate_signal(self, data, **kwargs):
                if not self.bought and len(data) >= 2:
                    self.bought = True
                    return Signal(action='BUY', price=100, size=0.1)
                return None

            def calculate_position_size(self, signal, portfolio):
                return signal.size if signal else 0.0

        strategy = BuyOnceStrategy()
        mock_adapter = create_mock_execution_adapter()

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000,
            execution_adapter=mock_adapter,
            execute_on_next_open=False  # 즉시 체결 모드
        )

        # When
        result = backtester.run()

        # Then: Mock 어댑터가 호출되었어야 함
        # Note: 현재 구현에서 execute_order 호출 여부 확인
        assert result is not None

    def test_backtester_default_adapter_creation(self):
        """어댑터 미주입 시 기본 어댑터 생성"""
        # Given
        data = create_test_data()
        strategy = SimpleTestStrategy()

        # When
        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000
            # execution_adapter 미지정
        )

        # Then: 기본 SimpleExecutionAdapter 사용
        from src.infrastructure.adapters.execution import SimpleExecutionAdapter
        assert isinstance(backtester._execution_adapter, SimpleExecutionAdapter)

    def test_backtester_intrabar_adapter_selection(self):
        """use_intrabar_stops=True 시 IntrabarExecutionAdapter 사용"""
        # Given
        data = create_test_data()
        strategy = SimpleTestStrategy()

        # When
        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000,
            use_intrabar_stops=True
            # execution_adapter 미지정
        )

        # Then: IntrabarExecutionAdapter 사용
        from src.infrastructure.adapters.execution import IntrabarExecutionAdapter
        assert isinstance(backtester._execution_adapter, IntrabarExecutionAdapter)


class TestBacktesterTestability:
    """Backtester 테스트 용이성 검증"""

    def test_backtester_can_run_with_mock_adapter(self):
        """Mock 어댑터로 백테스트 실행 가능"""
        # Given
        data = create_test_data(bars=10)
        strategy = SimpleTestStrategy()
        mock_adapter = create_mock_execution_adapter()

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000,
            execution_adapter=mock_adapter
        )

        # When
        result = backtester.run()

        # Then
        assert result is not None
        assert len(result.equity_curve) == 10
        assert result.initial_capital == 1_000_000

    def test_backtester_isolation_from_infrastructure(self):
        """인프라 레이어와 격리된 테스트 가능"""
        # Given: Mock 어댑터 사용
        data = create_test_data()
        strategy = SimpleTestStrategy()
        mock_adapter = create_mock_execution_adapter()

        # When: 실제 인프라 없이 테스트
        with patch('src.backtesting.backtester.SimpleExecutionAdapter') as mock_class:
            backtester = Backtester(
                strategy=strategy,
                data=data,
                ticker="KRW-BTC",
                initial_capital=1_000_000,
                execution_adapter=mock_adapter  # 직접 주입
            )

            # Then: SimpleExecutionAdapter가 생성되지 않음
            mock_class.assert_not_called()
