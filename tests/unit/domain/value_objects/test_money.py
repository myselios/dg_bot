"""
Tests for Money value object.
TDD RED Phase - These tests should fail until implementation.
"""
import pytest
from decimal import Decimal

from src.domain.value_objects.money import Money, Currency


class TestCurrency:
    """Tests for Currency enum."""

    def test_krw_currency_exists(self):
        """KRW currency should be available."""
        assert Currency.KRW.value == "KRW"

    def test_usd_currency_exists(self):
        """USD currency should be available."""
        assert Currency.USD.value == "USD"

    def test_btc_currency_exists(self):
        """BTC currency should be available."""
        assert Currency.BTC.value == "BTC"


class TestMoney:
    """Tests for Money value object."""

    # --- Creation Tests ---

    def test_create_money_with_decimal(self):
        """Should create Money with Decimal amount."""
        money = Money(Decimal("1000.50"), Currency.KRW)
        assert money.amount == Decimal("1000.50")
        assert money.currency == Currency.KRW

    def test_create_money_with_int(self):
        """Should create Money from integer."""
        money = Money(1000, Currency.KRW)
        assert money.amount == Decimal("1000")

    def test_create_money_with_float(self):
        """Should create Money from float (converted to Decimal)."""
        money = Money(1000.50, Currency.KRW)
        assert money.amount == Decimal("1000.50")

    def test_create_krw_shortcut(self):
        """Should create KRW Money using shortcut."""
        money = Money.krw(5000)
        assert money.amount == Decimal("5000")
        assert money.currency == Currency.KRW

    def test_create_btc_shortcut(self):
        """Should create BTC Money using shortcut."""
        money = Money.btc(Decimal("0.001"))
        assert money.amount == Decimal("0.001")
        assert money.currency == Currency.BTC

    def test_create_zero(self):
        """Should create zero Money."""
        money = Money.zero(Currency.KRW)
        assert money.amount == Decimal("0")
        assert money.is_zero()

    def test_negative_amount_allowed_for_pnl(self):
        """Should allow negative amounts for P&L tracking."""
        money = Money(Decimal("-100"), Currency.KRW)
        assert money.amount == Decimal("-100")
        assert not money.is_positive()

    # --- Arithmetic Tests ---

    def test_add_same_currency(self):
        """Should add two Money of same currency."""
        m1 = Money.krw(1000)
        m2 = Money.krw(500)
        result = m1 + m2
        assert result.amount == Decimal("1500")
        assert result.currency == Currency.KRW

    def test_add_different_currency_raises_error(self):
        """Should raise error when adding different currencies."""
        m1 = Money.krw(1000)
        m2 = Money.btc(Decimal("0.001"))
        with pytest.raises(ValueError, match="(?i)currenc"):
            m1 + m2

    def test_subtract_same_currency(self):
        """Should subtract two Money of same currency."""
        m1 = Money.krw(1000)
        m2 = Money.krw(300)
        result = m1 - m2
        assert result.amount == Decimal("700")

    def test_subtract_resulting_negative_allowed(self):
        """Should allow subtraction resulting in negative for P&L."""
        m1 = Money.krw(100)
        m2 = Money.krw(200)
        result = m1 - m2
        assert result.amount == Decimal("-100")

    def test_multiply_by_scalar(self):
        """Should multiply Money by scalar."""
        money = Money.krw(1000)
        result = money * Decimal("1.5")
        assert result.amount == Decimal("1500")

    def test_multiply_by_int(self):
        """Should multiply Money by integer."""
        money = Money.krw(1000)
        result = money * 2
        assert result.amount == Decimal("2000")

    def test_divide_by_scalar(self):
        """Should divide Money by scalar."""
        money = Money.krw(1000)
        result = money / Decimal("2")
        assert result.amount == Decimal("500")

    def test_divide_by_zero_raises_error(self):
        """Should raise error when dividing by zero."""
        money = Money.krw(1000)
        with pytest.raises(ZeroDivisionError):
            money / 0

    # --- Comparison Tests ---

    def test_equality_same_currency(self):
        """Should compare equal Money objects."""
        m1 = Money.krw(1000)
        m2 = Money.krw(1000)
        assert m1 == m2

    def test_inequality(self):
        """Should detect unequal Money objects."""
        m1 = Money.krw(1000)
        m2 = Money.krw(2000)
        assert m1 != m2

    def test_equality_different_currency(self):
        """Money with different currencies should not be equal."""
        m1 = Money(Decimal("1000"), Currency.KRW)
        m2 = Money(Decimal("1000"), Currency.USD)
        assert m1 != m2

    def test_greater_than(self):
        """Should compare greater than."""
        m1 = Money.krw(2000)
        m2 = Money.krw(1000)
        assert m1 > m2

    def test_less_than(self):
        """Should compare less than."""
        m1 = Money.krw(500)
        m2 = Money.krw(1000)
        assert m1 < m2

    def test_greater_equal(self):
        """Should compare greater than or equal."""
        m1 = Money.krw(1000)
        m2 = Money.krw(1000)
        assert m1 >= m2

    def test_less_equal(self):
        """Should compare less than or equal."""
        m1 = Money.krw(1000)
        m2 = Money.krw(1000)
        assert m1 <= m2

    def test_compare_different_currency_raises_error(self):
        """Should raise error when comparing different currencies."""
        m1 = Money.krw(1000)
        m2 = Money.btc(Decimal("0.001"))
        with pytest.raises(ValueError, match="(?i)currenc"):
            m1 > m2

    # --- Utility Tests ---

    def test_is_zero(self):
        """Should detect zero amount."""
        money = Money.zero(Currency.KRW)
        assert money.is_zero()

    def test_is_positive(self):
        """Should detect positive amount."""
        money = Money.krw(100)
        assert money.is_positive()
        assert not Money.zero(Currency.KRW).is_positive()

    def test_round_to_precision(self):
        """Should round to specified precision."""
        money = Money(Decimal("1000.5678"), Currency.KRW)
        rounded = money.round(2)
        assert rounded.amount == Decimal("1000.57")

    def test_krw_rounds_to_integer(self):
        """KRW should round to integer (no decimal places)."""
        money = Money(Decimal("1000.50"), Currency.KRW)
        rounded = money.round_for_currency()
        assert rounded.amount == Decimal("1001")

    def test_btc_rounds_to_8_decimals(self):
        """BTC should round to 8 decimal places."""
        money = Money(Decimal("0.123456789123"), Currency.BTC)
        rounded = money.round_for_currency()
        assert rounded.amount == Decimal("0.12345679")

    # --- Immutability Tests ---

    def test_money_is_immutable(self):
        """Money should be immutable (frozen dataclass)."""
        money = Money.krw(1000)
        with pytest.raises(AttributeError):
            money.amount = Decimal("2000")

    # --- String Representation ---

    def test_str_representation_krw(self):
        """Should format KRW as integer with currency."""
        money = Money.krw(1000)
        assert "1000" in str(money) or "1,000" in str(money)
        assert "KRW" in str(money)

    def test_str_representation_btc(self):
        """Should format BTC with decimals."""
        money = Money.btc(Decimal("0.12345678"))
        assert "0.12345678" in str(money)
        assert "BTC" in str(money)
