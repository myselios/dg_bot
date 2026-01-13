"""
CostPolicy 값 객체 테스트

비용 모델 정책의 버전 관리 및 슬리피지 계산 테스트
"""

import pytest
import math
from decimal import Decimal


class TestCostPolicy:
    """CostPolicy 값 객체 테스트"""

    def test_cost_policy_has_version(self):
        """비용 정책은 버전을 가져야 한다"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy(
            version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            slippage_base_bps=5.0,
            liquidity_threshold=10_000_000_000,
        )

        assert policy.version == "v1.0.0"
        assert policy.fee_rate == 0.0005

    def test_cost_policy_fee_rate_validation(self):
        """수수료율은 0 이상 1% 미만이어야 한다"""
        from src.domain.value_objects.cost_policy import CostPolicy

        # 유효한 수수료율
        policy = CostPolicy(
            version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )
        assert policy.fee_rate == 0.0005

        # 음수 수수료율은 불가
        with pytest.raises(ValueError):
            CostPolicy(version="v1.0.0", fee_rate=-0.001, slippage_model="sqrt")

        # 1% 이상 수수료율은 불가
        with pytest.raises(ValueError):
            CostPolicy(version="v1.0.0", fee_rate=0.02, slippage_model="sqrt")

    def test_cost_policy_slippage_model_validation(self):
        """슬리피지 모델은 linear, sqrt, dynamic 중 하나여야 한다"""
        from src.domain.value_objects.cost_policy import CostPolicy

        # 유효한 모델
        for model in ["linear", "sqrt", "dynamic"]:
            policy = CostPolicy(version="v1.0.0", fee_rate=0.0005, slippage_model=model)
            assert policy.slippage_model == model

        # 유효하지 않은 모델
        with pytest.raises(ValueError):
            CostPolicy(version="v1.0.0", fee_rate=0.0005, slippage_model="invalid")

    def test_calculate_slippage_linear(self):
        """선형 슬리피지 모델 계산"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy(
            version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="linear",
            slippage_base_bps=5.0,
        )

        # 주문 1억, 거래대금 100억, 변동성 2%
        slippage = policy.calculate_slippage(
            order_size=100_000_000,
            daily_volume=10_000_000_000,
            volatility=0.02,
        )

        # participation_rate = 0.01, slippage = 0.01 * 100 * 0.02 = 0.02%
        assert slippage > 0

    def test_calculate_slippage_sqrt(self):
        """제곱근 슬리피지 모델 계산 (Almgren-Chriss 기반)"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy(
            version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            slippage_base_bps=5.0,
        )

        # 주문 1억, 거래대금 100억, 변동성 2%
        slippage = policy.calculate_slippage(
            order_size=100_000_000,
            daily_volume=10_000_000_000,
            volatility=0.02,
        )

        # base_impact + 10 * sqrt(participation_rate) * volatility
        # 5.0 + 10 * sqrt(0.01) * 0.02 = 5.0 + 10 * 0.1 * 0.02 = 5.02 bps
        assert slippage > 0
        assert slippage < 0.01  # 1% 미만

    def test_calculate_liquidity_penalty(self):
        """유동성 페널티 계산"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy(
            version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            liquidity_threshold=10_000_000_000,
        )

        # 거래대금 100억 이상 -> 페널티 0
        penalty = policy.calculate_liquidity_penalty(daily_volume=15_000_000_000)
        assert penalty == 0.0

        # 거래대금 50억 -> 50% 미달 -> 페널티 0.25
        penalty = policy.calculate_liquidity_penalty(daily_volume=5_000_000_000)
        assert penalty == pytest.approx(0.25, rel=0.01)

        # 거래대금 0 -> 페널티 0.5 (최대)
        penalty = policy.calculate_liquidity_penalty(daily_volume=0)
        assert penalty == 0.5

    def test_calculate_total_cost(self):
        """총 비용 계산 (수수료 + 슬리피지 + 유동성 페널티)"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy(
            version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            slippage_base_bps=5.0,
            liquidity_threshold=10_000_000_000,
        )

        total_cost = policy.calculate_total_cost(
            gross_return=0.10,  # 10% 수익
            order_size=100_000_000,
            daily_volume=10_000_000_000,
            volatility=0.02,
        )

        # 수수료: 0.10 * 0.0005 * 2 = 0.001 (0.1%)
        # 슬리피지: ~0.0005 (5bps)
        # 유동성 페널티: 0
        assert total_cost > 0
        assert total_cost < 0.05  # 5% 미만

    def test_cost_policy_immutable(self):
        """CostPolicy는 불변 객체여야 한다"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy(
            version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        # frozen=True로 설정되어 있어야 함
        with pytest.raises((AttributeError, TypeError)):
            policy.version = "v2.0.0"


class TestCostPolicyFactory:
    """CostPolicy 팩토리 테스트"""

    def test_create_default_policy(self):
        """기본 비용 정책 생성"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy.default()

        assert policy.version == "v1.0.0"
        assert policy.fee_rate == 0.0005  # 0.05%
        assert policy.slippage_model == "sqrt"
        assert policy.slippage_base_bps == 5.0
        assert policy.liquidity_threshold == 10_000_000_000

    def test_create_vip_policy(self):
        """VIP 비용 정책 생성"""
        from src.domain.value_objects.cost_policy import CostPolicy

        policy = CostPolicy.vip1()
        assert policy.fee_rate == 0.0004  # 0.04%

        policy = CostPolicy.vip2()
        assert policy.fee_rate == 0.0003  # 0.03%
