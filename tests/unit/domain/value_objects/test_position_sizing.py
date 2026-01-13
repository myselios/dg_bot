"""
PositionSizingPolicy Value Object 테스트

TDD 방식으로 작성된 테스트입니다.
자본 배분 로직의 정확성을 검증합니다.
"""
import pytest
from decimal import Decimal

from src.domain.value_objects.position_sizing import PositionSizingPolicy


class TestPositionSizingPolicyCreation:
    """PositionSizingPolicy 생성 테스트"""

    def test_create_default_policy(self):
        """기본 정책 생성 테스트"""
        policy = PositionSizingPolicy()
        assert policy.max_allocation_ratio == Decimal("0.5")
        assert policy.reserve_ratio == Decimal("0.05")
        assert policy.max_positions == 2
        assert policy.min_entry_amount == Decimal("10000")

    def test_create_policy_with_custom_values(self):
        """커스텀 값으로 정책 생성"""
        policy = PositionSizingPolicy(
            max_allocation_ratio=Decimal("0.3"),
            reserve_ratio=Decimal("0.15"),
            max_positions=5,
            min_entry_amount=Decimal("50000")
        )
        assert policy.max_allocation_ratio == Decimal("0.3")
        assert policy.reserve_ratio == Decimal("0.15")
        assert policy.max_positions == 5
        assert policy.min_entry_amount == Decimal("50000")

    def test_create_policy_with_float_converts_to_decimal(self):
        """float 입력 시 Decimal로 변환"""
        policy = PositionSizingPolicy(
            max_allocation_ratio=0.3,
            reserve_ratio=0.15
        )
        assert isinstance(policy.max_allocation_ratio, Decimal)
        assert isinstance(policy.reserve_ratio, Decimal)


class TestPositionSizingPolicyFactoryMethods:
    """팩토리 메서드 테스트"""

    def test_default_factory(self):
        """default() 팩토리 메서드"""
        policy = PositionSizingPolicy.default()
        assert policy.max_allocation_ratio == Decimal("0.5")
        assert policy.max_positions == 2

    def test_conservative_factory(self):
        """conservative() 팩토리 메서드"""
        policy = PositionSizingPolicy.conservative()
        assert policy.max_allocation_ratio == Decimal("0.2")
        assert policy.reserve_ratio == Decimal("0.2")
        assert policy.max_positions == 2

    def test_aggressive_factory(self):
        """aggressive() 팩토리 메서드"""
        policy = PositionSizingPolicy.aggressive()
        assert policy.max_allocation_ratio == Decimal("0.5")
        assert policy.reserve_ratio == Decimal("0.05")
        assert policy.max_positions == 4

    def test_single_position_factory(self):
        """single_position() 팩토리 메서드"""
        policy = PositionSizingPolicy.single_position()
        assert policy.max_allocation_ratio == Decimal("0.9")
        assert policy.max_positions == 1


class TestPositionSizingPolicyValidation:
    """정책 값 검증 테스트"""

    def test_invalid_max_allocation_ratio_zero(self):
        """max_allocation_ratio가 0이면 에러"""
        with pytest.raises(ValueError, match="max_allocation_ratio"):
            PositionSizingPolicy(max_allocation_ratio=Decimal("0"))

    def test_invalid_max_allocation_ratio_negative(self):
        """max_allocation_ratio가 음수이면 에러"""
        with pytest.raises(ValueError, match="max_allocation_ratio"):
            PositionSizingPolicy(max_allocation_ratio=Decimal("-0.1"))

    def test_invalid_max_allocation_ratio_over_one(self):
        """max_allocation_ratio가 1 초과이면 에러"""
        with pytest.raises(ValueError, match="max_allocation_ratio"):
            PositionSizingPolicy(max_allocation_ratio=Decimal("1.1"))

    def test_invalid_reserve_ratio_negative(self):
        """reserve_ratio가 음수이면 에러"""
        with pytest.raises(ValueError, match="reserve_ratio"):
            PositionSizingPolicy(reserve_ratio=Decimal("-0.1"))

    def test_invalid_reserve_ratio_one_or_more(self):
        """reserve_ratio가 1 이상이면 에러"""
        with pytest.raises(ValueError, match="reserve_ratio"):
            PositionSizingPolicy(reserve_ratio=Decimal("1.0"))

    def test_invalid_max_positions_zero(self):
        """max_positions가 0이면 에러"""
        with pytest.raises(ValueError, match="max_positions"):
            PositionSizingPolicy(max_positions=0)


