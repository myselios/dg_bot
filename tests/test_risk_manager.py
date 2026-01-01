"""
리스크 관리자 테스트
TDD 원칙: 테스트 케이스를 먼저 작성하고 구현을 검증합니다.
"""
import pytest
from datetime import datetime, timedelta
from src.risk.manager import RiskManager, RiskLimits


class TestRiskLimits:
    """RiskLimits 설정 클래스 테스트"""

    @pytest.mark.unit
    def test_default_risk_limits(self):
        """기본 리스크 한도 설정 테스트"""
        # Given
        limits = RiskLimits()

        # Then
        assert limits.stop_loss_pct == -5.0
        assert limits.take_profit_pct == 10.0
        assert limits.daily_loss_limit_pct == -10.0
        assert limits.min_trade_interval_hours == 4
        assert limits.max_daily_trades == 5

    @pytest.mark.unit
    def test_custom_risk_limits(self):
        """커스텀 리스크 한도 설정 테스트"""
        # Given
        limits = RiskLimits(
            stop_loss_pct=-3.0,
            take_profit_pct=7.0,
            daily_loss_limit_pct=-8.0
        )

        # Then
        assert limits.stop_loss_pct == -3.0
        assert limits.take_profit_pct == 7.0
        assert limits.daily_loss_limit_pct == -8.0


