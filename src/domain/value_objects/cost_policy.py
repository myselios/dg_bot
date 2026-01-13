"""
CostPolicy 값 객체

비용 모델 정책의 버전 관리 및 슬리피지/수수료 계산을 담당하는 불변 값 객체
"""

from dataclasses import dataclass
from typing import Literal
import math


VALID_SLIPPAGE_MODELS = ("linear", "sqrt", "dynamic")


@dataclass(frozen=True)
class CostPolicy:
    """
    비용 정책 값 객체

    수수료, 슬리피지, 유동성 페널티를 계산하는 정책을 정의한다.
    버전 관리를 통해 재현성을 보장한다.

    Attributes:
        version: 정책 버전 (e.g., "v1.0.0")
        fee_rate: 수수료율 (e.g., 0.0005 = 0.05%)
        slippage_model: 슬리피지 모델 ("linear" | "sqrt" | "dynamic")
        slippage_base_bps: 기본 슬리피지 (basis points, e.g., 5.0 = 5bps)
        liquidity_threshold: 유동성 페널티 기준 거래대금 (KRW)
    """

    version: str
    fee_rate: float
    slippage_model: Literal["linear", "sqrt", "dynamic"]
    slippage_base_bps: float = 5.0
    liquidity_threshold: int = 10_000_000_000  # 100억 원

    def __post_init__(self):
        """생성 후 유효성 검증"""
        # 수수료율 검증 (0 ~ 1% 미만)
        if self.fee_rate < 0:
            raise ValueError(f"fee_rate는 0 이상이어야 합니다: {self.fee_rate}")
        if self.fee_rate >= 0.01:
            raise ValueError(f"fee_rate는 1% 미만이어야 합니다: {self.fee_rate}")

        # 슬리피지 모델 검증
        if self.slippage_model not in VALID_SLIPPAGE_MODELS:
            raise ValueError(
                f"slippage_model은 {VALID_SLIPPAGE_MODELS} 중 하나여야 합니다: "
                f"{self.slippage_model}"
            )

    def calculate_slippage(
        self, order_size: float, daily_volume: float, volatility: float
    ) -> float:
        """
        슬리피지 계산

        Args:
            order_size: 주문 금액 (KRW)
            daily_volume: 일일 거래대금 (KRW)
            volatility: 일일 변동성 (e.g., 0.02 = 2%)

        Returns:
            예상 슬리피지 (비율, e.g., 0.0005 = 0.05%)
        """
        if daily_volume <= 0:
            return 0.01  # 거래대금 없으면 1% 기본 슬리피지

        participation_rate = order_size / daily_volume

        if self.slippage_model == "linear":
            # 단순 선형 모델
            slippage_bps = participation_rate * 100 * volatility * 100
            return slippage_bps / 10000  # bps -> 비율

        elif self.slippage_model == "sqrt":
            # 제곱근 모델 (Almgren-Chriss 기반)
            slippage_bps = self.slippage_base_bps + 10 * math.sqrt(
                participation_rate
            ) * volatility * 100
            return slippage_bps / 10000  # bps -> 비율

        elif self.slippage_model == "dynamic":
            # 동적 모델 (시간대/변동성 반영)
            time_factor = 1.0  # 추후 시간대별 조정
            slippage_bps = self.slippage_base_bps * time_factor * (1 + volatility * 10)
            return slippage_bps / 10000  # bps -> 비율

        return self.slippage_base_bps / 10000

    def calculate_liquidity_penalty(self, daily_volume: float) -> float:
        """
        유동성 페널티 계산

        Args:
            daily_volume: 일일 거래대금 (KRW)

        Returns:
            페널티 계수 (0.0 ~ 0.5, 높을수록 불리)
        """
        if daily_volume >= self.liquidity_threshold:
            return 0.0

        if daily_volume <= 0:
            return 0.5  # 최대 페널티

        ratio = daily_volume / self.liquidity_threshold
        return (1 - ratio) * 0.5

    def calculate_total_cost(
        self,
        gross_return: float,
        order_size: float,
        daily_volume: float,
        volatility: float,
    ) -> float:
        """
        총 비용 계산 (수수료 + 슬리피지 + 유동성 페널티)

        Args:
            gross_return: 비용 전 수익률 (e.g., 0.10 = 10%)
            order_size: 주문 금액 (KRW)
            daily_volume: 일일 거래대금 (KRW)
            volatility: 일일 변동성

        Returns:
            총 비용 (비율)
        """
        # 수수료 (매수 + 매도)
        fee_cost = abs(gross_return) * self.fee_rate * 2

        # 슬리피지
        slippage_cost = self.calculate_slippage(order_size, daily_volume, volatility)

        # 유동성 페널티 (수익률에 적용)
        liquidity_penalty = self.calculate_liquidity_penalty(daily_volume)
        liquidity_cost = abs(gross_return) * liquidity_penalty

        return fee_cost + slippage_cost + liquidity_cost

    @classmethod
    def default(cls) -> "CostPolicy":
        """기본 비용 정책 생성 (일반 등급)"""
        return cls(
            version="v1.0.0",
            fee_rate=0.0005,  # 0.05%
            slippage_model="sqrt",
            slippage_base_bps=5.0,
            liquidity_threshold=10_000_000_000,
        )

    @classmethod
    def vip1(cls) -> "CostPolicy":
        """VIP1 비용 정책 (월 1억 이상)"""
        return cls(
            version="v1.0.0",
            fee_rate=0.0004,  # 0.04%
            slippage_model="sqrt",
            slippage_base_bps=5.0,
            liquidity_threshold=10_000_000_000,
        )

    @classmethod
    def vip2(cls) -> "CostPolicy":
        """VIP2 비용 정책 (월 10억 이상)"""
        return cls(
            version="v1.0.0",
            fee_rate=0.0003,  # 0.03%
            slippage_model="sqrt",
            slippage_base_bps=5.0,
            liquidity_threshold=10_000_000_000,
        )
