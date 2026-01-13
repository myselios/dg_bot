"""
AveragingDown Value Object

분할 매수(물타기) 정책을 정의하는 불변 Value Object입니다.

클린 아키텍처 원칙:
- Domain 레이어에 위치 (비즈니스 규칙)
- 외부 의존성 없음 (순수 계산)
- 불변성 보장 (frozen=True)
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass(frozen=True)
class AveragingDownLevel:
    """
    분할 매수 단계 (불변)

    Attributes:
        trigger_pct: 발동 손익률 (예: -5.0 = -5%)
        capital_ratio: 추가 투입 비율 (예: 0.3 = 30%)
        executed: 실행 여부
    """
    trigger_pct: Decimal
    capital_ratio: Decimal
    executed: bool = False

    def __post_init__(self):
        """값 검증"""
        if not isinstance(self.trigger_pct, Decimal):
            object.__setattr__(self, "trigger_pct", Decimal(str(self.trigger_pct)))
        if not isinstance(self.capital_ratio, Decimal):
            object.__setattr__(self, "capital_ratio", Decimal(str(self.capital_ratio)))

        if self.trigger_pct > Decimal("0"):
            raise ValueError(f"trigger_pct는 음수여야 합니다: {self.trigger_pct}")
        if self.capital_ratio <= Decimal("0") or self.capital_ratio > Decimal("1"):
            raise ValueError(f"capital_ratio는 0~1 사이여야 합니다: {self.capital_ratio}")


@dataclass(frozen=True)
class AveragingDownPolicy:
    """
    분할 매수 정책 (불변 Value Object)

    3차 분할 매수 전략:
    - 1차: 초기 진입 (50%)
    - 2차: -5% 도달 시 추가 30%
    - 3차: -10% 도달 시 추가 20%

    사용 예시:
        policy = AveragingDownPolicy.default()

        # 현재 손익률 체크
        action = policy.get_next_action(
            current_pnl_pct=-6.0,
            executed_levels=[False, False, False]
        )
        # action = {'level': 2, 'ratio': 0.3, 'trigger': -5.0}

    Attributes:
        levels: 분할 매수 단계 리스트
        enabled: 분할 매수 활성화 여부
    """
    levels: tuple[AveragingDownLevel, ...]
    enabled: bool = True

    def __post_init__(self):
        """값 검증"""
        if not isinstance(self.levels, tuple):
            object.__setattr__(self, "levels", tuple(self.levels))

        if len(self.levels) == 0:
            raise ValueError("levels가 비어있습니다")

        # 트리거 순서 검증 (오름차순이어야 함: -10 < -5 < 0)
        for i in range(len(self.levels) - 1):
            if self.levels[i].trigger_pct >= self.levels[i + 1].trigger_pct:
                raise ValueError(
                    f"트리거는 오름차순이어야 합니다: "
                    f"{self.levels[i].trigger_pct} >= {self.levels[i + 1].trigger_pct}"
                )

    # --- Factory Methods ---

    @classmethod
    def default(cls) -> AveragingDownPolicy:
        """
        기본 3차 분할 매수 정책

        - 2차: -5% 도달 시 30% 추가
        - 3차: -10% 도달 시 20% 추가
        """
        return cls(
            levels=(
                AveragingDownLevel(
                    trigger_pct=Decimal("-10.0"),
                    capital_ratio=Decimal("0.2")  # 20%
                ),
                AveragingDownLevel(
                    trigger_pct=Decimal("-5.0"),
                    capital_ratio=Decimal("0.3")  # 30%
                ),
            ),
            enabled=True
        )

    @classmethod
    def disabled(cls) -> AveragingDownPolicy:
        """분할 매수 비활성화"""
        return cls(
            levels=(
                AveragingDownLevel(
                    trigger_pct=Decimal("-5.0"),
                    capital_ratio=Decimal("0.0")
                ),
            ),
            enabled=False
        )

    # --- Core Business Logic ---

    def get_next_action(
        self,
        current_pnl_pct: Decimal,
        executed_levels: List[bool]
    ) -> Optional[dict]:
        """
        현재 손익률 기준으로 다음 추가 매수 액션 결정

        Args:
            current_pnl_pct: 현재 손익률 (%)
            executed_levels: 각 레벨 실행 여부 [2차, 3차, ...]

        Returns:
            추가 매수 액션 또는 None
            {
                'level': int (단계 번호, 0부터 시작),
                'ratio': Decimal (추가 투입 비율),
                'trigger': Decimal (트리거 손익률)
            }
        """
        if not self.enabled:
            return None

        if not isinstance(current_pnl_pct, Decimal):
            current_pnl_pct = Decimal(str(current_pnl_pct))

        # 실행 이력 확인
        if len(executed_levels) != len(self.levels):
            # 기본값으로 채우기
            executed_levels = executed_levels + [False] * (len(self.levels) - len(executed_levels))

        # 트리거 조건 체크 (가장 낮은 것부터)
        for i, level in enumerate(self.levels):
            if executed_levels[i]:
                # 이미 실행됨
                continue

            if current_pnl_pct <= level.trigger_pct:
                # 트리거 조건 충족
                return {
                    'level': i,
                    'ratio': level.capital_ratio,
                    'trigger': level.trigger_pct,
                    'description': f"{level.trigger_pct}% 도달 → {level.capital_ratio * 100:.0f}% 추가 매수"
                }

        return None

    def calculate_average_price(
        self,
        entries: List[dict]
    ) -> Decimal:
        """
        여러 진입의 평균 단가 계산

        Args:
            entries: 진입 리스트
                [
                    {'price': Decimal, 'amount': Decimal},
                    ...
                ]

        Returns:
            평균 단가
        """
        if not entries:
            return Decimal("0")

        total_cost = Decimal("0")
        total_amount = Decimal("0")

        for entry in entries:
            price = entry['price'] if isinstance(entry['price'], Decimal) else Decimal(str(entry['price']))
            amount = entry['amount'] if isinstance(entry['amount'], Decimal) else Decimal(str(entry['amount']))

            total_cost += price * amount
            total_amount += amount

        if total_amount == Decimal("0"):
            return Decimal("0")

        return total_cost / total_amount

    def is_complete(self, executed_levels: List[bool]) -> bool:
        """
        모든 단계가 완료되었는지 확인

        Args:
            executed_levels: 각 레벨 실행 여부

        Returns:
            완료 여부
        """
        if len(executed_levels) != len(self.levels):
            return False

        return all(executed_levels)

    # --- String Representation ---

    def __str__(self) -> str:
        """정책 요약"""
        if not self.enabled:
            return "AveragingDownPolicy(disabled)"

        level_str = ", ".join([
            f"{level.trigger_pct}%→{level.capital_ratio*100:.0f}%"
            for level in self.levels
        ])
        return f"AveragingDownPolicy({level_str})"

    def __repr__(self) -> str:
        """상세 표현"""
        return (
            f"AveragingDownPolicy("
            f"levels={self.levels}, "
            f"enabled={self.enabled})"
        )
