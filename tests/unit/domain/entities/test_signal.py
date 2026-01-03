"""
Signal 엔티티 테스트

TDD: Red → Green → Refactor
"""
import pytest
from datetime import datetime
from decimal import Decimal

from src.domain.entities.signal import Signal, SignalAction
from src.domain.value_objects import Money, Percentage


class TestSignal:
    """Signal 엔티티 테스트"""

    def test_create_buy_signal(self):
        """Given: 매수 신호 파라미터
        When: Signal 생성
        Then: 올바른 속성 설정"""
        signal = Signal(
            action=SignalAction.BUY,
            price=Money.krw(50000000),
            size=Decimal("0.001"),
            stop_loss=Money.krw(49000000),
            take_profit=Money.krw(52000000),
            reason={"strategy": "volatility_breakout"}
        )

        assert signal.action == SignalAction.BUY
        assert signal.price == Money.krw(50000000)
        assert signal.size == Decimal("0.001")
        assert signal.stop_loss == Money.krw(49000000)
        assert signal.take_profit == Money.krw(52000000)
        assert signal.reason["strategy"] == "volatility_breakout"

    def test_create_sell_signal(self):
        """Given: 매도 신호 파라미터
        When: Signal 생성
        Then: 올바른 속성 설정"""
        signal = Signal(
            action=SignalAction.SELL,
            price=Money.krw(51000000),
            reason={"type": "stop_loss"}
        )

        assert signal.action == SignalAction.SELL
        assert signal.price == Money.krw(51000000)
        assert signal.size is None
        assert signal.stop_loss is None

    def test_create_close_signal(self):
        """Given: 청산 신호 파라미터
        When: Signal 생성
        Then: 올바른 속성 설정"""
        signal = Signal(
            action=SignalAction.CLOSE,
            price=Money.krw(52000000)
        )

        assert signal.action == SignalAction.CLOSE

    def test_signal_with_timestamp(self):
        """Given: 캔들 시간 지정
        When: Signal 생성
        Then: 지정된 시간 사용"""
        candle_time = datetime(2026, 1, 3, 10, 0, 0)
        signal = Signal(
            action=SignalAction.BUY,
            price=Money.krw(50000000),
            timestamp=candle_time
        )

        assert signal.timestamp == candle_time

    def test_signal_default_timestamp_is_none(self):
        """Given: timestamp 미지정
        When: Signal 생성
        Then: timestamp는 None (datetime.now() 사용 안 함)"""
        signal = Signal(
            action=SignalAction.BUY,
            price=Money.krw(50000000)
        )

        # 중요: datetime.now() 사용하지 않음 - 백테스트 시간축 왜곡 방지
        assert signal.timestamp is None

    def test_signal_risk_reward_ratio(self):
        """Given: 스탑로스와 익절가 설정된 신호
        When: 손익비 계산
        Then: 올바른 손익비 반환"""
        signal = Signal(
            action=SignalAction.BUY,
            price=Money.krw(50000000),
            stop_loss=Money.krw(49000000),  # 100만원 손실
            take_profit=Money.krw(52000000)  # 200만원 이익
        )

        assert signal.risk_reward_ratio == Decimal("2.0")

    def test_signal_risk_reward_ratio_without_levels(self):
        """Given: 스탑로스/익절가 없는 신호
        When: 손익비 계산
        Then: None 반환"""
        signal = Signal(
            action=SignalAction.BUY,
            price=Money.krw(50000000)
        )

        assert signal.risk_reward_ratio is None

    def test_signal_risk_percentage(self):
        """Given: 스탑로스 설정된 신호
        When: 리스크 비율 계산
        Then: 올바른 퍼센티지 반환"""
        signal = Signal(
            action=SignalAction.BUY,
            price=Money.krw(50000000),
            stop_loss=Money.krw(49000000)  # 2% 손실
        )

        assert signal.risk_percentage == Percentage.from_points(Decimal("2.0"))

    def test_signal_from_legacy_dict(self):
        """Given: 레거시 형식의 딕셔너리
        When: from_legacy 팩토리 메서드 호출
        Then: Signal 객체 생성"""
        legacy_data = {
            "action": "buy",
            "price": 50000000,
            "stop_loss": 49000000,
            "take_profit": 52000000,
            "reason": {"strategy": "breakout"}
        }

        signal = Signal.from_legacy(legacy_data)

        assert signal.action == SignalAction.BUY
        assert signal.price == Money.krw(50000000)

    def test_signal_to_legacy_dict(self):
        """Given: Signal 객체
        When: to_legacy 메서드 호출
        Then: 레거시 호환 딕셔너리 반환"""
        signal = Signal(
            action=SignalAction.BUY,
            price=Money.krw(50000000),
            stop_loss=Money.krw(49000000)
        )

        legacy = signal.to_legacy()

        assert legacy["action"] == "buy"
        assert legacy["price"] == 50000000
        assert legacy["stop_loss"] == 49000000


class TestSignalAction:
    """SignalAction Enum 테스트"""

    def test_signal_action_values(self):
        """SignalAction enum 값 확인"""
        assert SignalAction.BUY.value == "buy"
        assert SignalAction.SELL.value == "sell"
        assert SignalAction.CLOSE.value == "close"
        assert SignalAction.HOLD.value == "hold"

    def test_signal_action_from_string(self):
        """문자열에서 SignalAction 변환"""
        assert SignalAction("buy") == SignalAction.BUY
        assert SignalAction("sell") == SignalAction.SELL