class TestCalculateEntryAmount:
    """진입 금액 계산 테스트 (핵심 비즈니스 로직)"""

    def test_basic_calculation_no_positions(self):
        """
        기본 계산: 포지션 없음
        - 총 자본: 1,000,000원
        - 현금: 1,000,000원
        - 포지션: 0개

        예상:
        - 예비금: 1,000,000 × 5% = 50,000
        - 가용: 1,000,000 - 50,000 = 950,000
        - 최대 배분: 1,000,000 × 50% = 500,000
        - 가용 = min(950,000, 500,000) = 500,000
        - 슬롯 2개 → 500,000 / 2 = 250,000
        """
        policy = PositionSizingPolicy()
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("1000000"),
            current_position_count=0
        )
        # 500,000 / 2 = 250,000
        assert entry == Decimal("250000")

    def test_calculation_with_one_position(self):
        """
        1개 포지션 보유 시
        - 총 자본: 1,000,000원
        - 현금: 600,000원 (400,000 투자 중)
        - 포지션: 1개

        예상:
        - 예비금: 1,000,000 × 5% = 50,000
        - 가용: 600,000 - 50,000 = 550,000
        - 최대 배분: 1,000,000 × 50% = 500,000
        - 가용 = min(550,000, 500,000) = 500,000
        - 슬롯 1개 → 500,000 / 1 = 500,000
        """
        policy = PositionSizingPolicy()
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("600000"),
            current_position_count=1
        )
        assert entry == Decimal("500000")

    def test_calculation_with_two_positions(self):
        """
        2개 포지션 보유 시
        - 총 자본: 1,000,000원
        - 현금: 200,000원
        - 포지션: 2개

        예상:
        - 최대 포지션 도달 (2개 = max_positions)
        - 0 반환
        """
        policy = PositionSizingPolicy()
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("200000"),
            current_position_count=2
        )
        assert entry == Decimal("0")

    def test_max_positions_reached_returns_zero(self):
        """최대 포지션 도달 시 0 반환"""
        policy = PositionSizingPolicy()
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("500000"),
            current_position_count=2  # max_positions = 2
        )
        assert entry == Decimal("0")

    def test_zero_capital_returns_zero(self):
        """총 자본이 0이면 0 반환"""
        policy = PositionSizingPolicy()
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("0"),
            current_krw=Decimal("0"),
            current_position_count=0
        )
        assert entry == Decimal("0")

    def test_insufficient_krw_for_reserve_returns_zero(self):
        """예비금보다 현금이 적으면 0 반환"""
        policy = PositionSizingPolicy()
        # 예비금 = 1,000,000 × 10% = 100,000
        # 현금 50,000 < 예비금 100,000
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("50000"),
            current_position_count=0
        )
        assert entry == Decimal("0")

    def test_below_min_entry_amount_returns_zero(self):
        """최소 진입 금액 미달 시 0 반환"""
        policy = PositionSizingPolicy(min_entry_amount=Decimal("50000"))
        # 계산 결과가 50,000 미만이면 0 반환
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("100000"),
            current_krw=Decimal("100000"),
            current_position_count=0
        )
        # 예비금: 10,000, 가용: 90,000, 최대배분: 40,000
        # 40,000 / 3 = 13,333 < 50,000 → 0
        assert entry == Decimal("0")

    def test_entry_amount_is_integer(self):
        """진입 금액은 정수여야 함"""
        policy = PositionSizingPolicy()
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("1000000"),
            current_position_count=0
        )
        # Decimal이지만 정수 값이어야 함
        assert entry == entry.quantize(Decimal("1"))

    def test_conservative_policy_calculation(self):
        """보수적 정책 계산 테스트"""
        policy = PositionSizingPolicy.conservative()
        # 20% 배분, 20% 예비금, 2 포지션
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("1000000"),
            current_position_count=0
        )
        # 예비금: 200,000, 가용: 800,000, 최대배분: 200,000
        # 200,000 / 2 = 100,000
        assert entry == Decimal("100000")

    def test_aggressive_policy_calculation(self):
        """공격적 정책 계산 테스트"""
        policy = PositionSizingPolicy.aggressive()
        # 50% 배분, 5% 예비금, 4 포지션
        entry = policy.calculate_entry_amount(
            total_capital=Decimal("1000000"),
            current_krw=Decimal("1000000"),
            current_position_count=0
        )
        # 예비금: 50,000, 가용: 950,000, 최대배분: 500,000
        # 500,000 / 4 = 125,000
        assert entry == Decimal("125000")


