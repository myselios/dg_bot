"""
Position Limit 계약 테스트

계약: 포지션 크기는 설정된 한도를 초과할 수 없음

이 테스트가 실패하면:
- 과도한 포지션으로 인한 리스크 발생 가능
- 거래 즉시 중단 필요
"""
import pytest
from decimal import Decimal

from src.domain.services.risk_calculator import RiskCalculator, RiskLevel
from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage


class TestPositionLimitContract:
    """포지션 한도 핵심 계약"""

    @pytest.fixture
    def risk_calculator(self):
        """기본 리스크 계산기 (30% 최대 포지션)"""
        return RiskCalculator(
            max_position_size=Percentage(Decimal("0.30")),  # 30%
            stop_loss=Percentage(Decimal("-0.05")),
            take_profit=Percentage(Decimal("0.10")),
            daily_loss_limit=Percentage(Decimal("-0.10")),
            weekly_loss_limit=Percentage(Decimal("-0.15")),
        )

    # =========================================================================
    # CONTRACT 1: 포지션 한도 내 거래 허용
    # =========================================================================

    @pytest.mark.contract
    def test_trade_within_limit_allowed(self, risk_calculator):
        """한도 내 거래는 허용되어야 함"""
        # Given: 25% 포지션 (30% 한도 내)
        trade_amount = Money.krw(250000)
        portfolio_value = Money.krw(1000000)

        # When: 거래 크기 검증
        assessment = risk_calculator.validate_trade_size(trade_amount, portfolio_value)

        # Then: 거래 허용
        assert assessment.allowed is True

    @pytest.mark.contract
    def test_trade_at_exact_limit_allowed(self, risk_calculator):
        """정확히 한도인 거래는 허용되어야 함"""
        # Given: 정확히 30% 포지션
        trade_amount = Money.krw(300000)
        portfolio_value = Money.krw(1000000)

        # When: 거래 크기 검증
        assessment = risk_calculator.validate_trade_size(trade_amount, portfolio_value)

        # Then: 거래 허용
        assert assessment.allowed is True

    # =========================================================================
    # CONTRACT 2: 포지션 한도 초과 거래 차단
    # =========================================================================

    @pytest.mark.contract
    def test_trade_exceeding_limit_blocked(self, risk_calculator):
        """한도 초과 거래는 차단되어야 함"""
        # Given: 40% 포지션 (30% 한도 초과)
        trade_amount = Money.krw(400000)
        portfolio_value = Money.krw(1000000)

        # When: 거래 크기 검증
        assessment = risk_calculator.validate_trade_size(trade_amount, portfolio_value)

        # Then: 거래 차단
        assert assessment.allowed is False

    @pytest.mark.contract
    def test_trade_way_over_limit_blocked(self, risk_calculator):
        """한도 크게 초과 거래는 차단되어야 함"""
        # Given: 80% 포지션 (30% 한도 크게 초과)
        trade_amount = Money.krw(800000)
        portfolio_value = Money.krw(1000000)

        # When: 거래 크기 검증
        assessment = risk_calculator.validate_trade_size(trade_amount, portfolio_value)

        # Then: 거래 차단
        assert assessment.allowed is False

    # =========================================================================
    # CONTRACT 3: 최대 포지션 크기 계산 정확성
    # =========================================================================

    @pytest.mark.contract
    def test_max_position_size_calculation_accurate(self, risk_calculator):
        """최대 포지션 크기 계산이 정확해야 함"""
        # Given: 포트폴리오 가치
        portfolio_value = Money.krw(1000000)

        # When: 최대 포지션 크기 계산
        max_size = risk_calculator.calculate_max_position_size(portfolio_value)

        # Then: 정확히 30% = 300,000원
        assert max_size == Money.krw(300000)

    @pytest.mark.contract
    def test_max_position_size_deterministic(self, risk_calculator):
        """동일 입력에 대해 항상 동일한 최대 크기 반환"""
        portfolio_value = Money.krw(1000000)

        # When: 여러 번 계산
        size1 = risk_calculator.calculate_max_position_size(portfolio_value)
        size2 = risk_calculator.calculate_max_position_size(portfolio_value)
        size3 = risk_calculator.calculate_max_position_size(portfolio_value)

        # Then: 모두 동일
        assert size1 == size2 == size3

    # =========================================================================
    # CONTRACT 4: 다양한 한도 설정 지원
    # =========================================================================

    @pytest.mark.contract
    def test_conservative_position_limit(self):
        """보수적 설정 (20%) 작동 확인"""
        calc = RiskCalculator.conservative()

        trade_amount = Money.krw(250000)  # 25%
        portfolio_value = Money.krw(1000000)

        assessment = calc.validate_trade_size(trade_amount, portfolio_value)

        # 25% > 20% 한도 → 차단
        assert assessment.allowed is False

    @pytest.mark.contract
    def test_aggressive_position_limit(self):
        """공격적 설정 (50%) 작동 확인"""
        calc = RiskCalculator.aggressive()

        trade_amount = Money.krw(450000)  # 45%
        portfolio_value = Money.krw(1000000)

        assessment = calc.validate_trade_size(trade_amount, portfolio_value)

        # 45% < 50% 한도 → 허용
        assert assessment.allowed is True

    # =========================================================================
    # CONTRACT 5: 제로/최소 금액 처리
    # =========================================================================

    @pytest.mark.contract
    def test_zero_trade_allowed(self, risk_calculator):
        """0원 거래는 허용되어야 함 (실제로는 실행 안됨)"""
        trade_amount = Money.krw(0)
        portfolio_value = Money.krw(1000000)

        assessment = risk_calculator.validate_trade_size(trade_amount, portfolio_value)

        assert assessment.allowed is True

    @pytest.mark.contract
    def test_tiny_trade_allowed(self, risk_calculator):
        """아주 작은 거래는 허용되어야 함"""
        trade_amount = Money.krw(1)
        portfolio_value = Money.krw(1000000)

        assessment = risk_calculator.validate_trade_size(trade_amount, portfolio_value)

        assert assessment.allowed is True


