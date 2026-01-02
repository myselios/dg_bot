"""
RiskCalculator Domain Service

Handles risk assessment and position sizing calculations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum, auto
from functools import total_ordering
from typing import List, Optional

from src.domain.entities.trade import Position
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


@total_ordering
class RiskLevel(Enum):
    """Risk level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: RiskLevel) -> bool:
        """Compare risk levels."""
        order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return order.index(self) < order.index(other)


@dataclass(frozen=True)
class RiskAssessment:
    """
    Result of a risk assessment.

    Attributes:
        level: Overall risk level
        allowed: Whether trading is allowed
        reasons: List of reasons for the assessment
        recommendations: List of recommendations
    """
    level: RiskLevel
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def is_trade_allowed(self) -> bool:
        """Check if trading is allowed."""
        return self.allowed


@dataclass(frozen=True)
class PositionRisk:
    """
    Risk metrics for a single position.

    Attributes:
        position_size_pct: Position size as % of portfolio
        unrealized_pnl: Unrealized profit/loss
        unrealized_pnl_pct: Unrealized P&L as percentage
        holding_hours: Hours position has been held
        stop_loss_distance: Distance to stop loss (negative = beyond SL)
        take_profit_distance: Distance to take profit (negative = beyond TP)
    """
    position_size_pct: Percentage
    unrealized_pnl: Money
    unrealized_pnl_pct: Percentage
    holding_hours: float
    stop_loss_distance: Percentage
    take_profit_distance: Percentage

    def is_at_stop_loss(self) -> bool:
        """Check if position is at or beyond stop loss."""
        return self.stop_loss_distance.value <= Decimal("0")

    def is_at_take_profit(self) -> bool:
        """Check if position is at or beyond take profit."""
        return self.take_profit_distance.value <= Decimal("0")


@dataclass(frozen=True)
class PortfolioRisk:
    """
    Risk metrics for entire portfolio.

    Attributes:
        total_exposure: Total amount invested
        exposure_pct: Exposure as percentage of portfolio
        daily_pnl: Today's realized + unrealized P&L
        daily_pnl_pct: Daily P&L as percentage
        weekly_pnl: This week's P&L
        weekly_pnl_pct: Weekly P&L as percentage
        open_positions_count: Number of open positions
        largest_position_pct: Size of largest position as %
    """
    total_exposure: Money
    exposure_pct: Percentage
    daily_pnl: Money
    daily_pnl_pct: Percentage
    weekly_pnl: Money
    weekly_pnl_pct: Percentage
    open_positions_count: int
    largest_position_pct: Percentage

    def is_daily_limit_exceeded(self, limit: Percentage) -> bool:
        """Check if daily loss limit is exceeded."""
        # Limit is negative (e.g., -5%)
        return self.daily_pnl_pct.value < limit.value

    def is_weekly_limit_exceeded(self, limit: Percentage) -> bool:
        """Check if weekly loss limit is exceeded."""
        return self.weekly_pnl_pct.value < limit.value


