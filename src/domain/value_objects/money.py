"""
Money Value Object

Represents monetary amounts with currency, ensuring type safety and
proper handling of financial calculations.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Union


class Currency(Enum):
    """Supported currencies."""
    KRW = "KRW"
    USD = "USD"
    BTC = "BTC"
    ETH = "ETH"

    @property
    def precision(self) -> int:
        """Return decimal precision for this currency."""
        precisions = {
            Currency.KRW: 0,
            Currency.USD: 2,
            Currency.BTC: 8,
            Currency.ETH: 8,
        }
        return precisions.get(self, 2)


@dataclass(frozen=True)
class Money:
    """
    Immutable value object representing a monetary amount.

    Attributes:
        amount: The numeric value (always stored as Decimal)
        currency: The currency type
    """
    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        """Validate and normalize the amount."""
        # Convert to Decimal if not already
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))

    # --- Factory Methods ---

    @classmethod
    def krw(cls, amount: Union[int, float, Decimal]) -> Money:
        """Create KRW Money."""
        return cls(Decimal(str(amount)), Currency.KRW)

    @classmethod
    def usd(cls, amount: Union[int, float, Decimal]) -> Money:
        """Create USD Money."""
        return cls(Decimal(str(amount)), Currency.USD)

    @classmethod
    def btc(cls, amount: Union[int, float, Decimal, str]) -> Money:
        """Create BTC Money."""
        return cls(Decimal(str(amount)), Currency.BTC)

    @classmethod
    def eth(cls, amount: Union[int, float, Decimal, str]) -> Money:
        """Create ETH Money."""
        return cls(Decimal(str(amount)), Currency.ETH)

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        """Create zero Money of given currency."""
        return cls(Decimal("0"), currency)

    # --- Arithmetic Operations ---

    def __add__(self, other: Money) -> Money:
        """Add two Money objects of same currency."""
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        """Subtract Money objects of same currency."""
        self._ensure_same_currency(other)
        result = self.amount - other.amount
        return Money(result, self.currency)

    def __mul__(self, scalar: Union[int, float, Decimal]) -> Money:
        """Multiply Money by a scalar."""
        scalar_decimal = Decimal(str(scalar))
        return Money(self.amount * scalar_decimal, self.currency)

    def __rmul__(self, scalar: Union[int, float, Decimal]) -> Money:
        """Right multiply Money by a scalar."""
        return self.__mul__(scalar)

    def __truediv__(self, scalar: Union[int, float, Decimal]) -> Money:
        """Divide Money by a scalar."""
        scalar_decimal = Decimal(str(scalar))
        if scalar_decimal == 0:
            raise ZeroDivisionError("Cannot divide Money by zero")
        return Money(self.amount / scalar_decimal, self.currency)

    # --- Comparison Operations ---

    def __lt__(self, other: Money) -> bool:
        """Less than comparison."""
        self._ensure_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        """Less than or equal comparison."""
        self._ensure_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        """Greater than comparison."""
        self._ensure_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        """Greater than or equal comparison."""
        self._ensure_same_currency(other)
        return self.amount >= other.amount

    # --- Utility Methods ---

    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == Decimal("0")

    def is_positive(self) -> bool:
        """Check if amount is positive (greater than zero)."""
        return self.amount > Decimal("0")

    def round(self, places: int) -> Money:
        """Round to specified decimal places."""
        quantize_str = "1." + "0" * places if places > 0 else "1"
        rounded = self.amount.quantize(
            Decimal(quantize_str), rounding=ROUND_HALF_UP
        )
        return Money(rounded, self.currency)

    def round_for_currency(self) -> Money:
        """Round to currency's standard precision."""
        return self.round(self.currency.precision)

    # --- Private Methods ---

    def _ensure_same_currency(self, other: Money) -> None:
        """Raise error if currencies don't match."""
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot operate on different currencies: "
                f"{self.currency.value} vs {other.currency.value}"
            )

    # --- String Representation ---

    def __str__(self) -> str:
        """Format Money as string."""
        if self.currency == Currency.KRW:
            return f"{int(self.amount):,} KRW"
        elif self.currency in (Currency.BTC, Currency.ETH):
            return f"{self.amount:.8f} {self.currency.value}"
        else:
            return f"{self.amount:.2f} {self.currency.value}"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Money({self.amount}, {self.currency})"