class TestRiskManager:
    """RiskManager 클래스 테스트"""

    @pytest.fixture
    def risk_manager(self):
        """테스트용 리스크 관리자 생성 (State Persistence 비활성화)"""
        return RiskManager(persist_state=False)

    @pytest.fixture
    def sample_position(self):
        """샘플 포지션 데이터"""
        return {
            'avg_buy_price': 4000000,  # 400만원
            'amount': 0.1,
            'current_price': 4000000
        }

    # ============================================
    # check_position_limits() 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_position_limits_no_position(self, risk_manager):
        """포지션이 없을 때 테스트"""
        # Given
        position = None
        current_price = 4000000

        # When
        result = risk_manager.check_position_limits(position, current_price)

        # Then
        assert result['action'] == 'hold'
        assert result['pnl_pct'] == 0.0
        assert '포지션 없음' in result['reason']

    @pytest.mark.unit
    def test_check_position_limits_stop_loss_triggered(self, risk_manager, sample_position):
        """손절 발동 테스트 (-5% 이하)"""
        # Given
        current_price = 3800000  # -5% 손실

        # When
        result = risk_manager.check_position_limits(sample_position, current_price)

        # Then
        assert result['action'] == 'stop_loss'
        assert result['pnl_pct'] == -5.0
        assert '손절' in result['reason']

    @pytest.mark.unit
    def test_check_position_limits_take_profit_triggered(self, risk_manager, sample_position):
        """익절 발동 테스트 (+10% 이상)"""
        # Given
        current_price = 4400000  # +10% 수익

        # When
        result = risk_manager.check_position_limits(sample_position, current_price)

        # Then
        assert result['action'] == 'take_profit'
        assert result['pnl_pct'] == 10.0
        assert '익절' in result['reason']

    @pytest.mark.unit
    def test_check_position_limits_hold(self, risk_manager, sample_position):
        """포지션 유지 테스트 (-5% ~ +10% 사이)"""
        # Given
        current_price = 4100000  # +2.5% 수익

        # When
        result = risk_manager.check_position_limits(sample_position, current_price)

        # Then
        assert result['action'] == 'hold'
        assert -5.0 < result['pnl_pct'] < 10.0

    @pytest.mark.unit
    def test_check_position_limits_custom_limits(self, sample_position):
        """커스텀 리스크 한도 테스트"""
        # Given
        custom_limits = RiskLimits(
            stop_loss_pct=-3.0,
            take_profit_pct=7.0
        )
        risk_manager = RiskManager(limits=custom_limits)
        current_price = 3880000  # -3% 손실

        # When
        result = risk_manager.check_position_limits(sample_position, current_price)

        # Then
        assert result['action'] == 'stop_loss'
        assert result['pnl_pct'] == -3.0

    # ============================================
    # check_circuit_breaker() 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_circuit_breaker_allowed(self, risk_manager):
        """정상 거래 가능 테스트"""
        # Given
        risk_manager.daily_pnl = -5.0  # -5% 손실
        risk_manager.weekly_pnl = -7.0

        # When
        result = risk_manager.check_circuit_breaker()

        # Then
        assert result['allowed'] is True
        assert '정상' in result['reason']

    @pytest.mark.unit
    def test_check_circuit_breaker_daily_loss_exceeded(self, risk_manager):
        """일일 손실 한도 초과 테스트"""
        # Given
        risk_manager.daily_pnl = -12.0  # -12% 손실 (한도: -10%)

        # When
        result = risk_manager.check_circuit_breaker()

        # Then
        assert result['allowed'] is False
        assert '일일 손실 한도 초과' in result['reason']
        assert risk_manager.safe_mode is True

    @pytest.mark.unit
    def test_check_circuit_breaker_weekly_loss_exceeded(self, risk_manager):
        """주간 손실 한도 초과 테스트"""
        # Given
        risk_manager.daily_pnl = -5.0
        risk_manager.weekly_pnl = -18.0  # -18% 손실 (한도: -15%)

        # When
        result = risk_manager.check_circuit_breaker()

        # Then
        assert result['allowed'] is False
        assert '주간 손실 한도 초과' in result['reason']
        assert risk_manager.safe_mode is True

    # ============================================
    # check_trade_frequency() 테스트
    # ============================================

    @pytest.mark.unit
    def test_check_trade_frequency_first_trade(self, risk_manager):
        """첫 거래 테스트"""
        # Given
        risk_manager.last_trade_time = None

        # When
        result = risk_manager.check_trade_frequency()

        # Then
        assert result['allowed'] is True
        assert '첫 거래' in result['reason']

    @pytest.mark.unit
    def test_check_trade_frequency_interval_not_met(self, risk_manager):
        """최소 거래 간격 미달 테스트"""
        # Given
        risk_manager.last_trade_time = datetime.now() - timedelta(hours=2)

        # When
        result = risk_manager.check_trade_frequency()

        # Then
        assert result['allowed'] is False
        assert '최소 거래 간격 미달' in result['reason']

    @pytest.mark.unit
    def test_check_trade_frequency_interval_met(self, risk_manager):
        """최소 거래 간격 충족 테스트"""
        # Given
        risk_manager.last_trade_time = datetime.now() - timedelta(hours=5)
        risk_manager.daily_trade_count = 2

        # When
        result = risk_manager.check_trade_frequency()

        # Then
        assert result['allowed'] is True

    @pytest.mark.unit
    def test_check_trade_frequency_max_daily_trades_exceeded(self, risk_manager):
        """일일 최대 거래 횟수 초과 테스트"""
        # Given
        risk_manager.last_trade_time = datetime.now() - timedelta(hours=5)
        risk_manager.daily_trade_count = 5  # 최대 5회

        # When
        result = risk_manager.check_trade_frequency()

        # Then
        assert result['allowed'] is False
        assert '일일 최대 거래 횟수 초과' in result['reason']

    # ============================================
    # calculate_kelly_position_size() 테스트
    # ============================================

    @pytest.mark.unit
    def test_calculate_kelly_position_size_normal(self, risk_manager):
        """정상적인 Kelly Criterion 포지션 사이징 테스트"""
        # Given
        win_rate = 0.6  # 60% 승률
        avg_win = 10.0  # 평균 수익 10%
        avg_loss = -5.0  # 평균 손실 -5%
        current_capital = 1000000  # 100만원

        # When
        position_size = risk_manager.calculate_kelly_position_size(
            win_rate, avg_win, avg_loss, current_capital
        )

        # Then
        assert 50000 <= position_size <= 300000  # 5% ~ 30% 범위
        assert isinstance(position_size, float)

    @pytest.mark.unit
    def test_calculate_kelly_position_size_low_win_rate(self, risk_manager):
        """낮은 승률에서 Kelly Criterion 테스트"""
        # Given
        win_rate = 0.3  # 30% 승률 (낮음)
        avg_win = 15.0
        avg_loss = -5.0
        current_capital = 1000000

        # When
        position_size = risk_manager.calculate_kelly_position_size(
            win_rate, avg_win, avg_loss, current_capital
        )

        # Then
        # 낮은 승률이므로 최소 포지션 크기(5%)
        assert position_size == current_capital * 0.05

    @pytest.mark.unit
    def test_calculate_kelly_position_size_high_win_rate(self, risk_manager):
        """높은 승률에서 Kelly Criterion 테스트"""
        # Given
        win_rate = 0.8  # 80% 승률 (높음)
        avg_win = 12.0
        avg_loss = -5.0
        current_capital = 1000000

        # When
        position_size = risk_manager.calculate_kelly_position_size(
            win_rate, avg_win, avg_loss, current_capital
        )

        # Then
        # 높은 승률이므로 최대 포지션 크기(30%)
        assert position_size == current_capital * 0.30

    @pytest.mark.unit
    def test_calculate_kelly_position_size_edge_case_zero_loss(self, risk_manager):
        """평균 손실이 0인 경우 (엣지 케이스)"""
        # Given
        win_rate = 0.6
        avg_win = 10.0
        avg_loss = 0  # 손실 없음 (비현실적이지만 엣지 케이스)
        current_capital = 1000000

        # When
        position_size = risk_manager.calculate_kelly_position_size(
            win_rate, avg_win, avg_loss, current_capital
        )

        # Then
        # Fallback: 기본 10%
        assert position_size == current_capital * 0.1

    # ============================================
    # record_trade() 테스트
    # ============================================

    @pytest.mark.unit
    def test_record_trade(self, risk_manager):
        """거래 기록 테스트"""
        # Given
        pnl_pct = 5.0  # +5% 수익

        # When
        risk_manager.record_trade(pnl_pct)

        # Then
        assert risk_manager.last_trade_time is not None
        assert risk_manager.daily_trade_count == 1
        assert risk_manager.daily_pnl == 5.0
        assert risk_manager.weekly_pnl == 5.0

    @pytest.mark.unit
    def test_record_multiple_trades(self, risk_manager):
        """여러 거래 기록 테스트"""
        # Given & When
        risk_manager.record_trade(3.0)   # +3%
        risk_manager.record_trade(-2.0)  # -2%
        risk_manager.record_trade(5.0)   # +5%

        # Then
        assert risk_manager.daily_trade_count == 3
        assert risk_manager.daily_pnl == 6.0  # 3 - 2 + 5
        assert risk_manager.weekly_pnl == 6.0

    # ============================================
    # 안전 모드 테스트
    # ============================================

    @pytest.mark.unit
    def test_enable_safe_mode(self, risk_manager):
        """안전 모드 활성화 테스트"""
        # Given
        reason = "테스트 안전 모드"

        # When
        risk_manager.enable_safe_mode(reason)

        # Then
        assert risk_manager.safe_mode is True
        assert risk_manager.safe_mode_reason == reason

    @pytest.mark.unit
    def test_disable_safe_mode(self, risk_manager):
        """안전 모드 해제 테스트"""
        # Given
        risk_manager.enable_safe_mode("테스트")

        # When
        risk_manager.disable_safe_mode()

        # Then
        assert risk_manager.safe_mode is False
        assert risk_manager.safe_mode_reason == ""

    # ============================================
    # 통계 초기화 테스트
    # ============================================

    @pytest.mark.unit
    def test_reset_daily_stats(self, risk_manager):
        """일일 통계 초기화 테스트"""
        # Given
        risk_manager.daily_trade_count = 5
        risk_manager.daily_pnl = -10.0

        # When
        risk_manager.reset_daily_stats()

        # Then
        assert risk_manager.daily_trade_count == 0
        assert risk_manager.daily_pnl == 0.0

    @pytest.mark.unit
    def test_reset_weekly_stats(self, risk_manager):
        """주간 통계 초기화 테스트"""
        # Given
        risk_manager.weekly_pnl = -15.0

        # When
        risk_manager.reset_weekly_stats()

        # Then
        assert risk_manager.weekly_pnl == 0.0
