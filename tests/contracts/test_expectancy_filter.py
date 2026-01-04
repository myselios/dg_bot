"""
Phase 2: 승률↔손익비 연동 필터 (Expectancy) 테스트

TDD RED Phase - 테스트 먼저 작성
목표: 기대값 음수 조합 차단

핵심 공식:
- cost_R = cost_pct / avg_loss_pct
- gross = (win_rate × R) - (1 - win_rate)
- net = gross - cost_R
- R_min = ((1 - win_rate) + cost_R + margin_R) / win_rate
"""
import pytest

# 아직 구현되지 않은 함수 - 테스트가 실패해야 함
from src.backtesting.expectancy_filter import (
    AVG_LOSS_PCT_FLOOR,
    apply_avg_loss_floor,
    calculate_cost_R,
    calculate_net_expectancy,
    check_expectancy_filter,
    get_min_win_loss_ratio,
)


class TestExpectancyCalculation:
    """기대값 계산 정확성 테스트"""

    def test_expectancy_positive_case(self):
        """승률 33%, R=2.5 → 양수 기대값 (P0-1, P0-6 통일 시그니처)"""
        # avg_loss_pct=0.01(1%), cost_pct=0.0012(0.12%) → cost_R = 0.12
        # gross = 0.33 × 2.5 - 0.67 = 0.825 - 0.67 = 0.155
        # net = 0.155 - 0.12 = 0.035
        result = calculate_net_expectancy(
            win_rate=0.33,
            avg_win_loss_ratio=2.5,
            avg_loss_pct=0.01,  # 1%
            cost_pct=0.0012     # 0.12%
        )
        assert abs(result - 0.035) < 0.001
        assert result > 0  # 양수여야 함

    def test_expectancy_negative_stress(self):
        """승률 33%, R=2.5, stress cost → 음수 기대값"""
        # cost_pct=0.002(0.2%) → cost_R = 0.2
        # gross = 0.155, net = 0.155 - 0.2 = -0.045
        result = calculate_net_expectancy(
            win_rate=0.33,
            avg_win_loss_ratio=2.5,
            avg_loss_pct=0.01,  # 1%
            cost_pct=0.002      # 0.2% (stress)
        )
        assert abs(result - (-0.045)) < 0.001
        assert result < 0  # 음수 → 탈락

    def test_expectancy_breakeven_case(self):
        """승률 50%, R=1.0 → 손익분기 (비용 고려 전)"""
        # gross = 0.5 × 1.0 - 0.5 = 0
        # cost_R = 0.0012 / 0.01 = 0.12
        # net = 0 - 0.12 = -0.12
        result = calculate_net_expectancy(
            win_rate=0.5,
            avg_win_loss_ratio=1.0,
            avg_loss_pct=0.01,
            cost_pct=0.0012
        )
        assert result < 0  # 비용 포함 시 음수

    def test_expectancy_with_high_win_rate(self):
        """승률 60%, R=1.5 → 높은 양수 기대값"""
        # gross = 0.6 × 1.5 - 0.4 = 0.9 - 0.4 = 0.5
        # cost_R = 0.0012 / 0.01 = 0.12
        # net = 0.5 - 0.12 = 0.38
        result = calculate_net_expectancy(
            win_rate=0.6,
            avg_win_loss_ratio=1.5,
            avg_loss_pct=0.01,
            cost_pct=0.0012
        )
        assert abs(result - 0.38) < 0.01
        assert result > 0


