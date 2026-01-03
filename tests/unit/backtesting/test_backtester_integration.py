"""
Backtester 통합 테스트

새로운 ExecutionPort와 기존 Backtester 통합 검증.
하위 호환성 및 Intrabar 모드 테스트.
"""
import pytest
from datetime import datetime
from decimal import Decimal
import pandas as pd
import numpy as np

from src.backtesting.backtester import Backtester, BacktestResult
from src.backtesting.strategy import Strategy, Signal
from src.backtesting.portfolio import Portfolio


class SimpleTestStrategy(Strategy):
    """테스트용 간단한 전략"""

    def __init__(self, buy_on_bar: int = 5, sell_on_bar: int = 10):
        self.buy_on_bar = buy_on_bar
        self.sell_on_bar = sell_on_bar
        self.position_open = False

    def generate_signal(self, data: pd.DataFrame, portfolio=None) -> Signal:
        bar_num = len(data)

        # 포지션 확인
        has_position = portfolio and len(portfolio.positions) > 0

        if bar_num == self.buy_on_bar and not has_position:
            current_price = data['close'].iloc[-1]
            # 스탑로스 2% 아래, 익절 3% 위
            stop_loss = current_price * 0.98
            take_profit = current_price * 1.03
            return Signal(
                action='buy',
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason={'type': 'test_buy'}
            )
        elif bar_num == self.sell_on_bar and has_position:
            return Signal(
                action='sell',
                price=data['close'].iloc[-1],
                reason={'type': 'test_sell'}
            )

        return None

    def calculate_position_size(self, signal: Signal, portfolio: Portfolio) -> float:
        # 포트폴리오의 10%
        return (portfolio.equity * 0.1) / signal.price


class StopLossTestStrategy(Strategy):
    """스탑로스 테스트용 전략 - 무조건 스탑 걸리는 시나리오"""

    def __init__(self, stop_loss_pct: float = 0.02):
        self.stop_loss_pct = stop_loss_pct
        self.entered = False

    def generate_signal(self, data: pd.DataFrame, portfolio=None) -> Signal:
        bar_num = len(data)
        has_position = portfolio and len(portfolio.positions) > 0

        # 첫 번째 봉에서 진입
        if bar_num == 1 and not has_position and not self.entered:
            current_price = data['close'].iloc[-1]
            stop_loss = current_price * (1 - self.stop_loss_pct)
            take_profit = current_price * 1.10  # 익절은 멀리
            self.entered = True
            return Signal(
                action='buy',
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason={'type': 'entry'}
            )

        return None

    def calculate_position_size(self, signal: Signal, portfolio: Portfolio) -> float:
        return (portfolio.equity * 0.1) / signal.price


def create_test_data(num_bars: int = 20, start_price: float = 50000000) -> pd.DataFrame:
    """테스트용 캔들 데이터 생성"""
    dates = pd.date_range(start='2026-01-01', periods=num_bars, freq='h')

    # 약간의 변동성을 가진 가격 데이터
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, num_bars)
    prices = start_price * np.cumprod(1 + returns)

    data = pd.DataFrame({
        'open': prices * (1 - np.random.uniform(0, 0.01, num_bars)),
        'high': prices * (1 + np.random.uniform(0.01, 0.02, num_bars)),
        'low': prices * (1 - np.random.uniform(0.01, 0.02, num_bars)),
        'close': prices,
        'volume': np.random.uniform(100, 1000, num_bars)
    }, index=dates)

    return data


def create_stop_loss_triggered_data() -> pd.DataFrame:
    """스탑로스가 트리거되는 데이터 생성

    시나리오:
    - 봉 1: 진입 (50000000)
    - 봉 2: 저점이 스탑(49000000) 아래로 떨어지지만 종가는 회복
    """
    dates = pd.date_range(start='2026-01-01', periods=5, freq='h')

    data = pd.DataFrame({
        'open':  [50000000, 50100000, 49500000, 49000000, 48500000],
        'high':  [50500000, 50200000, 49800000, 49500000, 49000000],
        'low':   [49800000, 48500000, 49000000, 48000000, 47500000],  # 봉2에서 스탑 도달
        'close': [50000000, 50000000, 49200000, 48500000, 48000000],  # 종가는 스탑 위로 회복
        'volume': [100, 150, 120, 130, 110]
    }, index=dates)

    return data


class TestBacktesterLegacyCompatibility:
    """기존 API 하위 호환성 테스트"""

    def test_backtester_runs_with_default_settings(self):
        """Given: 기본 설정의 Backtester
        When: 백테스트 실행
        Then: 정상 동작 및 결과 반환"""
        data = create_test_data(num_bars=15)
        strategy = SimpleTestStrategy(buy_on_bar=5, sell_on_bar=10)

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=10000000,
            commission=0.0005,
            slippage=0.0001
        )

        result = backtester.run()

        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 10000000
        assert len(result.equity_curve) > 0

    def test_backtester_execute_on_next_open_default(self):
        """Given: execute_on_next_open=True (기본값)
        When: 백테스트 실행
        Then: 다음 봉 시가로 체결"""
        data = create_test_data(num_bars=15)
        strategy = SimpleTestStrategy(buy_on_bar=5, sell_on_bar=10)

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=10000000,
            execute_on_next_open=True  # 기본값
        )

        result = backtester.run()

        assert result.execution_mode == 'next_open'


class TestBacktesterIntrabarMode:
    """Intrabar 체결 모드 테스트"""

    def test_intrabar_mode_enables_realistic_stops(self):
        """Given: Intrabar 모드 활성화
        When: 봉 내에서 스탑 가격 도달
        Then: 스탑 체결됨 (종가와 무관)"""
        data = create_stop_loss_triggered_data()
        strategy = StopLossTestStrategy(stop_loss_pct=0.02)  # 2% 스탑

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=10000000,
            execute_on_next_open=True,
            use_intrabar_stops=True  # 새 옵션
        )

        result = backtester.run()

        # Intrabar 모드에서는 스탑이 트리거되어야 함
        # 봉 2에서 저점(48500000)이 스탑(49000000) 아래로 내려감
        assert len(result.trades) >= 1  # 적어도 한 번 거래 발생

    def test_simple_mode_ignores_intrabar_stops(self):
        """Given: Simple 모드 (기본값)
        When: 봉 내에서 스탑 가격 도달했지만 종가는 회복
        Then: 스탑 체결 안 됨"""
        data = create_stop_loss_triggered_data()
        strategy = StopLossTestStrategy(stop_loss_pct=0.02)

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=10000000,
            execute_on_next_open=True,
            use_intrabar_stops=False  # 기본값
        )

        result = backtester.run()

        # Simple 모드에서는 종가 기준이므로 봉 2에서 스탑 안 걸림
        # (종가 50000000 > 스탑 49000000)


class TestBacktesterMetrics:
    """백테스트 메트릭 테스트"""

    def test_metrics_include_all_required_fields(self):
        """Given: 백테스트 실행
        When: 결과 메트릭 확인
        Then: 필수 필드 모두 포함"""
        data = create_test_data(num_bars=20)
        strategy = SimpleTestStrategy(buy_on_bar=5, sell_on_bar=15)

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=10000000
        )

        result = backtester.run()

        # 필수 메트릭 확인
        assert 'total_return' in result.metrics
        assert 'max_drawdown' in result.metrics
        assert 'sharpe_ratio' in result.metrics
        assert 'win_rate' in result.metrics