@dataclass(frozen=True)
class RiskCalculator:
    """
    Domain service for risk assessment and position sizing.

    Attributes:
        max_position_size: Maximum position size as % of portfolio
        stop_loss: Stop loss percentage (negative)
        take_profit: Take profit percentage (positive)
        daily_loss_limit: Daily loss limit (negative)
        weekly_loss_limit: Weekly loss limit (negative)
    """
    max_position_size: Percentage
    stop_loss: Percentage
    take_profit: Percentage
    daily_loss_limit: Percentage = field(
        default_factory=lambda: Percentage(Decimal("-0.10"))
    )
    weekly_loss_limit: Percentage = field(
        default_factory=lambda: Percentage(Decimal("-0.15"))
    )

    # --- Factory Methods ---

    @classmethod
    def conservative(cls) -> RiskCalculator:
        """Create conservative risk calculator."""
        return cls(
            max_position_size=Percentage(Decimal("0.20")),  # 20%
            stop_loss=Percentage(Decimal("-0.03")),  # -3%
            take_profit=Percentage(Decimal("0.06")),  # +6%
            daily_loss_limit=Percentage(Decimal("-0.05")),  # -5%
            weekly_loss_limit=Percentage(Decimal("-0.10")),  # -10%
        )

    @classmethod
    def moderate(cls) -> RiskCalculator:
        """Create moderate risk calculator."""
        return cls(
            max_position_size=Percentage(Decimal("0.30")),  # 30%
            stop_loss=Percentage(Decimal("-0.05")),  # -5%
            take_profit=Percentage(Decimal("0.10")),  # +10%
            daily_loss_limit=Percentage(Decimal("-0.10")),  # -10%
            weekly_loss_limit=Percentage(Decimal("-0.15")),  # -15%
        )

    @classmethod
    def aggressive(cls) -> RiskCalculator:
        """Create aggressive risk calculator."""
        return cls(
            max_position_size=Percentage(Decimal("0.50")),  # 50%
            stop_loss=Percentage(Decimal("-0.07")),  # -7%
            take_profit=Percentage(Decimal("0.15")),  # +15%
            daily_loss_limit=Percentage(Decimal("-0.15")),  # -15%
            weekly_loss_limit=Percentage(Decimal("-0.25")),  # -25%
        )

    @classmethod
    def custom(
        cls,
        max_position_size: Percentage,
        stop_loss: Percentage,
        take_profit: Percentage,
        daily_loss_limit: Optional[Percentage] = None,
        weekly_loss_limit: Optional[Percentage] = None,
    ) -> RiskCalculator:
        """Create calculator with custom limits."""
        return cls(
            max_position_size=max_position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            daily_loss_limit=daily_loss_limit or Percentage(Decimal("-0.10")),
            weekly_loss_limit=weekly_loss_limit or Percentage(Decimal("-0.15")),
        )

    # --- Position Risk Assessment ---

    def assess_position_risk(
        self,
        position: Position,
        current_price: Money,
        portfolio_value: Money,
    ) -> RiskAssessment:
        """Assess risk for a single position."""
        reasons = []
        recommendations = []

        # Calculate metrics
        pnl_pct = position.profit_rate(current_price)
        position_value = position.current_value(current_price)
        position_size_pct = Percentage(
            position_value.amount / portfolio_value.amount
        )

        # Check stop loss
        if pnl_pct.value <= self.stop_loss.value:
            reasons.append(
                f"Stop loss triggered: {pnl_pct.as_points():.1f}% "
                f"<= {self.stop_loss.as_points():.1f}%"
            )
            return RiskAssessment(
                level=RiskLevel.CRITICAL,
                allowed=True,
                reasons=reasons,
                recommendations=["Exit position immediately"],
            )

        # Check take profit
        if pnl_pct.value >= self.take_profit.value:
            recommendations.append(
                f"Take profit target reached: {pnl_pct.as_points():.1f}% "
                f">= {self.take_profit.as_points():.1f}%"
            )

        # Determine risk level
        if pnl_pct.value < Decimal("-0.03"):
            level = RiskLevel.HIGH
            reasons.append(f"Position at significant loss: {pnl_pct.as_points():.1f}%")
        elif pnl_pct.value < Decimal("0"):
            level = RiskLevel.MEDIUM
            reasons.append(f"Position at minor loss: {pnl_pct.as_points():.1f}%")
        else:
            level = RiskLevel.LOW
            reasons.append(f"Position profitable: {pnl_pct.as_points():.1f}%")

        return RiskAssessment(
            level=level,
            allowed=True,
            reasons=reasons,
            recommendations=recommendations,
        )

    # --- Portfolio Risk Assessment ---

    def assess_portfolio_risk(
        self,
        portfolio_risk: PortfolioRisk,
    ) -> RiskAssessment:
        """Assess risk for entire portfolio."""
        reasons = []
        recommendations = []

        # Check daily limit
        if portfolio_risk.is_daily_limit_exceeded(self.daily_loss_limit):
            return RiskAssessment(
                level=RiskLevel.CRITICAL,
                allowed=False,
                reasons=[
                    f"Daily loss limit exceeded: {portfolio_risk.daily_pnl_pct.as_points():.1f}% "
                    f"< {self.daily_loss_limit.as_points():.1f}%"
                ],
                recommendations=["Stop trading for today"],
            )

        # Check weekly limit
        if portfolio_risk.is_weekly_limit_exceeded(self.weekly_loss_limit):
            return RiskAssessment(
                level=RiskLevel.CRITICAL,
                allowed=False,
                reasons=[
                    f"Weekly loss limit exceeded: {portfolio_risk.weekly_pnl_pct.as_points():.1f}% "
                    f"< {self.weekly_loss_limit.as_points():.1f}%"
                ],
                recommendations=["Stop trading for this week"],
            )

        # Determine risk level based on daily P&L
        daily_pnl_value = portfolio_risk.daily_pnl_pct.value
        if daily_pnl_value < self.daily_loss_limit.value * Decimal("0.7"):
            level = RiskLevel.HIGH
            reasons.append("Approaching daily loss limit")
            recommendations.append("Reduce position sizes")
        elif daily_pnl_value < Decimal("0"):
            level = RiskLevel.MEDIUM
            reasons.append(f"Daily P&L negative: {portfolio_risk.daily_pnl_pct}")
        else:
            level = RiskLevel.LOW
            reasons.append(f"Daily P&L positive: {portfolio_risk.daily_pnl_pct}")

        return RiskAssessment(
            level=level,
            allowed=True,
            reasons=reasons,
            recommendations=recommendations,
        )

    # --- Trade Size Validation ---

    def validate_trade_size(
        self,
        trade_amount: Money,
        portfolio_value: Money,
    ) -> RiskAssessment:
        """Validate if trade size is within limits."""
        size_pct = Percentage(trade_amount.amount / portfolio_value.amount)

        if size_pct.value > self.max_position_size.value:
            return RiskAssessment(
                level=RiskLevel.HIGH,
                allowed=False,
                reasons=[
                    f"Trade size {size_pct.as_points():.1f}% exceeds "
                    f"max position size {self.max_position_size.as_points():.1f}%"
                ],
                recommendations=[
                    f"Reduce trade size to max {self.calculate_max_position_size(portfolio_value)}"
                ],
            )

        return RiskAssessment(
            level=RiskLevel.LOW,
            allowed=True,
            reasons=[f"Trade size within limits: {size_pct.as_points():.1f}%"],
        )

    # --- Price Calculations ---

    def calculate_stop_loss_price(self, entry_price: Money) -> Money:
        """Calculate stop loss price from entry."""
        multiplier = Decimal("1") + self.stop_loss.value
        return Money(
            entry_price.amount * multiplier,
            entry_price.currency,
        ).round_for_currency()

    def calculate_take_profit_price(self, entry_price: Money) -> Money:
        """Calculate take profit price from entry."""
        multiplier = Decimal("1") + self.take_profit.value
        return Money(
            entry_price.amount * multiplier,
            entry_price.currency,
        ).round_for_currency()

    # --- Position Sizing ---

    def calculate_max_position_size(self, portfolio_value: Money) -> Money:
        """Calculate maximum allowed position size."""
        return Money(
            self.max_position_size.apply_to(portfolio_value.amount),
            portfolio_value.currency,
        ).round_for_currency()

    def calculate_recommended_position_size(
        self,
        portfolio_value: Money,
        risk_per_trade: Percentage,
    ) -> Money:
        """
        Calculate recommended position size based on risk.

        Uses simplified position sizing: risk_amount / stop_loss_distance
        """
        # Amount willing to risk
        risk_amount = risk_per_trade.apply_to(portfolio_value.amount)

        # Position size = risk_amount / |stop_loss|
        stop_loss_abs = abs(self.stop_loss.value)
        if stop_loss_abs == 0:
            # No stop loss set, use max position size
            return self.calculate_max_position_size(portfolio_value)

        position_size = risk_amount / stop_loss_abs

        # Cap at max position size
        max_size = self.max_position_size.apply_to(portfolio_value.amount)
        final_size = min(position_size, max_size)

        return Money(final_size, portfolio_value.currency).round_for_currency()
