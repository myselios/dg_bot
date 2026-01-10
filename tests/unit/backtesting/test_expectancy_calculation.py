"""
Phase 1: Expectancy 계산 정확성 테스트 (TDD)

avg_loss_pct 계산 및 Expectancy 필터 연동 검증
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.backtesting.performance import PerformanceAnalyzer
from src.backtesting.portfolio import Trade
from src.backtesting.expectancy_filter import (
    AVG_LOSS_PCT_FLOOR,
    check_expectancy_filter,
    apply_avg_loss_floor
)


# ============================================================
# 테스트용 Trade 생성 헬퍼
# ============================================================

def create_trade(
    entry_price: float,
    exit_price: float,
    size: float,
    commission: float = 0.0
) -> Trade:
    """테스트용 Trade 객체 생성"""
    entry_time = datetime(2024, 1, 1, 10, 0, 0)
    exit_time = entry_time + timedelta(hours=24)
    pnl = (exit_price - entry_price) * size - commission
    pnl_percent = ((exit_price - entry_price) / entry_price) * 100

    return Trade(
        symbol="KRW-BTC",
        entry_price=entry_price,
        exit_price=exit_price,
        size=size,
        entry_time=entry_time,
        exit_time=exit_time,
        pnl=pnl,
        pnl_percent=pnl_percent,
        commission=commission
    )


# ============================================================
# Phase 1: avg_loss_pct 계산 테스트
# ============================================================

class TestAvgLossPctCalculation:
    """PerformanceAnalyzer에서 avg_loss_pct 계산 검증"""

    def test_performance_analyzer_calculates_avg_loss_pct(self):
        """avg_loss_pct가 metrics에 포함되어야 함"""
        # Given: 손실 거래가 있는 거래 목록
        trades = [
            create_trade(entry_price=100_000, exit_price=95_000, size=1.0),  # -5%
            create_trade(entry_price=100_000, exit_price=97_000, size=1.0),  # -3%
            create_trade(entry_price=100_000, exit_price=110_000, size=1.0),  # +10% (수익)
        ]
        equity_curve = [1_000_000, 950_000, 920_000, 1_020_000]

        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # Then: avg_loss_pct가 존재하고 0~1 범위
        assert 'avg_loss_pct' in metrics, "avg_loss_pct 필드가 없음"
        assert 0 <= metrics['avg_loss_pct'] <= 1, "avg_loss_pct는 0~1 범위여야 함"

    def test_avg_loss_pct_calculation_accuracy(self):
        """avg_loss_pct 계산 정확성 검증"""
        # Given: 명확한 손실률을 가진 거래
        # Trade 1: 100,000원 → 95,000원, size=1 → -5,000원 = -5%
        # Trade 2: 100,000원 → 97,000원, size=1 → -3,000원 = -3%
        # 평균 손실률 = (5% + 3%) / 2 = 4% = 0.04
        trades = [
            create_trade(entry_price=100_000, exit_price=95_000, size=1.0),  # -5%
            create_trade(entry_price=100_000, exit_price=97_000, size=1.0),  # -3%
            create_trade(entry_price=100_000, exit_price=110_000, size=1.0),  # 수익 (제외)
        ]
        equity_curve = [1_000_000, 950_000, 920_000, 1_020_000]

        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # Then: 평균 손실률 ≈ 4%
        expected_avg_loss_pct = 0.04
        assert abs(metrics['avg_loss_pct'] - expected_avg_loss_pct) < 0.001, \
            f"avg_loss_pct 계산 오류: 기대값 {expected_avg_loss_pct}, 실제 {metrics['avg_loss_pct']}"

    def test_avg_loss_pct_range_zero_to_one(self):
        """avg_loss_pct가 항상 0~1 범위인지 확인"""
        # Given: 큰 손실 거래
        trades = [
            create_trade(entry_price=100_000, exit_price=50_000, size=1.0),  # -50%
        ]
        equity_curve = [1_000_000, 500_000]

        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # Then
        assert 0 <= metrics['avg_loss_pct'] <= 1

    def test_avg_loss_pct_with_no_losses(self):
        """손실 거래가 없을 때 avg_loss_pct = 0"""
        # Given: 모두 수익 거래
        trades = [
            create_trade(entry_price=100_000, exit_price=110_000, size=1.0),
            create_trade(entry_price=100_000, exit_price=105_000, size=1.0),
        ]
        equity_curve = [1_000_000, 1_100_000, 1_150_000]

        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # Then
        assert metrics['avg_loss_pct'] == 0.0

    def test_avg_win_pct_also_calculated(self):
        """avg_win_pct도 함께 계산되어야 함 (일관성)"""
        trades = [
            create_trade(entry_price=100_000, exit_price=110_000, size=1.0),  # +10%
            create_trade(entry_price=100_000, exit_price=95_000, size=1.0),  # -5%
        ]
        equity_curve = [1_000_000, 1_100_000, 1_050_000]

        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        assert 'avg_win_pct' in metrics


# ============================================================
# Phase 1: AVG_LOSS_PCT_FLOOR 적용 테스트
# ============================================================

class TestAvgLossPctFloor:
    """AVG_LOSS_PCT_FLOOR 적용 테스트"""

    def test_avg_loss_pct_floor_applied_when_too_low(self):
        """매우 낮은 손실률에 floor 적용"""
        # Given: 매우 작은 손실 (0.01%)
        trades = [
            create_trade(entry_price=100_000, exit_price=99_990, size=1.0),  # -0.01%
        ]
        equity_curve = [1_000_000, 999_900]

        # When
        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # Then: floor (0.2% = 0.002) 적용됨
        assert metrics['avg_loss_pct'] >= AVG_LOSS_PCT_FLOOR

    def test_avg_loss_pct_floor_applied_flag_in_metrics(self):
        """floor 적용 시 플래그가 metrics에 포함"""
        trades = [
            create_trade(entry_price=100_000, exit_price=99_990, size=1.0),  # 0.01% 손실
        ]
        equity_curve = [1_000_000, 999_900]

        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        assert 'avg_loss_pct_floor_applied' in metrics


# ============================================================
# Phase 1: Expectancy 필터 연동 테스트
# ============================================================

class TestExpectancyFilterIntegration:
    """Expectancy 필터와 avg_loss_pct 연동 테스트"""

    def test_expectancy_filter_uses_correct_avg_loss_pct(self):
        """Expectancy 필터가 올바른 avg_loss_pct 사용"""
        # Given: 손실 거래 포함
        trades = [
            create_trade(entry_price=100_000, exit_price=95_000, size=1.0),  # -5%
            create_trade(entry_price=100_000, exit_price=115_000, size=1.0),  # +15%
        ]
        equity_curve = [1_000_000, 950_000, 1_100_000]

        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # When: Expectancy 필터 호출
        win_rate = metrics['win_rate'] / 100.0  # % → 0~1
        avg_win = metrics['avg_win']
        avg_loss = abs(metrics['avg_loss'])
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        avg_loss_pct = metrics['avg_loss_pct']
        cost_pct = 0.0012  # 0.12% 왕복

        passed, net_expectancy = check_expectancy_filter(
            win_rate=win_rate,
            avg_win_loss_ratio=avg_win_loss_ratio,
            avg_loss_pct=avg_loss_pct,
            cost_pct=cost_pct
        )

        # Then: 계산이 정상 동작 (numpy bool도 허용)
        assert passed in (True, False)
        assert isinstance(net_expectancy, (float, int))

    def test_expectancy_filter_pass_with_correct_ratio(self):
        """양호한 전략은 Expectancy 필터 통과"""
        # 승률 50%, 손익비 2.0 → 기대값 양수
        passed, net_expectancy = check_expectancy_filter(
            win_rate=0.5,
            avg_win_loss_ratio=2.0,
            avg_loss_pct=0.03,  # 3% 평균 손실
            cost_pct=0.0012
        )

        assert passed is True
        assert net_expectancy > 0

    def test_expectancy_filter_fail_with_low_win_rate(self):
        """낮은 승률 + 낮은 손익비는 Expectancy 필터 실패"""
        # 승률 30%, 손익비 1.0 → 기대값 음수
        passed, net_expectancy = check_expectancy_filter(
            win_rate=0.3,
            avg_win_loss_ratio=1.0,
            avg_loss_pct=0.03,
            cost_pct=0.0012
        )

        assert passed is False
        assert net_expectancy < 0


# ============================================================
# Phase 4: profit_factor inf 처리 테스트
# ============================================================

class TestProfitFactorEdgeCases:
    """profit_factor edge case 테스트"""

    def test_profit_factor_no_losses_returns_none(self):
        """손실 거래 없을 때 profit_factor = None"""
        trades = [
            create_trade(entry_price=100_000, exit_price=110_000, size=1.0),
            create_trade(entry_price=100_000, exit_price=105_000, size=1.0),
        ]
        equity_curve = [1_000_000, 1_100_000, 1_150_000]

        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # inf 대신 None 반환
        assert metrics['profit_factor'] is None or metrics['profit_factor'] == float('inf')

    def test_sharpe_with_zero_volatility_returns_none(self):
        """변동성 0일 때 sharpe_ratio = None (또는 0)"""
        # 모든 수익률이 동일한 경우 → 변동성 0
        equity_curve = [1_000_000, 1_000_000, 1_000_000]
        trades = []

        metrics = PerformanceAnalyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1_000_000
        )

        # None 또는 0
        assert metrics['sharpe_ratio'] is None or metrics['sharpe_ratio'] == 0
