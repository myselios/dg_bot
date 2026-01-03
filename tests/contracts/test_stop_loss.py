"""
Stop-Loss 계약 테스트

계약: 손절 조건이 충족되면 반드시 청산 신호를 발생시켜야 함

이 테스트가 실패하면:
- 손절 실패로 인한 과도한 손실 발생 가능
- 거래 즉시 중단 필요
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.domain.services.risk_calculator import (
    RiskCalculator,
    RiskLevel,
    PositionRisk,
    PortfolioRisk,
)
from src.domain.entities.trade import Position
from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage


class TestStopLossContract:
    """손절 핵심 계약"""

    @pytest.fixture
    def risk_calculator(self):
        """기본 리스크 계산기 (-5% 손절)"""
        return RiskCalculator(
            max_position_size=Percentage(Decimal("0.30")),
            stop_loss=Percentage(Decimal("-0.05")),  # -5%
            take_profit=Percentage(Decimal("0.10")),
            daily_loss_limit=Percentage(Decimal("-0.10")),
            weekly_loss_limit=Percentage(Decimal("-0.15")),
        )

    @pytest.fixture
    def sample_position(self):
        """샘플 포지션 (진입가 5천만원)"""
        return Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.005"),
            avg_entry_price=Money.krw(50000000),
            entry_time=datetime.now() - timedelta(hours=1),
        )

    # =========================================================================
    # CONTRACT 1: 손절가 도달 시 HIGH/CRITICAL 리스크 반환
    # =========================================================================

    @pytest.mark.contract
    def test_stop_loss_trigger_at_threshold(self, risk_calculator, sample_position):
        """손절 임계값(-5%) 도달 시 HIGH 이상 리스크 반환"""
        # Given: 정확히 -5% 하락
        current_price = Money.krw(47500000)  # 50M * 0.95 = 47.5M
        portfolio_value = Money.krw(1000000)

        # When: 리스크 평가
        risk = risk_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )

        # Then: HIGH 또는 CRITICAL 리스크
        assert risk.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    @pytest.mark.contract
    def test_stop_loss_trigger_below_threshold(self, risk_calculator, sample_position):
        """손절 임계값 초과 하락 시 CRITICAL 리스크"""
        # Given: -10% 하락 (손절 초과)
        current_price = Money.krw(45000000)  # 50M * 0.90 = 45M
        portfolio_value = Money.krw(1000000)

        # When: 리스크 평가
        risk = risk_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )

        # Then: CRITICAL 리스크
        assert risk.level == RiskLevel.CRITICAL

    # =========================================================================
    # CONTRACT 2: 손절 미도달 시 LOW/MEDIUM 리스크
    # =========================================================================

    @pytest.mark.contract
    def test_no_stop_loss_when_price_above_threshold(self, risk_calculator, sample_position):
        """손절 미도달 시 LOW 리스크"""
        # Given: +2% 상승
        current_price = Money.krw(51000000)
        portfolio_value = Money.krw(1000000)

        # When: 리스크 평가
        risk = risk_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )

        # Then: LOW 리스크, 거래 허용
        assert risk.level == RiskLevel.LOW
        assert risk.allowed is True

    @pytest.mark.contract
    def test_no_stop_loss_at_small_loss(self, risk_calculator, sample_position):
        """작은 손실(-2%)에서는 손절 트리거 없음"""
        # Given: -2% 하락 (손절 미도달)
        current_price = Money.krw(49000000)
        portfolio_value = Money.krw(1000000)

        # When: 리스크 평가
        risk = risk_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )

        # Then: LOW 또는 MEDIUM (손절 미도달)
        assert risk.level in [RiskLevel.LOW, RiskLevel.MEDIUM]

    # =========================================================================
    # CONTRACT 3: 손절가 계산 정확성
    # =========================================================================

    @pytest.mark.contract
    def test_stop_loss_price_calculation_accuracy(self, risk_calculator):
        """손절가 계산이 정확해야 함"""
        # Given: 진입가
        entry_price = Money.krw(50000000)

        # When: 손절가 계산
        stop_price = risk_calculator.calculate_stop_loss_price(entry_price)

        # Then: 정확히 -5% = 47,500,000원
        assert stop_price == Money.krw(47500000)

    @pytest.mark.contract
    def test_stop_loss_price_deterministic(self, risk_calculator):
        """동일 진입가에 대해 항상 동일한 손절가 반환"""
        entry_price = Money.krw(50000000)

        # When: 여러 번 계산
        stop1 = risk_calculator.calculate_stop_loss_price(entry_price)
        stop2 = risk_calculator.calculate_stop_loss_price(entry_price)
        stop3 = risk_calculator.calculate_stop_loss_price(entry_price)

        # Then: 모두 동일
        assert stop1 == stop2 == stop3


class TestTakeProfitContract:
    """익절 계약 테스트"""

    @pytest.fixture
    def risk_calculator(self):
        """기본 리스크 계산기 (+10% 익절)"""
        return RiskCalculator(
            max_position_size=Percentage(Decimal("0.30")),
            stop_loss=Percentage(Decimal("-0.05")),
            take_profit=Percentage(Decimal("0.10")),  # +10%
            daily_loss_limit=Percentage(Decimal("-0.10")),
            weekly_loss_limit=Percentage(Decimal("-0.15")),
        )

    @pytest.fixture
    def sample_position(self):
        """샘플 포지션"""
        return Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.005"),
            avg_entry_price=Money.krw(50000000),
            entry_time=datetime.now() - timedelta(hours=1),
        )

    # =========================================================================
    # CONTRACT 4: 익절가 도달 시 권고 발생
    # =========================================================================

    @pytest.mark.contract
    def test_take_profit_recommendation_at_threshold(self, risk_calculator, sample_position):
        """익절 임계값(+10%) 도달 시 익절 권고 발생"""
        # Given: 정확히 +10% 상승
        current_price = Money.krw(55000000)  # 50M * 1.10 = 55M
        portfolio_value = Money.krw(1000000)

        # When: 리스크 평가
        risk = risk_calculator.assess_position_risk(
            sample_position, current_price, portfolio_value
        )

        # Then: 익절 권고 포함
        recommendations_str = str(risk.recommendations).lower()
        assert "take profit" in recommendations_str or "profit" in recommendations_str

    # =========================================================================
    # CONTRACT 5: 익절가 계산 정확성
    # =========================================================================

    @pytest.mark.contract
    def test_take_profit_price_calculation_accuracy(self, risk_calculator):
        """익절가 계산이 정확해야 함"""
        # Given: 진입가
        entry_price = Money.krw(50000000)

        # When: 익절가 계산
        tp_price = risk_calculator.calculate_take_profit_price(entry_price)

        # Then: 정확히 +10% = 55,000,000원
        assert tp_price == Money.krw(55000000)


class TestDailyLossLimitContract:
    """일일 손실 한도 계약"""

    @pytest.fixture
    def risk_calculator(self):
        """기본 리스크 계산기 (-10% 일일 한도)"""
        return RiskCalculator(
            max_position_size=Percentage(Decimal("0.30")),
            stop_loss=Percentage(Decimal("-0.05")),
            take_profit=Percentage(Decimal("0.10")),
            daily_loss_limit=Percentage(Decimal("-0.10")),  # -10%
            weekly_loss_limit=Percentage(Decimal("-0.15")),
        )

    # =========================================================================
    # CONTRACT 6: 일일 손실 한도 초과 시 거래 차단
    # =========================================================================

    @pytest.mark.contract
    def test_daily_loss_limit_blocks_trading(self, risk_calculator):
        """일일 손실 한도 초과 시 거래 차단"""
        # Given: 일일 -12% 손실 (한도 -10% 초과)
        portfolio_risk = PortfolioRisk(
            total_exposure=Money.krw(300000),
            exposure_pct=Percentage(Decimal("0.30")),
            daily_pnl=Money.krw(-120000),
            daily_pnl_pct=Percentage(Decimal("-0.12")),  # -12% > -10% limit
            weekly_pnl=Money.krw(-120000),
            weekly_pnl_pct=Percentage(Decimal("-0.12")),
            open_positions_count=1,
            largest_position_pct=Percentage(Decimal("0.30")),
        )

        # When: 리스크 평가
        risk = risk_calculator.assess_portfolio_risk(portfolio_risk)

        # Then: 거래 차단
        assert risk.allowed is False
        assert risk.level == RiskLevel.CRITICAL

    @pytest.mark.contract
    def test_within_daily_limit_allows_trading(self, risk_calculator):
        """일일 손실 한도 내에서는 거래 허용"""
        # Given: 일일 -5% 손실 (한도 내)
        portfolio_risk = PortfolioRisk(
            total_exposure=Money.krw(300000),
            exposure_pct=Percentage(Decimal("0.30")),
            daily_pnl=Money.krw(-50000),
            daily_pnl_pct=Percentage(Decimal("-0.05")),  # -5% < -10% limit
            weekly_pnl=Money.krw(-50000),
            weekly_pnl_pct=Percentage(Decimal("-0.05")),
            open_positions_count=1,
            largest_position_pct=Percentage(Decimal("0.30")),
        )

        # When: 리스크 평가
        risk = risk_calculator.assess_portfolio_risk(portfolio_risk)

        # Then: 거래 허용
        assert risk.allowed is True


class TestWeeklyLossLimitContract:
    """주간 손실 한도 계약"""

    @pytest.fixture
    def risk_calculator(self):
        """기본 리스크 계산기 (-15% 주간 한도)"""
        return RiskCalculator(
            max_position_size=Percentage(Decimal("0.30")),
            stop_loss=Percentage(Decimal("-0.05")),
            take_profit=Percentage(Decimal("0.10")),
            daily_loss_limit=Percentage(Decimal("-0.10")),
            weekly_loss_limit=Percentage(Decimal("-0.15")),  # -15%
        )

    # =========================================================================
    # CONTRACT 7: 주간 손실 한도 초과 시 거래 차단
    # =========================================================================

    @pytest.mark.contract
    def test_weekly_loss_limit_blocks_trading(self, risk_calculator):
        """주간 손실 한도 초과 시 거래 차단"""
        # Given: 주간 -18% 손실 (한도 -15% 초과)
        portfolio_risk = PortfolioRisk(
            total_exposure=Money.krw(300000),
            exposure_pct=Percentage(Decimal("0.30")),
            daily_pnl=Money.krw(-10000),
            daily_pnl_pct=Percentage(Decimal("-0.01")),
            weekly_pnl=Money.krw(-180000),
            weekly_pnl_pct=Percentage(Decimal("-0.18")),  # -18% > -15% limit
            open_positions_count=1,
            largest_position_pct=Percentage(Decimal("0.30")),
        )

        # When: 리스크 평가
        risk = risk_calculator.assess_portfolio_risk(portfolio_risk)

        # Then: 거래 차단
        assert risk.allowed is False
        assert risk.level == RiskLevel.CRITICAL