class TestRiskCalculatorFactoryContract:
    """리스크 계산기 팩토리 계약"""

    # =========================================================================
    # CONTRACT 6: 팩토리 메서드 일관성
    # =========================================================================

    @pytest.mark.contract
    def test_conservative_factory_values(self):
        """보수적 팩토리는 올바른 값을 설정해야 함"""
        calc = RiskCalculator.conservative()

        assert calc.max_position_size.as_points() == Decimal("20")  # 20%
        assert calc.stop_loss.as_points() == Decimal("-3")  # -3%

    @pytest.mark.contract
    def test_moderate_factory_values(self):
        """중립적 팩토리는 올바른 값을 설정해야 함"""
        calc = RiskCalculator.moderate()

        assert calc.max_position_size.as_points() == Decimal("30")  # 30%
        assert calc.stop_loss.as_points() == Decimal("-5")  # -5%

    @pytest.mark.contract
    def test_aggressive_factory_values(self):
        """공격적 팩토리는 올바른 값을 설정해야 함"""
        calc = RiskCalculator.aggressive()

        assert calc.max_position_size.as_points() == Decimal("50")  # 50%
        assert calc.stop_loss.as_points() == Decimal("-7")  # -7%

    @pytest.mark.contract
    def test_custom_factory_accepts_values(self):
        """커스텀 팩토리는 사용자 정의 값을 수용해야 함"""
        calc = RiskCalculator.custom(
            max_position_size=Percentage(Decimal("0.25")),
            stop_loss=Percentage(Decimal("-0.04")),
            take_profit=Percentage(Decimal("0.08")),
        )

        assert calc.max_position_size.as_points() == Decimal("25")
        assert calc.stop_loss.as_points() == Decimal("-4")
        assert calc.take_profit.as_points() == Decimal("8")
