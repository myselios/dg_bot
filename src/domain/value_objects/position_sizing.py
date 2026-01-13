"""
PositionSizingPolicy Value Object

포지션 사이징 정책을 정의하는 불변 Value Object입니다.
자본 배분 규칙을 캡슐화하여 일관된 진입 금액 계산을 보장합니다.

클린 아키텍처 원칙:
- Domain 레이어에 위치 (비즈니스 규칙)
- 외부 의존성 없음 (순수 계산)
- 불변성 보장 (frozen=True)
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class PositionSizingPolicy:
    """
    포지션 사이징 정책 (불변 Value Object)

    비즈니스 규칙:
    - 코인당 최대 배분: max_allocation_ratio
    - 예비금 비율: reserve_ratio
    - 최대 동시 포지션: max_positions
    - 최소 진입 금액: min_entry_amount

    사용 예시:
        policy = PositionSizingPolicy()
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("1000000"),
            current_position_count=0
        )
        # entry = 400,000 (40% 제한, 3슬롯 중 1개 사용 시)

    Attributes:
        max_allocation_ratio: 코인당 최대 자본 배분 비율 (기본 50%)
        reserve_ratio: 예비금 비율 (기본 5%)
        max_positions: 최대 동시 포지션 수 (기본 2)
        min_entry_amount: 최소 진입 금액 KRW (기본 10,000원)
    """
    max_allocation_ratio: Decimal = Decimal("0.5")    # 50%
    reserve_ratio: Decimal = Decimal("0.05")          # 5%
    max_positions: int = 2
    min_entry_amount: Decimal = Decimal("10000")      # 최소 1만원

    def __post_init__(self) -> None:
        """값 검증"""
        # Decimal 타입 변환 및 검증
        if not isinstance(self.max_allocation_ratio, Decimal):
            object.__setattr__(
                self, "max_allocation_ratio",
                Decimal(str(self.max_allocation_ratio))
            )
        if not isinstance(self.reserve_ratio, Decimal):
            object.__setattr__(
                self, "reserve_ratio",
                Decimal(str(self.reserve_ratio))
            )
        if not isinstance(self.min_entry_amount, Decimal):
            object.__setattr__(
                self, "min_entry_amount",
                Decimal(str(self.min_entry_amount))
            )

        # 비율 범위 검증
        if self.max_allocation_ratio <= Decimal("0") or self.max_allocation_ratio > Decimal("1"):
            raise ValueError(
                f"max_allocation_ratio는 0~1 사이여야 합니다: {self.max_allocation_ratio}"
            )
        if self.reserve_ratio < Decimal("0") or self.reserve_ratio >= Decimal("1"):
            raise ValueError(
                f"reserve_ratio는 0~1 미만이어야 합니다: {self.reserve_ratio}"
            )
        if self.max_positions < 1:
            raise ValueError(
                f"max_positions는 1 이상이어야 합니다: {self.max_positions}"
            )

    # --- Factory Methods ---

    @classmethod
    def default(cls) -> PositionSizingPolicy:
        """기본 정책 생성 (50% 배분, 5% 예비금, 2 포지션)"""
        return cls()

    @classmethod
    def conservative(cls) -> PositionSizingPolicy:
        """보수적 정책 (20% 배분, 20% 예비금, 2 포지션)"""
        return cls(
            max_allocation_ratio=Decimal("0.2"),
            reserve_ratio=Decimal("0.2"),
            max_positions=2,
            min_entry_amount=Decimal("50000")
        )

    @classmethod
    def aggressive(cls) -> PositionSizingPolicy:
        """공격적 정책 (50% 배분, 5% 예비금, 4 포지션)"""
        return cls(
            max_allocation_ratio=Decimal("0.5"),
            reserve_ratio=Decimal("0.05"),
            max_positions=4,
            min_entry_amount=Decimal("10000")
        )

    @classmethod
    def single_position(cls) -> PositionSizingPolicy:
        """단일 포지션 정책 (90% 배분, 5% 예비금, 1 포지션)"""
        return cls(
            max_allocation_ratio=Decimal("0.9"),
            reserve_ratio=Decimal("0.05"),
            max_positions=1,
            min_entry_amount=Decimal("10000")
        )

    # --- Core Business Logic ---

    def calculate_entry_amount(
        self,
        total_capital: Decimal,
        current_krw: Decimal,
        current_position_count: int
    ) -> Decimal:
        """
        진입 금액 계산 (순수 비즈니스 로직)

        계산 공식:
        1. 최대 포지션 수 체크 → 초과 시 0 반환
        2. 예비금 계산: reserve = total_capital × reserve_ratio
        3. 가용 자본: available = current_krw - reserve
        4. 코인당 최대 배분: max_per_coin = total_capital × max_allocation_ratio
        5. 가용 자본 제한: available = min(available, max_per_coin)
        6. 남은 슬롯 분배: entry = available / remaining_slots
        7. 최소 금액 체크 → 미달 시 0 반환

        Args:
            total_capital: 총 자본 (현금 + 투자금 평가액)
            current_krw: 현재 KRW 잔고
            current_position_count: 현재 보유 포지션 수

        Returns:
            진입 가능 금액 (KRW). 진입 불가 시 Decimal("0")
        """
        # 1. 최대 포지션 체크
        if current_position_count >= self.max_positions:
            return Decimal("0")

        # 2. 총 자본이 0이면 진입 불가
        if total_capital <= Decimal("0"):
            return Decimal("0")

        # 3. 예비금 계산
        reserve = total_capital * self.reserve_ratio

        # 4. 가용 자본 = 현금 - 예비금
        available = current_krw - reserve
        if available <= Decimal("0"):
            return Decimal("0")

        # 5. 코인당 최대 배분 적용
        max_per_coin = total_capital * self.max_allocation_ratio
        available = min(available, max_per_coin)

        # 6. 남은 슬롯으로 분배
        remaining_slots = self.max_positions - current_position_count
        entry_amount = available / Decimal(remaining_slots)

        # 7. 최소 금액 체크
        if entry_amount < self.min_entry_amount:
            return Decimal("0")

        # 소수점 이하 버림 (KRW 정수)
        return entry_amount.quantize(Decimal("1"))

    def can_open_position(
        self,
        current_krw: Decimal,
        current_position_count: int
    ) -> bool:
        """
        신규 포지션 진입 가능 여부 확인

        Args:
            current_krw: 현재 KRW 잔고
            current_position_count: 현재 보유 포지션 수

        Returns:
            진입 가능 여부
        """
        # 최대 포지션 체크
        if current_position_count >= self.max_positions:
            return False

        # 최소 금액 체크
        if current_krw < self.min_entry_amount:
            return False

        return True

    def remaining_slots(self, current_position_count: int) -> int:
        """
        남은 포지션 슬롯 수

        Args:
            current_position_count: 현재 보유 포지션 수

        Returns:
            남은 슬롯 수 (0 이상)
        """
        return max(0, self.max_positions - current_position_count)

    # --- String Representation ---

    def __str__(self) -> str:
        """정책 요약"""
        return (
            f"PositionSizingPolicy("
            f"max={self.max_allocation_ratio*100:.0f}%, "
            f"reserve={self.reserve_ratio*100:.0f}%, "
            f"positions={self.max_positions})"
        )

    def __repr__(self) -> str:
        """상세 표현"""
        return (
            f"PositionSizingPolicy("
            f"max_allocation_ratio={self.max_allocation_ratio}, "
            f"reserve_ratio={self.reserve_ratio}, "
            f"max_positions={self.max_positions}, "
            f"min_entry_amount={self.min_entry_amount})"
        )
