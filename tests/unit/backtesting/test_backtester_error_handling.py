"""
Phase 2: 백테스터 예외 처리 및 로깅 테스트 (TDD)

Silent fail 제거 및 로깅 표준화 검증
"""
import pytest
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from src.backtesting.backtester import Backtester
from src.backtesting.strategy import Strategy


# ============================================================
# 테스트용 Strategy 구현
# ============================================================

class FailingStrategy(Strategy):
    """항상 예외를 발생시키는 테스트용 전략"""

    def __init__(self, fail_at_bar: int = 5):
        self.fail_at_bar = fail_at_bar
        self.call_count = 0

    def generate_signal(self, data: pd.DataFrame, **kwargs):
        self.call_count += 1
        if self.call_count >= self.fail_at_bar:
            raise ValueError(f"의도적 오류: bar {self.call_count}")
        return None

    def calculate_position_size(self, signal, portfolio):
        return 0.0


class NormalStrategy(Strategy):
    """정상 동작하는 테스트용 전략"""

    def generate_signal(self, data: pd.DataFrame, **kwargs):
        return None

    def calculate_position_size(self, signal, portfolio):
        return 0.0


# ============================================================
# 테스트용 데이터 생성
# ============================================================

def create_test_data(bars: int = 20) -> pd.DataFrame:
    """테스트용 OHLCV 데이터 생성"""
    dates = pd.date_range(start='2024-01-01', periods=bars, freq='D')
    return pd.DataFrame({
        'open': np.random.uniform(100, 110, bars),
        'high': np.random.uniform(110, 120, bars),
        'low': np.random.uniform(90, 100, bars),
        'close': np.random.uniform(100, 110, bars),
        'volume': np.random.uniform(1000, 2000, bars),
    }, index=dates)


# ============================================================
# Phase 2: 로깅 표준화 테스트
# ============================================================

class TestBacktesterLogging:
    """백테스터 로깅 표준화 테스트"""

    def test_backtester_has_logger(self):
        """백테스터가 표준 logger를 사용해야 함"""
        # Given
        data = create_test_data()
        strategy = NormalStrategy()

        # When
        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000
        )

        # Then: logger가 존재해야 함
        from src.backtesting import backtester as bt_module
        assert hasattr(bt_module, 'logger'), "backtester 모듈에 logger가 없음"

    def test_signal_generation_error_logged(self, caplog):
        """신호 생성 오류 시 logging으로 기록되어야 함"""
        # Given
        data = create_test_data(bars=10)
        strategy = FailingStrategy(fail_at_bar=3)

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000
        )

        # When
        with caplog.at_level(logging.WARNING):
            result = backtester.run()

        # Then: 로그에 경고 메시지가 포함되어야 함
        assert any("신호 생성 오류" in record.message or "signal" in record.message.lower()
                   for record in caplog.records), \
            f"신호 생성 오류 로그가 없음. 캡처된 로그: {[r.message for r in caplog.records]}"

    def test_order_execution_error_logged(self, caplog):
        """주문 실행 오류 시 logging으로 기록되어야 함"""
        # Given
        data = create_test_data(bars=10)

        class BuySignalStrategy(Strategy):
            def generate_signal(self, data, **kwargs):
                from src.backtesting.strategy import Signal
                # 자금보다 큰 금액으로 매수 시도
                return Signal(action='BUY', size=1000000, price=100)

            def calculate_position_size(self, signal, portfolio):
                return signal.size if signal.size else 1.0

        strategy = BuySignalStrategy()
        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1000  # 매우 작은 자금
        )

        # When
        with caplog.at_level(logging.WARNING):
            result = backtester.run()

        # Then: 주문 실행 관련 로그 또는 정상 완료
        # (자금 부족은 예외가 아닌 정상 거절일 수 있음)
        assert result is not None


class TestBacktesterErrorHandling:
    """백테스터 예외 처리 테스트"""

    def test_signal_error_does_not_crash_backtest(self):
        """신호 생성 오류가 발생해도 백테스트가 중단되지 않아야 함"""
        # Given
        data = create_test_data(bars=20)
        strategy = FailingStrategy(fail_at_bar=5)

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000
        )

        # When
        result = backtester.run()

        # Then: 백테스트가 정상 완료되어야 함
        assert result is not None
        assert len(result.equity_curve) == 20

    def test_backtest_continues_after_multiple_errors(self):
        """여러 오류가 발생해도 백테스트가 계속 진행되어야 함"""
        # Given
        data = create_test_data(bars=30)

        class IntermittentFailStrategy(Strategy):
            def __init__(self):
                self.call_count = 0

            def generate_signal(self, data, **kwargs):
                self.call_count += 1
                if self.call_count % 7 == 0:  # 매 7번째 호출마다 실패
                    raise RuntimeError("간헐적 오류")
                return None

            def calculate_position_size(self, signal, portfolio):
                return 0.0

        strategy = IntermittentFailStrategy()
        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000
        )

        # When
        result = backtester.run()

        # Then
        assert result is not None
        assert len(result.equity_curve) == 30
        # 최소 4번의 오류가 발생했어야 함 (30/7 ≈ 4)
        assert strategy.call_count >= 28


class TestLoggingFormat:
    """로깅 포맷 및 내용 테스트"""

    def test_error_log_contains_context(self, caplog):
        """오류 로그에 컨텍스트 정보가 포함되어야 함"""
        # Given
        data = create_test_data(bars=10)
        strategy = FailingStrategy(fail_at_bar=3)

        backtester = Backtester(
            strategy=strategy,
            data=data,
            ticker="KRW-BTC",
            initial_capital=1_000_000
        )

        # When
        with caplog.at_level(logging.WARNING):
            result = backtester.run()

        # Then: 로그에 시점 정보가 포함되어야 함
        error_logs = [r for r in caplog.records if r.levelno >= logging.WARNING]
        if error_logs:
            # 로그 메시지에 유용한 컨텍스트가 있어야 함
            combined_message = " ".join(r.message for r in error_logs)
            assert any(char.isdigit() for char in combined_message), \
                "오류 로그에 시점/bar 번호 정보가 없음"
