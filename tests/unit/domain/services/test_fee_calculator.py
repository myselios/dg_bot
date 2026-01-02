"""
Tests for FeeCalculator domain service.
TDD RED Phase - These tests should fail until implementation.
"""
import pytest
from decimal import Decimal

from src.domain.services.fee_calculator import FeeCalculator, FeeResult
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


class TestFeeResult:
    """Tests for FeeResult value object."""

    def test_create_fee_result(self):
        """Should create FeeResult with fee and net amount."""
        result = FeeResult(
            gross_amount=Money.krw(100000),
            fee=Money.krw(50),
            net_amount=Money.krw(99950),
        )
        assert result.gross_amount == Money.krw(100000)
        assert result.fee == Money.krw(50)
        assert result.net_amount == Money.krw(99950)

    def test_fee_rate_calculation(self):
        """Should calculate effective fee rate."""
        result = FeeResult(
            gross_amount=Money.krw(100000),
            fee=Money.krw(50),
            net_amount=Money.krw(99950),
        )
        # 50 / 100000 = 0.0005 = 0.05%
        assert result.fee_rate.value == Decimal("0.0005")


class TestFeeCalculator:
    """Tests for FeeCalculator domain service."""

    @pytest.fixture
    def upbit_calculator(self):
        """Create calculator with Upbit fee rates."""
        return FeeCalculator(
            fee_rate=Percentage(Decimal("0.0005")),  # 0.05%
            min_fee=Money.krw(0),  # No minimum fee for Upbit
        )

    @pytest.fixture
    def calculator_with_min_fee(self):
        """Create calculator with minimum fee."""
        return FeeCalculator(
            fee_rate=Percentage(Decimal("0.0005")),  # 0.05%
            min_fee=Money.krw(5000),  # 5000 KRW minimum
        )

    # --- Basic Fee Calculation ---

    def test_calculate_fee_rate_based(self, upbit_calculator):
        """Should calculate fee based on rate."""
        amount = Money.krw(100000)
        fee = upbit_calculator.calculate_fee(amount)
        # 100000 * 0.0005 = 50
        assert fee == Money.krw(50)

    def test_calculate_fee_large_amount(self, upbit_calculator):
        """Should calculate fee for large amounts."""
        amount = Money.krw(10000000)  # 10M KRW
        fee = upbit_calculator.calculate_fee(amount)
        # 10,000,000 * 0.0005 = 5,000
        assert fee == Money.krw(5000)

    def test_calculate_fee_with_minimum(self, calculator_with_min_fee):
        """Should apply minimum fee when calculated fee is lower."""
        amount = Money.krw(100000)  # 100K KRW
        fee = calculator_with_min_fee.calculate_fee(amount)
        # Calculated: 100000 * 0.0005 = 50, but min is 5000
        assert fee == Money.krw(5000)

    def test_calculate_fee_exceeds_minimum(self, calculator_with_min_fee):
        """Should use calculated fee when it exceeds minimum."""
        amount = Money.krw(20000000)  # 20M KRW
        fee = calculator_with_min_fee.calculate_fee(amount)
        # Calculated: 20,000,000 * 0.0005 = 10,000 > 5,000 min
        assert fee == Money.krw(10000)

    # --- Buy/Sell with Fee ---

    def test_calculate_buy_amount_with_fee(self, upbit_calculator):
        """Should calculate amount available for buying after fee."""
        budget = Money.krw(100000)
        result = upbit_calculator.calculate_buy_amount(budget)
        # Available = 100000 / 1.0005 = 99950.02499...
        # Fee = available * 0.0005 = 49.975...
        # Total = available + fee = 100000
        assert result.gross_amount.amount < budget.amount
        assert (result.gross_amount + result.fee).amount <= budget.amount

    def test_calculate_sell_net_amount(self, upbit_calculator):
        """Should calculate net amount received after selling."""
        sell_amount = Money.krw(100000)
        result = upbit_calculator.calculate_sell_net(sell_amount)
        # Net = 100000 - fee = 100000 - 50 = 99950
        assert result.net_amount == Money.krw(99950)
        assert result.fee == Money.krw(50)

    # --- Complex Calculations ---

    def test_calculate_total_cost_for_volume(self, upbit_calculator):
        """Should calculate total cost to buy specific volume."""
        price = Money.krw(50000000)  # 50M KRW per BTC
        volume = Decimal("0.002")  # 0.002 BTC

        result = upbit_calculator.calculate_buy_total(price, volume)
        # Base amount = 50M * 0.002 = 100,000
        # Fee = 100,000 * 0.0005 = 50
        # Total = 100,050
        assert result.gross_amount == Money.krw(100000)
        assert result.fee == Money.krw(50)
        assert result.total_cost == Money.krw(100050)

    def test_calculate_sell_proceeds(self, upbit_calculator):
        """Should calculate net proceeds from selling volume."""
        price = Money.krw(50000000)
        volume = Decimal("0.002")

        result = upbit_calculator.calculate_sell_net_for_volume(price, volume)
        # Gross = 50M * 0.002 = 100,000
        # Fee = 100,000 * 0.0005 = 50
        # Net = 99,950
        assert result.gross_amount == Money.krw(100000)
        assert result.fee == Money.krw(50)
        assert result.net_amount == Money.krw(99950)

    # --- Volume Calculation ---

    def test_calculate_buyable_volume(self, upbit_calculator):
        """Should calculate volume that can be bought with budget."""
        budget = Money.krw(100050)
        price = Money.krw(50000000)

        volume = upbit_calculator.calculate_buyable_volume(budget, price)
        # With 100,050 budget and 50 fee, can buy 100,000 worth
        # Volume = 100,000 / 50,000,000 = 0.002
        assert volume == Decimal("0.002")

    def test_calculate_sellable_amount(self, upbit_calculator):
        """Should calculate amount to sell to receive target net."""
        target_net = Money.krw(99950)
        price = Money.krw(50000000)

        volume = upbit_calculator.calculate_sell_volume_for_net(target_net, price)
        # To receive 99,950, need to sell 100,000 worth (50 fee)
        # Volume = 100,000 / 50,000,000 = 0.002
        assert volume == Decimal("0.002")

    # --- Edge Cases ---

    def test_zero_amount_fee(self, upbit_calculator):
        """Should return zero fee for zero amount."""
        fee = upbit_calculator.calculate_fee(Money.zero(Currency.KRW))
        assert fee.is_zero()

    def test_small_amount_applies_minimum(self, calculator_with_min_fee):
        """Should apply minimum fee for very small amounts."""
        amount = Money.krw(1000)
        fee = calculator_with_min_fee.calculate_fee(amount)
        assert fee == Money.krw(5000)

    def test_fee_rounds_appropriately(self, upbit_calculator):
        """Fee should round to currency precision."""
        # Amount that would result in fractional fee
        amount = Money.krw(99999)
        fee = upbit_calculator.calculate_fee(amount)
        # 99999 * 0.0005 = 49.9995, rounds to 50
        assert fee == Money.krw(50)


class TestFeeCalculatorFactory:
    """Tests for FeeCalculator factory methods."""

    def test_create_upbit_calculator(self):
        """Should create calculator with Upbit defaults."""
        calc = FeeCalculator.upbit()
        assert calc.fee_rate.value == Decimal("0.0005")

    def test_create_custom_calculator(self):
        """Should create calculator with custom rates."""
        calc = FeeCalculator.custom(
            fee_rate=Percentage(Decimal("0.001")),
            min_fee=Money.krw(1000),
        )
        assert calc.fee_rate.value == Decimal("0.001")
        assert calc.min_fee == Money.krw(1000)
