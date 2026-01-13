"""
손절/익절 설정 전파 시나리오 테스트

손절/익절 설정이 모든 컴포넌트에 일관되게 전파되는지 검증합니다.

문제점 (PM-1, PM-4):
- 손절/익절 기본값이 3-4곳에 분산 정의됨
- SSOT 위반 (RiskManagementConfig 없음)

검증 항목:
- HybridRiskCheckStage 기본값
- 커스텀 손절/익절 값 적용
- 포지션 체크에서 손절/익절 트리거
"""
import pytest
from unittest.mock import MagicMock, patch

from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage


@pytest.mark.scenario
class TestStopLossPropagation:
    """손절/익절 설정 전파"""

    def test_default_values_are_consistent(self):
        """기본값이 일관되는지 확인"""
        # Given: 기대되는 기본값
        expected_stop_loss = -5.0
        expected_take_profit = 10.0

        # When: HybridRiskCheckStage 생성
        stage = HybridRiskCheckStage()

        # Then: 기본값이 일치해야 함
        assert stage.stop_loss_pct == expected_stop_loss, \
            f"기본 손절 비율이 {expected_stop_loss}%여야 함 (실제: {stage.stop_loss_pct}%)"
        assert stage.take_profit_pct == expected_take_profit, \
            f"기본 익절 비율이 {expected_take_profit}%여야 함 (실제: {stage.take_profit_pct}%)"

    def test_custom_values_are_applied(self):
        """커스텀 값이 적용되는지 확인"""
        # Given: 커스텀 손절/익절
        custom_stop = -3.0
        custom_profit = 15.0

        # When: 스테이지 생성
        stage = HybridRiskCheckStage(
            stop_loss_pct=custom_stop,
            take_profit_pct=custom_profit
        )

        # Then: 커스텀 값 적용
        assert stage.stop_loss_pct == custom_stop
        assert stage.take_profit_pct == custom_profit

    def test_stop_loss_range_validation(self):
        """손절 비율 유효 범위 테스트"""
        # 손절은 음수여야 함 (손실을 의미)
        stage = HybridRiskCheckStage(stop_loss_pct=-10.0)
        assert stage.stop_loss_pct == -10.0

        # 0보다 작아야 함
        stage = HybridRiskCheckStage(stop_loss_pct=-1.0)
        assert stage.stop_loss_pct == -1.0

    def test_take_profit_range_validation(self):
        """익절 비율 유효 범위 테스트"""
        # 익절은 양수여야 함 (이익을 의미)
        stage = HybridRiskCheckStage(take_profit_pct=5.0)
        assert stage.take_profit_pct == 5.0

        stage = HybridRiskCheckStage(take_profit_pct=50.0)
        assert stage.take_profit_pct == 50.0