class TestCanOpenPosition:
    """포지션 진입 가능 여부 테스트"""

    def test_can_open_when_slots_available(self):
        """슬롯이 있으면 진입 가능"""
        policy = PositionSizingPolicy()
        assert policy.can_open_position(
            current_krw=Decimal("100000"),
            current_position_count=0
        ) is True

    def test_cannot_open_when_max_positions_reached(self):
        """최대 포지션 도달 시 진입 불가"""
        policy = PositionSizingPolicy()
        assert policy.can_open_position(
            current_krw=Decimal("1000000"),
            current_position_count=3
        ) is False

    def test_cannot_open_when_krw_below_minimum(self):
        """현금이 최소 금액 미만이면 진입 불가"""
        policy = PositionSizingPolicy(min_entry_amount=Decimal("50000"))
        assert policy.can_open_position(
            current_krw=Decimal("10000"),
            current_position_count=0
        ) is False


class TestRemainingSlots:
    """남은 슬롯 수 테스트"""

    def test_remaining_slots_no_positions(self):
        """포지션 없을 때 전체 슬롯"""
        policy = PositionSizingPolicy()
        assert policy.remaining_slots(0) == 2

    def test_remaining_slots_with_positions(self):
        """포지션 있을 때 남은 슬롯"""
        policy = PositionSizingPolicy()
        assert policy.remaining_slots(1) == 1
        assert policy.remaining_slots(2) == 0

    def test_remaining_slots_over_max_returns_zero(self):
        """최대 초과 시 0 반환"""
        policy = PositionSizingPolicy()
        assert policy.remaining_slots(5) == 0


class TestImmutability:
    """불변성 테스트"""

    def test_policy_is_immutable(self):
        """정책은 불변이어야 함 (frozen dataclass)"""
        policy = PositionSizingPolicy()
        with pytest.raises(AttributeError):
            policy.max_allocation_ratio = Decimal("0.5")

    def test_policy_is_hashable(self):
        """정책은 해시 가능해야 함"""
        policy = PositionSizingPolicy()
        # 에러 없이 해시 가능
        hash(policy)


class TestStringRepresentation:
    """문자열 표현 테스트"""

    def test_str_representation(self):
        """__str__ 표현"""
        policy = PositionSizingPolicy()
        s = str(policy)
        assert "50%" in s
        assert "5%" in s
        assert "2" in s

    def test_repr_representation(self):
        """__repr__ 표현"""
        policy = PositionSizingPolicy()
        r = repr(policy)
        assert "PositionSizingPolicy" in r
        assert "max_allocation_ratio" in r
