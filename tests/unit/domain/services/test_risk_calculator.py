"""
Tests for RiskCalculator domain service.
TDD RED Phase - These tests should fail until implementation.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.domain.services.risk_calculator import (
    RiskCalculator,
    RiskAssessment,
    RiskLevel,
    PositionRisk,
    PortfolioRisk,
)
from src.domain.entities.trade import Position, OrderSide
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_low_risk_level(self):
        """LOW risk level should be available."""
        assert RiskLevel.LOW.value == "low"

    def test_medium_risk_level(self):
        """MEDIUM risk level should be available."""
        assert RiskLevel.MEDIUM.value == "medium"

    def test_high_risk_level(self):
        """HIGH risk level should be available."""
        assert RiskLevel.HIGH.value == "high"

    def test_critical_risk_level(self):
        """CRITICAL risk level should be available."""
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_ordering(self):
        """Risk levels should be orderable."""
        assert RiskLevel.LOW < RiskLevel.MEDIUM
        assert RiskLevel.MEDIUM < RiskLevel.HIGH
        assert RiskLevel.HIGH < RiskLevel.CRITICAL


class TestRiskAssessment:
    """Tests for RiskAssessment value object."""

    def test_create_risk_assessment(self):
        """Should create RiskAssessment with all fields."""
        assessment = RiskAssessment(
            level=RiskLevel.MEDIUM,
            allowed=True,
            reasons=["Position size within limits"],
            recommendations=["Consider reducing exposure"],
        )
        assert assessment.level == RiskLevel.MEDIUM
        assert assessment.allowed is True
        assert len(assessment.reasons) == 1
        assert len(assessment.recommendations) == 1

    def test_is_trade_allowed(self):
        """Should check if trade is allowed."""
        allowed = RiskAssessment(
            level=RiskLevel.LOW,
            allowed=True,
            reasons=[],
        )
        assert allowed.is_trade_allowed()

        blocked = RiskAssessment(
            level=RiskLevel.CRITICAL,
            allowed=False,
            reasons=["Daily loss limit exceeded"],
        )
        assert not blocked.is_trade_allowed()


class TestPositionRisk:
    """Tests for PositionRisk calculation."""

    def test_create_position_risk(self):
        """Should create PositionRisk with metrics."""
        risk = PositionRisk(
            position_size_pct=Percentage(Decimal("0.10")),  # 10% of portfolio
            unrealized_pnl=Money.krw(-5000),
            unrealized_pnl_pct=Percentage(Decimal("-0.05")),  # -5%
            holding_hours=24.0,
            stop_loss_distance=Percentage(Decimal("0.03")),  # 3% away
            take_profit_distance=Percentage(Decimal("0.07")),  # 7% away
        )
        assert risk.position_size_pct.as_points() == Decimal("10")
        assert risk.unrealized_pnl_pct.is_negative()

    def test_is_at_stop_loss(self):
        """Should detect if position is at stop loss."""
        risk = PositionRisk(
            position_size_pct=Percentage(Decimal("0.10")),
            unrealized_pnl=Money.krw(-5000),
            unrealized_pnl_pct=Percentage(Decimal("-0.05")),
            holding_hours=1.0,
            stop_loss_distance=Percentage(Decimal("0")),  # At stop loss
            take_profit_distance=Percentage(Decimal("0.15")),
        )
        assert risk.is_at_stop_loss()

    def test_is_at_take_profit(self):
        """Should detect if position is at take profit."""
        risk = PositionRisk(
            position_size_pct=Percentage(Decimal("0.10")),
            unrealized_pnl=Money.krw(10000),
            unrealized_pnl_pct=Percentage(Decimal("0.10")),
            holding_hours=1.0,
            stop_loss_distance=Percentage(Decimal("0.15")),
            take_profit_distance=Percentage(Decimal("0")),  # At take profit
        )
        assert risk.is_at_take_profit()


class TestPortfolioRisk:
    """Tests for PortfolioRisk calculation."""

    def test_create_portfolio_risk(self):
        """Should create PortfolioRisk with daily/weekly metrics."""
        risk = PortfolioRisk(
            total_exposure=Money.krw(500000),
            exposure_pct=Percentage(Decimal("0.50")),  # 50% invested
            daily_pnl=Money.krw(-10000),
            daily_pnl_pct=Percentage(Decimal("-0.01")),  # -1%
            weekly_pnl=Money.krw(-30000),
            weekly_pnl_pct=Percentage(Decimal("-0.03")),  # -3%
            open_positions_count=3,
            largest_position_pct=Percentage(Decimal("0.20")),  # 20%
        )
        assert risk.total_exposure == Money.krw(500000)
        assert risk.open_positions_count == 3

    def test_is_daily_limit_exceeded(self):
        """Should detect daily loss limit breach."""
        risk = PortfolioRisk(
            total_exposure=Money.krw(500000),
            exposure_pct=Percentage(Decimal("0.50")),
            daily_pnl=Money.krw(-100000),
            daily_pnl_pct=Percentage(Decimal("-0.10")),  # -10%
            weekly_pnl=Money.krw(-100000),
            weekly_pnl_pct=Percentage(Decimal("-0.10")),
            open_positions_count=1,
            largest_position_pct=Percentage(Decimal("0.50")),
        )
        limit = Percentage(Decimal("-0.05"))  # -5% daily limit
        assert risk.is_daily_limit_exceeded(limit)

    def test_is_weekly_limit_exceeded(self):
        """Should detect weekly loss limit breach."""
        risk = PortfolioRisk(
            total_exposure=Money.krw(500000),
            exposure_pct=Percentage(Decimal("0.50")),
            daily_pnl=Money.krw(-10000),
            daily_pnl_pct=Percentage(Decimal("-0.01")),
            weekly_pnl=Money.krw(-200000),
            weekly_pnl_pct=Percentage(Decimal("-0.20")),  # -20%
            open_positions_count=1,
            largest_position_pct=Percentage(Decimal("0.50")),
        )
        limit = Percentage(Decimal("-0.15"))  # -15% weekly limit
        assert risk.is_weekly_limit_exceeded(limit)


class TestRiskCalculator:
    """Tests for RiskCalculator domain service."""

    @pytest.fixture
    def default_calculator(self):
        """Create calculator with default risk limits."""
        return RiskCalculator(
            max_position_size=Percentage(Decimal("0.30")),  # 30% max
            stop_loss=Percentage(Decimal("-0.05")),  # -5%
            take_profit=Percentage(Decimal("0.10")),  # +10%
            daily_loss_limit=Percentage(Decimal("-0.10")),  # -10%
            weekly_loss_limit=Percentage(Decimal("-0.15")),  # -15%
        )

    @pytest.fixture
    def sample_position(self):
        """Create sample position for testing."""
        return Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.005"),
            avg_entry_price=Money.krw(50000000),
            entry_time=datetime.now() - timedelta(hours=2),
        )

    # --- Position Risk Assessment ---

    def test_assess_position_risk_low(self, default_calculator, sample_position):
        """Should assess low risk for profitable position."""
        current_price = Money.krw(52000000)  # +4% gain
        portfolio_value = Money.krw(1000000)

        risk = default_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )
        assert risk.level == RiskLevel.LOW
        assert risk.allowed is True

    def test_assess_position_risk_stop_loss_trigger(
        self, default_calculator, sample_position
    ):
        """Should trigger stop loss at -5%."""
        current_price = Money.krw(47500000)  # -5%
        portfolio_value = Money.krw(1000000)

        risk = default_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )
        assert risk.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert "stop loss" in str(risk.reasons).lower()

    def test_assess_position_risk_take_profit_trigger(
        self, default_calculator, sample_position
    ):
        """Should trigger take profit at +10%."""
        current_price = Money.krw(55000000)  # +10%
        portfolio_value = Money.krw(1000000)

        risk = default_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )
        assert "take profit" in str(risk.recommendations).lower()

    # --- Portfolio Risk Assessment ---

    def test_assess_portfolio_risk_allowed(self, default_calculator):
        """Should allow trading when within limits."""
        portfolio_risk = PortfolioRisk(
            total_exposure=Money.krw(300000),
            exposure_pct=Percentage(Decimal("0.30")),
            daily_pnl=Money.krw(-20000),
            daily_pnl_pct=Percentage(Decimal("-0.02")),
            weekly_pnl=Money.krw(-50000),
            weekly_pnl_pct=Percentage(Decimal("-0.05")),
            open_positions_count=2,
            largest_position_pct=Percentage(Decimal("0.20")),
        )

        risk = default_calculator.assess_portfolio_risk(portfolio_risk)
        assert risk.allowed is True

    def test_assess_portfolio_risk_daily_limit_exceeded(self, default_calculator):
        """Should block trading when daily limit exceeded."""
        portfolio_risk = PortfolioRisk(
            total_exposure=Money.krw(300000),
            exposure_pct=Percentage(Decimal("0.30")),
            daily_pnl=Money.krw(-120000),
            daily_pnl_pct=Percentage(Decimal("-0.12")),  # > -10%
            weekly_pnl=Money.krw(-120000),
            weekly_pnl_pct=Percentage(Decimal("-0.12")),
            open_positions_count=1,
            largest_position_pct=Percentage(Decimal("0.30")),
        )

        risk = default_calculator.assess_portfolio_risk(portfolio_risk)
        assert risk.allowed is False
        assert risk.level == RiskLevel.CRITICAL
        assert "daily" in str(risk.reasons).lower()

    def test_assess_portfolio_risk_weekly_limit_exceeded(self, default_calculator):
        """Should block trading when weekly limit exceeded."""
        portfolio_risk = PortfolioRisk(
            total_exposure=Money.krw(300000),
            exposure_pct=Percentage(Decimal("0.30")),
            daily_pnl=Money.krw(-10000),
            daily_pnl_pct=Percentage(Decimal("-0.01")),
            weekly_pnl=Money.krw(-180000),
            weekly_pnl_pct=Percentage(Decimal("-0.18")),  # > -15%
            open_positions_count=1,
            largest_position_pct=Percentage(Decimal("0.30")),
        )

        risk = default_calculator.assess_portfolio_risk(portfolio_risk)
        assert risk.allowed is False
        assert risk.level == RiskLevel.CRITICAL
        assert "weekly" in str(risk.reasons).lower()

    # --- Trade Size Validation ---

    def test_validate_trade_size_within_limit(self, default_calculator):
        """Should allow trade within position size limit."""
        trade_amount = Money.krw(250000)
        portfolio_value = Money.krw(1000000)

        assessment = default_calculator.validate_trade_size(
            trade_amount, portfolio_value
        )
        assert assessment.allowed is True

    def test_validate_trade_size_exceeds_limit(self, default_calculator):
        """Should reject trade exceeding position size limit."""
        trade_amount = Money.krw(400000)  # 40% > 30% max
        portfolio_value = Money.krw(1000000)

        assessment = default_calculator.validate_trade_size(
            trade_amount, portfolio_value
        )
        assert assessment.allowed is False
        assert "size" in str(assessment.reasons).lower()

    # --- Stop Loss / Take Profit Calculation ---

    def test_calculate_stop_loss_price(self, default_calculator):
        """Should calculate stop loss price."""
        entry_price = Money.krw(50000000)
        stop_price = default_calculator.calculate_stop_loss_price(entry_price)
        # -5% = 47,500,000
        assert stop_price == Money.krw(47500000)

    def test_calculate_take_profit_price(self, default_calculator):
        """Should calculate take profit price."""
        entry_price = Money.krw(50000000)
        tp_price = default_calculator.calculate_take_profit_price(entry_price)
        # +10% = 55,000,000
        assert tp_price == Money.krw(55000000)

    # --- Position Sizing ---

    def test_calculate_max_position_size(self, default_calculator):
        """Should calculate maximum allowed position size."""
        portfolio_value = Money.krw(1000000)
        max_size = default_calculator.calculate_max_position_size(portfolio_value)
        # 30% of 1M = 300,000
        assert max_size == Money.krw(300000)

    def test_calculate_recommended_position_size(self, default_calculator):
        """Should calculate recommended size based on risk."""
        portfolio_value = Money.krw(1000000)
        risk_per_trade = Percentage(Decimal("0.02"))  # 2% risk

        size = default_calculator.calculate_recommended_position_size(
            portfolio_value, risk_per_trade
        )
        # Risk-adjusted sizing
        assert size.amount > Decimal("0")
        assert size <= default_calculator.calculate_max_position_size(portfolio_value)


class TestRiskCalculatorFactory:
    """Tests for RiskCalculator factory methods."""

    def test_create_conservative_calculator(self):
        """Should create conservative risk calculator."""
        calc = RiskCalculator.conservative()
        assert calc.max_position_size.as_points() == Decimal("20")  # 20%
        assert calc.stop_loss.as_points() == Decimal("-3")  # -3%

    def test_create_moderate_calculator(self):
        """Should create moderate risk calculator."""
        calc = RiskCalculator.moderate()
        assert calc.max_position_size.as_points() == Decimal("30")  # 30%
        assert calc.stop_loss.as_points() == Decimal("-5")  # -5%

    def test_create_aggressive_calculator(self):
        """Should create aggressive risk calculator."""
        calc = RiskCalculator.aggressive()
        assert calc.max_position_size.as_points() == Decimal("50")  # 50%
        assert calc.stop_loss.as_points() == Decimal("-7")  # -7%

    def test_create_custom_calculator(self):
        """Should create calculator with custom limits."""
        calc = RiskCalculator.custom(
            max_position_size=Percentage(Decimal("0.25")),
            stop_loss=Percentage(Decimal("-0.04")),
            take_profit=Percentage(Decimal("0.08")),
        )
        assert calc.max_position_size.as_points() == Decimal("25")
        assert calc.stop_loss.as_points() == Decimal("-4")