@pytest.mark.scenario
class TestPositionCheckWithStopLoss:
    """포지션 체크에서 손절/익절 트리거 테스트"""

    @pytest.fixture
    def stage_with_defaults(self):
        """기본값으로 스테이지 생성"""
        return HybridRiskCheckStage()

    @pytest.fixture
    def mock_position(self):
        """Mock 포지션 생성 헬퍼"""
        def _create(pnl_pct: float):
            position = MagicMock()
            position.profit_rate = pnl_pct
            position.ticker = "KRW-BTC"
            position.volume = 0.01
            return position
        return _create

    def test_stop_loss_trigger(self, stage_with_defaults, mock_position):
        """손절 트리거 테스트 (기본 -5%)"""
        # Given: -6% 손실 (손절 조건 충족)
        position = mock_position(-6.0)
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage_with_defaults._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 손절 트리거
        assert result['action'] == 'sell'
        assert result['trigger'] == 'stop_loss'

    def test_stop_loss_boundary(self, stage_with_defaults, mock_position):
        """손절 경계값 테스트 (정확히 -5%)"""
        # Given: 정확히 -5% 손실
        position = mock_position(-5.0)
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage_with_defaults._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 손절 트리거 (경계값 포함)
        assert result['action'] == 'sell'
        assert result['trigger'] == 'stop_loss'

    def test_take_profit_trigger(self, stage_with_defaults, mock_position):
        """익절 트리거 테스트 (기본 +10%)"""
        # Given: +12% 이익 (익절 조건 충족)
        position = mock_position(12.0)
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage_with_defaults._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 익절 트리거
        assert result['action'] == 'sell'
        assert result['trigger'] == 'take_profit'

    def test_take_profit_boundary(self, stage_with_defaults, mock_position):
        """익절 경계값 테스트 (정확히 +10%)"""
        # Given: 정확히 +10% 이익
        position = mock_position(10.0)
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage_with_defaults._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 익절 트리거 (경계값 포함)
        assert result['action'] == 'sell'
        assert result['trigger'] == 'take_profit'

    def test_hold_in_neutral_zone(self, stage_with_defaults, mock_position):
        """중립 구간에서 보류 테스트"""
        # Given: 0% (손절도 익절도 아닌 상태)
        position = mock_position(0.0)
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage_with_defaults._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 보류
        assert result['action'] == 'hold'

    def test_hold_with_small_loss(self, stage_with_defaults, mock_position):
        """작은 손실에서 보류 테스트"""
        # Given: -3% 손실 (손절 조건 미충족)
        position = mock_position(-3.0)
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage_with_defaults._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 보류
        assert result['action'] == 'hold'

    def test_hold_with_small_profit(self, stage_with_defaults, mock_position):
        """작은 이익에서 보류 테스트"""
        # Given: +5% 이익 (익절 조건 미충족)
        position = mock_position(5.0)
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage_with_defaults._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 보류
        assert result['action'] == 'hold'


@pytest.mark.scenario
class TestCustomStopLossInPositionCheck:
    """커스텀 손절/익절 설정으로 포지션 체크 테스트"""

    @pytest.fixture
    def mock_position(self):
        """Mock 포지션 생성 헬퍼"""
        def _create(pnl_pct: float):
            position = MagicMock()
            position.profit_rate = pnl_pct
            position.ticker = "KRW-BTC"
            position.volume = 0.01
            return position
        return _create

    def test_tight_stop_loss_triggers_earlier(self, mock_position):
        """타이트한 손절 설정 테스트 (-3%)"""
        # Given: -3% 손절 설정
        stage = HybridRiskCheckStage(stop_loss_pct=-3.0)
        position = mock_position(-4.0)  # -4% 손실
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 손절 트리거 (-4% < -3%)
        assert result['action'] == 'sell'
        assert result['trigger'] == 'stop_loss'

    def test_loose_stop_loss_holds_longer(self, mock_position):
        """느슨한 손절 설정 테스트 (-10%)"""
        # Given: -10% 손절 설정
        stage = HybridRiskCheckStage(stop_loss_pct=-10.0)
        position = mock_position(-8.0)  # -8% 손실
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 보류 (-8% > -10%)
        assert result['action'] == 'hold'

    def test_low_take_profit_triggers_earlier(self, mock_position):
        """낮은 익절 설정 테스트 (+5%)"""
        # Given: +5% 익절 설정
        stage = HybridRiskCheckStage(take_profit_pct=5.0)
        position = mock_position(6.0)  # +6% 이익
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 익절 트리거 (+6% > +5%)
        assert result['action'] == 'sell'
        assert result['trigger'] == 'take_profit'

    def test_high_take_profit_holds_longer(self, mock_position):
        """높은 익절 설정 테스트 (+20%)"""
        # Given: +20% 익절 설정
        stage = HybridRiskCheckStage(take_profit_pct=20.0)
        position = mock_position(15.0)  # +15% 이익
        mock_context = MagicMock()

        # When: 규칙 체크
        result = stage._check_position_rules(
            position, position.profit_rate, mock_context
        )

        # Then: 보류 (+15% < +20%)
        assert result['action'] == 'hold'
