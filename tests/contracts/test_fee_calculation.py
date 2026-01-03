"""
Fee Calculation 계약 테스트

계약: 수수료 계산은 항상 정확해야 하며, 손실을 방지해야 함

이 테스트가 실패하면:
- 수수료 계산 오류로 인한 손실 발생 가능
- 거래 즉시 중단 필요
"""
import pytest
from decimal import Decimal

from src.domain.services.fee_calculator import FeeCalculator, FeeResult
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


class TestFeeCalculationContract:
    """수수료 계산 핵심 계약"""

    @pytest.fixture
    def upbit_calculator(self):
        """Upbit 수수료 계산기 (0.05%)"""
        return FeeCalculator(
            fee_rate=Percentage(Decimal("0.0005")),
            min_fee=Money.krw(0),
        )

    @pytest.fixture
    def calculator_with_min_fee(self):
        """최소 수수료 적용 계산기"""
        return FeeCalculator(
            fee_rate=Percentage(Decimal("0.0005")),
            min_fee=Money.krw(5000),
        )

    # =========================================================================
    # CONTRACT 1: 수수료는 항상 0 이상
    # =========================================================================

    @pytest.mark.contract
    def test_fee_is_never_negative(self, upbit_calculator):
        """수수료는 절대 음수가 될 수 없음"""
        # Given: 다양한 금액
        amounts = [
            Money.krw(0),
            Money.krw(1),
            Money.krw(100),
            Money.krw(100000),
            Money.krw(1000000000),
        ]

        # When & Then: 모든 금액에 대해 수수료는 0 이상
        for amount in amounts:
            fee = upbit_calculator.calculate_fee(amount)
            assert fee.amount >= Decimal("0"), f"Fee for {amount} was negative: {fee}"

    # =========================================================================
    # CONTRACT 2: 정확한 비율 계산
    # =========================================================================

    @pytest.mark.contract
    def test_fee_rate_is_accurate(self, upbit_calculator):
        """수수료 비율이 정확해야 함 (0.05% = 0.0005)"""
        # Given: 정확히 계산 가능한 금액
        amount = Money.krw(1000000)  # 100만원

        # When: 수수료 계산
        fee = upbit_calculator.calculate_fee(amount)

        # Then: 정확히 0.05% = 500원
        assert fee == Money.krw(500)

    @pytest.mark.contract
    def test_fee_calculation_deterministic(self, upbit_calculator):
        """동일 입력에 대해 항상 동일한 수수료 반환"""
        # Given: 동일한 금액
        amount = Money.krw(123456)

        # When: 여러 번 계산
        fee1 = upbit_calculator.calculate_fee(amount)
        fee2 = upbit_calculator.calculate_fee(amount)
        fee3 = upbit_calculator.calculate_fee(amount)

        # Then: 모두 동일
        assert fee1 == fee2 == fee3

    # =========================================================================
    # CONTRACT 3: 최소 수수료 보장
    # =========================================================================

    @pytest.mark.contract
    def test_minimum_fee_applied_when_calculated_is_lower(self, calculator_with_min_fee):
        """계산된 수수료가 최소 수수료보다 작으면 최소 수수료 적용"""
        # Given: 적은 금액 (계산 수수료 < 최소 수수료)
        amount = Money.krw(100000)  # 0.05% = 50원 < 5000원 최소

        # When: 수수료 계산
        fee = calculator_with_min_fee.calculate_fee(amount)

        # Then: 최소 수수료 적용
        assert fee == Money.krw(5000)

    @pytest.mark.contract
    def test_calculated_fee_used_when_exceeds_minimum(self, calculator_with_min_fee):
        """계산된 수수료가 최소 수수료를 초과하면 계산값 사용"""
        # Given: 큰 금액 (계산 수수료 > 최소 수수료)
        amount = Money.krw(20000000)  # 0.05% = 10,000원 > 5000원 최소

        # When: 수수료 계산
        fee = calculator_with_min_fee.calculate_fee(amount)

        # Then: 계산된 수수료 사용
        assert fee == Money.krw(10000)

    # =========================================================================
    # CONTRACT 4: 매수 시 예산 내 거래 보장
    # =========================================================================

    @pytest.mark.contract
    def test_buy_amount_never_exceeds_budget(self, upbit_calculator):
        """매수 시 총 비용(금액 + 수수료)은 예산을 초과하지 않음"""
        # Given: 예산
        budget = Money.krw(100000)

        # When: 매수 가능 금액 계산
        result = upbit_calculator.calculate_buy_amount(budget)

        # Then: 총 비용 <= 예산
        total_cost = result.gross_amount + result.fee
        assert total_cost.amount <= budget.amount

    # =========================================================================
    # CONTRACT 5: 매도 시 순 수익 정확성
    # =========================================================================

    @pytest.mark.contract
    def test_sell_net_amount_is_accurate(self, upbit_calculator):
        """매도 시 순 수익 = 매도 금액 - 수수료"""
        # Given: 매도 금액
        sell_amount = Money.krw(100000)

        # When: 순 수익 계산
        result = upbit_calculator.calculate_sell_net(sell_amount)

        # Then: 순 수익 = 매도 금액 - 수수료
        assert result.net_amount == sell_amount - result.fee
        assert result.net_amount == Money.krw(99950)  # 100000 - 50

    # =========================================================================
    # CONTRACT 6: 제로 금액 처리
    # =========================================================================

    @pytest.mark.contract
    def test_zero_amount_returns_zero_fee(self, upbit_calculator):
        """0원 거래의 수수료는 0원"""
        # Given: 0원
        amount = Money.zero(Currency.KRW)

        # When: 수수료 계산
        fee = upbit_calculator.calculate_fee(amount)

        # Then: 0원 수수료
        assert fee.is_zero()

    # =========================================================================
    # CONTRACT 7: 수수료 비율 팩토리 정확성
    # =========================================================================

    @pytest.mark.contract
    def test_upbit_factory_has_correct_rate(self):
        """Upbit 팩토리는 정확한 수수료율 적용"""
        calc = FeeCalculator.upbit()
        assert calc.fee_rate.value == Decimal("0.0005")


class TestFeeResultContract:
    """FeeResult 값 객체 계약"""

    @pytest.mark.contract
    def test_fee_result_consistency(self):
        """FeeResult의 gross, fee, net 관계가 일관성 있어야 함"""
        # Given: FeeResult 생성
        gross = Money.krw(100000)
        fee = Money.krw(50)
        net = Money.krw(99950)

        result = FeeResult(
            gross_amount=gross,
            fee=fee,
            net_amount=net,
        )

        # Then: gross - fee = net
        assert result.gross_amount - result.fee == result.net_amount

    @pytest.mark.contract
    def test_fee_rate_calculation_accurate(self):
        """수수료율 계산이 정확해야 함"""
        result = FeeResult(
            gross_amount=Money.krw(100000),
            fee=Money.krw(50),
            net_amount=Money.krw(99950),
        )

        # Then: 수수료율 = 50 / 100000 = 0.0005
        assert result.fee_rate.value == Decimal("0.0005")
