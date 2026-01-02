"""
Tests for Percentage value object.
TDD RED Phase - These tests should fail until implementation.
"""
import pytest
from decimal import Decimal

from src.domain.value_objects.percentage import Percentage, Ratio


class TestPercentage:
    """Tests for Percentage value object."""

    # --- Creation Tests ---

    def test_create_percentage_from_decimal(self):
        """Should create Percentage from decimal value (0.05 = 5%)."""
        pct = Percentage(Decimal("0.05"))
        assert pct.value == Decimal("0.05")

    def test_create_percentage_from_points(self):
        """Should create Percentage from percentage points (5 = 5%)."""
        pct = Percentage.from_points(5)
        assert pct.value == Decimal("0.05")

    def test_create_percentage_from_float(self):
        """Should create Percentage from float."""
        pct = Percentage(0.05)
        assert pct.value == Decimal("0.05")

    def test_create_zero_percentage(self):
        """Should create zero percentage."""
        pct = Percentage.zero()
        assert pct.value == Decimal("0")
        assert pct.is_zero()

    # --- Common Percentages ---

    def test_common_fee_rate(self):
        """Should have common fee rate shortcut (0.05%)."""
        pct = Percentage.upbit_fee()
        assert pct.value == Decimal("0.0005")

    # --- Arithmetic Tests ---

    def test_apply_to_amount(self):
        """Should apply percentage to an amount."""
        pct = Percentage(Decimal("0.05"))  # 5%
        result = pct.apply_to(Decimal("1000"))
        assert result == Decimal("50")

    def test_add_percentages(self):
        """Should add two percentages."""
        p1 = Percentage(Decimal("0.05"))
        p2 = Percentage(Decimal("0.03"))
        result = p1 + p2
        assert result.value == Decimal("0.08")

    def test_subtract_percentages(self):
        """Should subtract two percentages."""
        p1 = Percentage(Decimal("0.10"))
        p2 = Percentage(Decimal("0.03"))
        result = p1 - p2
        assert result.value == Decimal("0.07")

    def test_multiply_percentage(self):
        """Should multiply percentage by scalar."""
        pct = Percentage(Decimal("0.05"))
        result = pct * 2
        assert result.value == Decimal("0.10")

    # --- Comparison Tests ---

    def test_equality(self):
        """Should compare equal percentages."""
        p1 = Percentage(Decimal("0.05"))
        p2 = Percentage(Decimal("0.05"))
        assert p1 == p2

    def test_greater_than(self):
        """Should compare greater than."""
        p1 = Percentage(Decimal("0.10"))
        p2 = Percentage(Decimal("0.05"))
        assert p1 > p2

    def test_less_than(self):
        """Should compare less than."""
        p1 = Percentage(Decimal("0.03"))
        p2 = Percentage(Decimal("0.05"))
        assert p1 < p2

    # --- Utility Tests ---

    def test_is_positive(self):
        """Should detect positive percentage."""
        pct = Percentage(Decimal("0.05"))
        assert pct.is_positive()

    def test_is_negative(self):
        """Should detect negative percentage."""
        pct = Percentage(Decimal("-0.05"))
        assert pct.is_negative()

    def test_as_points(self):
        """Should convert to percentage points."""
        pct = Percentage(Decimal("0.05"))
        assert pct.as_points() == Decimal("5")

    def test_as_basis_points(self):
        """Should convert to basis points."""
        pct = Percentage(Decimal("0.0005"))  # 0.05%
        assert pct.as_basis_points() == Decimal("5")

    # --- String Representation ---

    def test_str_representation(self):
        """Should format as percentage string."""
        pct = Percentage(Decimal("0.05"))
        assert "5" in str(pct)
        assert "%" in str(pct)

    def test_str_negative_percentage(self):
        """Should format negative percentage."""
        pct = Percentage(Decimal("-0.05"))
        assert "-5" in str(pct)
        assert "%" in str(pct)


class TestRatio:
    """Tests for Ratio value object."""

    # --- Creation Tests ---

    def test_create_ratio(self):
        """Should create Ratio from decimal."""
        ratio = Ratio(Decimal("0.5"))
        assert ratio.value == Decimal("0.5")

    def test_create_ratio_from_parts(self):
        """Should create Ratio from numerator/denominator."""
        ratio = Ratio.from_parts(1, 3)
        assert ratio.value == Decimal("1") / Decimal("3")

    def test_create_full_ratio(self):
        """Should create full ratio (1.0)."""
        ratio = Ratio.full()
        assert ratio.value == Decimal("1")

    def test_create_half_ratio(self):
        """Should create half ratio (0.5)."""
        ratio = Ratio.half()
        assert ratio.value == Decimal("0.5")

    def test_ratio_cannot_exceed_one(self):
        """Should raise error if ratio exceeds 1.0."""
        with pytest.raises(ValueError, match="exceed"):
            Ratio(Decimal("1.5"))

    def test_ratio_cannot_be_negative(self):
        """Should raise error if ratio is negative."""
        with pytest.raises(ValueError, match="negative"):
            Ratio(Decimal("-0.5"))

    # --- Arithmetic Tests ---

    def test_apply_to_amount(self):
        """Should apply ratio to an amount."""
        ratio = Ratio(Decimal("0.3"))
        result = ratio.apply_to(Decimal("1000"))
        assert result == Decimal("300")

    def test_remaining(self):
        """Should calculate remaining ratio."""
        ratio = Ratio(Decimal("0.3"))
        remaining = ratio.remaining()
        assert remaining.value == Decimal("0.7")

    # --- Comparison Tests ---

    def test_equality(self):
        """Should compare equal ratios."""
        r1 = Ratio(Decimal("0.5"))
        r2 = Ratio(Decimal("0.5"))
        assert r1 == r2

    def test_is_full(self):
        """Should detect full ratio."""
        ratio = Ratio.full()
        assert ratio.is_full()

    # --- String Representation ---

    def test_str_representation(self):
        """Should format as percentage string."""
        ratio = Ratio(Decimal("0.5"))
        assert "50" in str(ratio) or "0.5" in str(ratio)