class TestMinWinLossRatio:
    """최소 손익비 계산 테스트"""

    def test_min_r_calculation_33_percent(self):
        """최소 손익비 계산 검증 - 승률 33% (P0-2, P0-6 통일 시그니처)"""
        # avg_loss_pct=0.01, cost_pct=0.0012 → cost_R = 0.12
        # R_min = (0.67 + 0.12 + 0.05) / 0.33 = 0.84 / 0.33 = 2.545
        result = get_min_win_loss_ratio(
            win_rate=0.33,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        assert abs(result - 2.545) < 0.01

    def test_min_r_calculation_40_percent(self):
        """최소 손익비 계산 - 승률 40%"""
        # R_min = (0.6 + 0.12 + 0.05) / 0.4 = 0.77 / 0.4 = 1.925
        result = get_min_win_loss_ratio(
            win_rate=0.4,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        assert abs(result - 1.925) < 0.01

    def test_min_r_calculation_50_percent(self):
        """최소 손익비 계산 - 승률 50%"""
        # R_min = (0.5 + 0.12 + 0.05) / 0.5 = 0.67 / 0.5 = 1.34
        result = get_min_win_loss_ratio(
            win_rate=0.5,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        assert abs(result - 1.34) < 0.01


class TestAvgLossPctFloor:
    """avg_loss_pct floor 적용 테스트 (P0-7)"""

    def test_floor_constant_value(self):
        """floor 상수값 확인"""
        assert AVG_LOSS_PCT_FLOOR == 0.002  # 0.2%

    def test_apply_floor_low_value(self):
        """극단적으로 낮은 avg_loss_pct → floor 적용"""
        result = apply_avg_loss_floor(avg_loss_pct=0.0001)  # 0.01%
        assert result == 0.002  # floor = 0.2%

    def test_apply_floor_zero_value(self):
        """0 값 → floor 적용"""
        result = apply_avg_loss_floor(avg_loss_pct=0.0)
        assert result == 0.002

    def test_no_floor_normal_value(self):
        """정상 값은 floor 적용 안함"""
        result = apply_avg_loss_floor(avg_loss_pct=0.01)  # 1%
        assert result == 0.01

    def test_no_floor_above_floor(self):
        """floor보다 큰 값은 그대로"""
        result = apply_avg_loss_floor(avg_loss_pct=0.005)  # 0.5%
        assert result == 0.005


class TestCostRCalculation:
    """비용 R 환산 테스트"""

    def test_cost_r_basic(self):
        """기본 cost_R 계산"""
        # cost_R = 0.0012 / 0.01 = 0.12
        result = calculate_cost_R(cost_pct=0.0012, avg_loss_pct=0.01)
        assert abs(result - 0.12) < 0.001

    def test_cost_r_with_floor(self):
        """floor 적용된 avg_loss_pct로 cost_R 계산"""
        # avg_loss_pct=0.0001 → floor 0.002 적용
        # cost_R = 0.0012 / 0.002 = 0.6
        result = calculate_cost_R(cost_pct=0.0012, avg_loss_pct=0.0001)
        assert abs(result - 0.6) < 0.001

    def test_cost_r_stress_test(self):
        """스트레스 테스트 비용"""
        # cost_R = 0.002 / 0.01 = 0.2
        result = calculate_cost_R(cost_pct=0.002, avg_loss_pct=0.01)
        assert abs(result - 0.2) < 0.001


class TestExpectancyFilter:
    """기대값 필터 통합 테스트"""

    def test_filter_pass_good_strategy(self):
        """좋은 전략 → 필터 통과"""
        passed, net_exp = check_expectancy_filter(
            win_rate=0.45,
            avg_win_loss_ratio=1.8,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        assert passed is True
        assert net_exp > 0.05

    def test_filter_fail_bad_strategy(self):
        """나쁜 전략 → 필터 실패"""
        passed, net_exp = check_expectancy_filter(
            win_rate=0.33,
            avg_win_loss_ratio=1.0,  # R=1.0, 승률 33%는 기대값 음수
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        assert passed is False
        assert net_exp < 0

    def test_filter_fail_logical_conflict(self):
        """논리적 충돌 조합 차단 (승률 33% + R=1.0)"""
        # gross = 0.33 × 1.0 - 0.67 = -0.34
        # net = -0.34 - 0.12 = -0.46
        passed, net_exp = check_expectancy_filter(
            win_rate=0.33,
            avg_win_loss_ratio=1.0,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        assert passed is False
        assert net_exp < -0.4


class TestCostPctRequired:
    """cost_pct 필수 파라미터 테스트 (P0-12)"""

    def test_cost_pct_required_for_net_expectancy(self):
        """cost_pct 누락 시 TypeError"""
        with pytest.raises(TypeError):
            # cost_pct 없이 호출 → 실패해야 함
            calculate_net_expectancy(
                win_rate=0.33,
                avg_win_loss_ratio=2.5,
                avg_loss_pct=0.01
                # cost_pct 누락!
            )

    def test_cost_pct_required_for_check_filter(self):
        """check_expectancy_filter도 cost_pct 필수"""
        with pytest.raises(TypeError):
            check_expectancy_filter(
                win_rate=0.33,
                avg_win_loss_ratio=2.5,
                avg_loss_pct=0.01
                # cost_pct 누락!
            )

    def test_cost_pct_required_for_min_r(self):
        """get_min_win_loss_ratio도 cost_pct 필수"""
        with pytest.raises(TypeError):
            get_min_win_loss_ratio(
                win_rate=0.33,
                avg_loss_pct=0.01
                # cost_pct 누락!
            )


class TestEdgeCases:
    """경계값 테스트"""

    def test_win_rate_30_percent(self):
        """승률 30% 경계값"""
        result = get_min_win_loss_ratio(
            win_rate=0.30,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        # R_min = (0.7 + 0.12 + 0.05) / 0.3 = 2.9
        assert abs(result - 2.9) < 0.01

    def test_win_rate_60_percent(self):
        """승률 60% 경계값"""
        result = get_min_win_loss_ratio(
            win_rate=0.60,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.05
        )
        # R_min = (0.4 + 0.12 + 0.05) / 0.6 = 0.95
        assert abs(result - 0.95) < 0.01

    def test_zero_margin(self):
        """margin_R = 0 케이스"""
        result = get_min_win_loss_ratio(
            win_rate=0.5,
            avg_loss_pct=0.01,
            cost_pct=0.0012,
            margin_R=0.0
        )
        # R_min = (0.5 + 0.12 + 0) / 0.5 = 1.24
        assert abs(result - 1.24) < 0.01
