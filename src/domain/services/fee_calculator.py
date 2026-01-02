"""
FeeCalculator Domain Service

Handles all fee-related calculations for trading operations.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


@dataclass(frozen=True)
class FeeResult:
    """
    Result of a fee calculation.

    Attributes:
        gross_amount: Amount before fee
        fee: Calculated fee amount
        net_amount: Amount after fee
    """
    gross_amount: Money
    fee: Money
    net_amount: Money

    @property
    def fee_rate(self) -> Percentage:
        """Calculate effective fee rate."""
        if self.gross_amount.is_zero():
            return Percentage.zero()
        rate = self.fee.amount / self.gross_amount.amount
        return Percentage(rate)

    @property
    def total_cost(self) -> Money:
        """Total cost (gross + fee) for buy orders."""
        return self.gross_amount + self.fee


@dataclass(frozen=True)
class FeeCalculator:
    """
    Domain service for calculating trading fees.

    Attributes:
        fee_rate: Fee rate as percentage
        min_fee: Minimum fee amount
    """
    fee_rate: Percentage
    min_fee: Money

    # --- Factory Methods ---

    @classmethod
    def upbit(cls) -> FeeCalculator:
        """Create calculator with Upbit defaults (0.05% fee, no minimum)."""
        return cls(
            fee_rate=Percentage(Decimal("0.0005")),
            min_fee=Money.zero(Currency.KRW),
        )

    @classmethod
    def custom(
        cls,
        fee_rate: Percentage,
        min_fee: Money,
    ) -> FeeCalculator:
        """Create calculator with custom rates."""
        return cls(fee_rate=fee_rate, min_fee=min_fee)

    # --- Basic Fee Calculation ---

    def calculate_fee(self, amount: Money) -> Money:
        """
        Calculate fee for a given amount.

        Uses rate-based calculation with minimum fee floor.
        """
        if amount.is_zero():
            return Money.zero(amount.currency)

        # Calculate rate-based fee
        calculated_fee = self.fee_rate.apply_to(amount.amount)

        # Apply minimum fee
        if self.min_fee.is_positive():
            calculated_fee = max(calculated_fee, self.min_fee.amount)

        # Round to currency precision
        rounded_fee = calculated_fee.quantize(
            Decimal("1") if amount.currency == Currency.KRW else Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        return Money(rounded_fee, amount.currency)

    # --- Buy Calculations ---

    def calculate_buy_amount(self, budget: Money) -> FeeResult:
        """
        Calculate how much can be bought with a given budget.

        Returns the gross amount (before fee) that fits within budget.
        """
        if budget.is_zero():
            return FeeResult(
                gross_amount=Money.zero(budget.currency),
                fee=Money.zero(budget.currency),
                net_amount=Money.zero(budget.currency),
            )

        # If there's a minimum fee and it exceeds rate-based fee
        if self.min_fee.is_positive():
            rate_fee = self.fee_rate.apply_to(budget.amount)
            if rate_fee < self.min_fee.amount:
                # Budget must cover amount + min_fee
                gross = budget - self.min_fee
                if gross.amount <= Decimal("0"):
                    return FeeResult(
                        gross_amount=Money.zero(budget.currency),
                        fee=Money.zero(budget.currency),
                        net_amount=Money.zero(budget.currency),
                    )
                return FeeResult(
                    gross_amount=gross,
                    fee=self.min_fee,
                    net_amount=gross,
                )

        # Rate-based calculation: budget = gross + fee = gross * (1 + rate)
        divisor = Decimal("1") + self.fee_rate.value
        gross_amount = budget.amount / divisor

        # Round down for gross amount
        rounded_gross = gross_amount.quantize(
            Decimal("1") if budget.currency == Currency.KRW else Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        gross = Money(rounded_gross, budget.currency)
        fee = self.calculate_fee(gross)

        return FeeResult(
            gross_amount=gross,
            fee=fee,
            net_amount=gross,
        )

    def calculate_buy_total(self, price: Money, volume: Decimal) -> FeeResult:
        """
        Calculate total cost to buy specific volume at given price.
        """
        gross = price * volume

        # Round to currency precision
        gross = gross.round_for_currency()
        fee = self.calculate_fee(gross)

        return FeeResult(
            gross_amount=gross,
            fee=fee,
            net_amount=gross,
        )

    def calculate_buyable_volume(
        self,
        budget: Money,
        price: Money,
    ) -> Decimal:
        """
        Calculate volume that can be bought with budget at given price.
        """
        buy_result = self.calculate_buy_amount(budget)
        if buy_result.gross_amount.is_zero():
            return Decimal("0")

        # Volume = available amount / price
        volume = buy_result.gross_amount.amount / price.amount
        return volume.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    # --- Sell Calculations ---

    def calculate_sell_net(self, sell_amount: Money) -> FeeResult:
        """
        Calculate net amount received after selling.
        """
        fee = self.calculate_fee(sell_amount)
        net = sell_amount - fee

        return FeeResult(
            gross_amount=sell_amount,
            fee=fee,
            net_amount=net,
        )

    def calculate_sell_net_for_volume(
        self,
        price: Money,
        volume: Decimal,
    ) -> FeeResult:
        """
        Calculate net proceeds from selling volume at price.
        """
        gross = price * volume
        gross = gross.round_for_currency()
        fee = self.calculate_fee(gross)

        return FeeResult(
            gross_amount=gross,
            fee=fee,
            net_amount=gross - fee,
        )

    def calculate_sell_volume_for_net(
        self,
        target_net: Money,
        price: Money,
    ) -> Decimal:
        """
        Calculate volume to sell to receive target net amount.
        """
        # net = gross - fee = gross * (1 - rate)
        # gross = net / (1 - rate)
        divisor = Decimal("1") - self.fee_rate.value
        if divisor <= 0:
            raise ValueError("Fee rate cannot be 100% or more")

        gross_needed = target_net.amount / divisor

        # Volume = gross / price
        volume = gross_needed / price.amount
        return volume.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
