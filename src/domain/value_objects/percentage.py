"""
Percentage and Ratio Value Objects

Represents percentage values and ratios, ensuring type safety and
proper mathematical operations.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Union


@dataclass(frozen=True)
class Percentage:
    """
    Immutable value object representing a percentage.

    Stored as decimal value (0.05 = 5%).

    Attributes:
        value: The percentage as decimal (e.g., 0.05 for 5%)
    """
    value: Decimal

    def __post_init__(self) -> None:
        """Convert to Decimal if needed."""
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, "value", Decimal(str(self.value)))

    # --- Factory Methods ---

    @classmethod
    def from_points(cls, points: Union[int, float, Decimal]) -> Percentage:
        """Create Percentage from percentage points (5 = 5%)."""
        return cls(Decimal(str(points)) / Decimal("100"))

    @classmethod
    def zero(cls) -> Percentage:
        """Create zero percentage."""
        return cls(Decimal("0"))

    @classmethod
    def upbit_fee(cls) -> Percentage:
        """Create Upbit's standard fee rate (0.05%)."""
        return cls(Decimal("0.0005"))

    # --- Arithmetic Operations ---

    def apply_to(self, amount: Decimal) -> Decimal:
        """Apply percentage to an amount."""
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        return amount * self.value

    def __add__(self, other: Percentage) -> Percentage:
        """Add two percentages."""
        return Percentage(self.value + other.value)

    def __sub__(self, other: Percentage) -> Percentage:
        """Subtract percentages."""
        return Percentage(self.value - other.value)

    def __mul__(self, scalar: Union[int, float, Decimal]) -> Percentage:
        """Multiply percentage by scalar."""
        scalar_decimal = Decimal(str(scalar))
        return Percentage(self.value * scalar_decimal)

    def __rmul__(self, scalar: Union[int, float, Decimal]) -> Percentage:
        """Right multiply percentage by scalar."""
        return self.__mul__(scalar)

    def __neg__(self) -> Percentage:
        """Negate percentage."""
        return Percentage(-self.value)

    # --- Comparison Operations ---

    def __lt__(self, other: Percentage) -> bool:
        """Less than comparison."""
        return self.value < other.value

    def __le__(self, other: Percentage) -> bool:
        """Less than or equal comparison."""
        return self.value <= other.value

    def __gt__(self, other: Percentage) -> bool:
        """Greater than comparison."""
        return self.value > other.value

    def __ge__(self, other: Percentage) -> bool:
        """Greater than or equal comparison."""
        return self.value >= other.value

    # --- Utility Methods ---

    def is_zero(self) -> bool:
        """Check if percentage is zero."""
        return self.value == Decimal("0")

    def is_positive(self) -> bool:
        """Check if percentage is positive."""
        return self.value > Decimal("0")

    def is_negative(self) -> bool:
        """Check if percentage is negative."""
        return self.value < Decimal("0")

    def as_points(self) -> Decimal:
        """Convert to percentage points (0.05 -> 5)."""
        return self.value * Decimal("100")

    def as_basis_points(self) -> Decimal:
        """Convert to basis points (0.0005 -> 5)."""
        return self.value * Decimal("10000")

    # --- String Representation ---

    def __str__(self) -> str:
        """Format as percentage string."""
        points = self.as_points()
        return f"{points}%"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Percentage({self.value})"


@dataclass(frozen=True)
class Ratio:
    """
    Immutable value object representing a ratio (0.0 to 1.0).

    Used for position sizing, split percentages, etc.

    Attributes:
        value: The ratio as decimal (0.0 to 1.0)
    """
    value: Decimal

    def __post_init__(self) -> None:
        """Validate and convert to Decimal."""
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, "value", Decimal(str(self.value)))

        if self.value < Decimal("0"):
            raise ValueError(f"Ratio cannot be negative: {self.value}")

        if self.value > Decimal("1"):
            raise ValueError(f"Ratio cannot exceed 1.0: {self.value}")

    # --- Factory Methods ---

    @classmethod
    def from_parts(cls, numerator: int, denominator: int) -> Ratio:
        """Create Ratio from numerator/denominator."""
        if denominator == 0:
            raise ValueError("Denominator cannot be zero")
        return cls(Decimal(str(numerator)) / Decimal(str(denominator)))

    @classmethod
    def full(cls) -> Ratio:
        """Create full ratio (1.0 = 100%)."""
        return cls(Decimal("1"))

    @classmethod
    def half(cls) -> Ratio:
        """Create half ratio (0.5 = 50%)."""
        return cls(Decimal("0.5"))

    @classmethod
    def zero(cls) -> Ratio:
        """Create zero ratio."""
        return cls(Decimal("0"))

    # --- Arithmetic Operations ---

    def apply_to(self, amount: Decimal) -> Decimal:
        """Apply ratio to an amount."""
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        return amount * self.value

    def remaining(self) -> Ratio:
        """Calculate remaining ratio (1 - value)."""
        return Ratio(Decimal("1") - self.value)

    # --- Comparison Operations ---

    def __lt__(self, other: Ratio) -> bool:
        """Less than comparison."""
        return self.value < other.value

    def __le__(self, other: Ratio) -> bool:
        """Less than or equal comparison."""
        return self.value <= other.value

    def __gt__(self, other: Ratio) -> bool:
        """Greater than comparison."""
        return self.value > other.value

    def __ge__(self, other: Ratio) -> bool:
        """Greater than or equal comparison."""
        return self.value >= other.value

    # --- Utility Methods ---

    def is_full(self) -> bool:
        """Check if ratio is 1.0 (100%)."""
        return self.value == Decimal("1")

    def is_zero(self) -> bool:
        """Check if ratio is 0."""
        return self.value == Decimal("0")

    # --- String Representation ---

    def __str__(self) -> str:
        """Format as percentage string."""
        pct = self.value * Decimal("100")
        return f"{pct}%"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Ratio({self.value})"
