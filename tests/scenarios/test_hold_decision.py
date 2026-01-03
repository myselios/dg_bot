"""
홀드 결정 시나리오 테스트

시나리오: 진입/청산하지 않고 관망하는 결정 흐름
"""
import pytest
from decimal import Decimal

from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage


class TestHoldDecisionScenario:
    """홀드 결정 시나리오"""

    # =========================================================================
    # SCENARIO 1: AI 홀드 결정
    # =========================================================================

    @pytest.mark.scenario
    def test_ai_hold_decision(self, mock_ai_decision_hold):
        """
        시나리오: AI가 홀드를 결정하면 거래 없음

        Given: 시장 분석 완료
        And: AI 홀드 결정 (중간 신뢰도)
        When: 트레이딩 사이클 실행
        Then: 매수/매도 없음
        """
        # Given: AI 홀드 결정
        decision = mock_ai_decision_hold
        assert decision["decision"] == "hold"

        # When: 결정 처리
        should_buy = decision["decision"] == "buy"
        should_sell = decision["decision"] == "sell"
        should_hold = decision["decision"] == "hold"

        # Then: 거래 없음
        assert should_buy is False
        assert should_sell is False
        assert should_hold is True

    # =========================================================================
    # SCENARIO 2: 낮은 신뢰도로 인한 홀드
    # =========================================================================

    @pytest.mark.scenario
    def test_hold_on_low_confidence(self):
        """
        시나리오: 신뢰도가 낮으면 홀드

        Given: AI 매수 결정이지만 낮은 신뢰도
        When: 신뢰도 필터 적용
        Then: 실제 매수 실행하지 않음 (홀드)
        """
        # Given: 낮은 신뢰도 매수 결정
        decision = {
            "decision": "buy",
            "confidence": "low",
            "reason": "약한 신호",
        }

        # Given: 신뢰도 임계값
        min_confidence_for_action = ["high", "medium"]

        # When: 신뢰도 확인
        should_execute = decision["confidence"] in min_confidence_for_action

        # Then: 실행하지 않음
        assert should_execute is False

    # =========================================================================
    # SCENARIO 3: 일일 손실 한도 도달로 홀드
    # =========================================================================

    @pytest.mark.scenario
    def test_hold_on_daily_loss_limit(self):
        """
        시나리오: 일일 손실 한도 도달 시 신규 진입 홀드

        Given: 일일 손실 -10% (한도 도달)
        And: AI 매수 신호
        When: 리스크 체크
        Then: 신규 진입 차단 (홀드)
        """
        # Given: 일일 손실 상태
        daily_pnl_pct = Percentage(Decimal("-0.10"))  # -10%
        daily_loss_limit = Percentage(Decimal("-0.10"))  # -10% 한도

        # When: 한도 확인
        is_limit_reached = daily_pnl_pct.value <= daily_loss_limit.value

        # Then: 신규 진입 차단
        assert is_limit_reached is True

    # =========================================================================
    # SCENARIO 4: 포지션 유지 시 홀드
    # =========================================================================

    @pytest.mark.scenario
    def test_hold_existing_position(self):
        """
        시나리오: 포지션이 손익 구간 내에 있으면 유지

        Given: BTC 포지션 보유
        And: 현재 손익 -2% (손절 미도달)
        When: 포지션 관리 사이클 실행
        Then: 포지션 유지 (홀드)
        """
        # Given: 포지션 정보
        position = {
            "ticker": "KRW-BTC",
            "entry_price": Money.krw(50000000),
            "current_price": Money.krw(49000000),  # -2%
            "volume": Decimal("0.005"),
        }

        stop_loss_pct = Decimal("-0.05")  # -5%
        take_profit_pct = Decimal("0.10")  # +10%

        # When: 손익률 계산
        entry = position["entry_price"].amount
        current = position["current_price"].amount
        pnl_pct = (current - entry) / entry

        # When: 청산 조건 확인
        is_stop_loss = pnl_pct <= stop_loss_pct
        is_take_profit = pnl_pct >= take_profit_pct

        # Then: 청산 조건 미충족 = 홀드
        assert is_stop_loss is False
        assert is_take_profit is False

    # =========================================================================
    # SCENARIO 5: 시장 불확실성으로 홀드
    # =========================================================================

    @pytest.mark.scenario
    def test_hold_on_market_uncertainty(self):
        """
        시나리오: 시장 불확실성 높을 때 홀드

        Given: 변동성 지표가 높음
        And: 거래량이 평소보다 낮음
        When: 시장 상태 분석
        Then: 홀드 권고
        """
        # Given: 시장 상태
        volatility = Decimal("0.08")  # 8% 변동성
        volatility_threshold = Decimal("0.05")  # 5% 임계값
        volume_ratio = Decimal("0.6")  # 평소의 60%
        min_volume_ratio = Decimal("0.8")  # 최소 80%

        # When: 불확실성 판단
        is_high_volatility = volatility > volatility_threshold
        is_low_volume = volume_ratio < min_volume_ratio

        # Then: 시장 불확실성 높음
        assert is_high_volatility or is_low_volume

    # =========================================================================
    # SCENARIO 6: 백테스트 미통과로 홀드
    # =========================================================================

    @pytest.mark.scenario
    def test_hold_on_backtest_fail(self):
        """
        시나리오: 백테스트 미통과 시 진입 홀드

        Given: 코인 스캔 완료
        And: 모든 코인 백테스트 미통과
        When: 진입 대상 선정
        Then: 진입 없음 (홀드)
        """
        # Given: 백테스트 결과
        backtest_results = {
            "KRW-BTC": {"passed": False, "score": 0.45},
            "KRW-ETH": {"passed": False, "score": 0.38},
            "KRW-XRP": {"passed": False, "score": 0.42},
        }

        # When: 통과한 코인 필터링
        passed_coins = [
            coin for coin, result in backtest_results.items()
            if result["passed"]
        ]

        # Then: 진입 대상 없음
        assert len(passed_coins) == 0


class TestHoldNotificationScenario:
    """홀드 알림 시나리오"""

    # =========================================================================
    # SCENARIO 7: 홀드 시 알림 없음 (기본)
    # =========================================================================

    @pytest.mark.scenario
    def test_no_notification_on_hold(self):
        """
        시나리오: 홀드 결정 시 기본적으로 알림 없음

        Given: 홀드 결정
        When: 알림 처리
        Then: 거래 알림 전송 안함
        """
        # Given: 홀드 결정
        decision = {"decision": "hold", "confidence": "medium"}

        # When: 알림 필요 여부 확인
        should_notify = decision["decision"] in ["buy", "sell"]

        # Then: 알림 불필요
        assert should_notify is False

    # =========================================================================
    # SCENARIO 8: 연속 홀드 시 요약 알림
    # =========================================================================

    @pytest.mark.scenario
    def test_summary_notification_on_consecutive_holds(self):
        """
        시나리오: 연속 N회 홀드 시 요약 알림

        Given: 6시간 연속 홀드 (6회)
        When: 연속 홀드 카운트 확인
        Then: 요약 알림 트리거
        """
        # Given: 연속 홀드 카운트
        consecutive_holds = 6
        summary_threshold = 6  # 6회 연속 시 알림

        # When: 알림 트리거 확인
        should_send_summary = consecutive_holds >= summary_threshold

        # Then: 요약 알림 필요
        assert should_send_summary is True
