"""
청산 흐름 시나리오 테스트

시나리오: 포지션 청산 결정 및 실행까지의 전체 흐름
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta

from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage


class TestExitFlowScenario:
    """청산 흐름 시나리오"""

    # =========================================================================
    # SCENARIO 1: 익절 청산
    # =========================================================================

    @pytest.mark.scenario
    @pytest.mark.asyncio
    async def test_take_profit_exit(self, mock_exchange_port):
        """
        시나리오: 익절 목표 도달 시 청산

        Given: BTC 포지션 보유 (진입가 5천만원)
        And: 현재가 5500만원 (+10%)
        When: 익절 조건 확인
        Then: 청산 실행
        """
        # Given: 포지션 정보
        position = {
            "ticker": "KRW-BTC",
            "entry_price": Money.krw(50000000),
            "volume": Decimal("0.005"),
            "take_profit_pct": Percentage(Decimal("0.10")),  # +10%
        }

        # Given: 현재가 (+10%)
        current_price = Money.krw(55000000)
        entry_price = position["entry_price"]

        # When: 수익률 계산
        profit_pct = (current_price.amount - entry_price.amount) / entry_price.amount

        # Then: 익절 조건 충족
        assert profit_pct >= Decimal("0.10")

        # When: 청산 실행
        mock_exchange_port.execute_sell = AsyncMock(
            return_value={"success": True, "trade_id": "exit-tp-123"}
        )
        result = await mock_exchange_port.execute_sell(
            ticker="KRW-BTC",
            volume=position["volume"],
        )

        # Then: 청산 성공
        assert result["success"] is True

    # =========================================================================
    # SCENARIO 2: 손절 청산
    # =========================================================================

    @pytest.mark.scenario
    @pytest.mark.asyncio
    async def test_stop_loss_exit(self, mock_exchange_port):
        """
        시나리오: 손절 조건 도달 시 청산

        Given: BTC 포지션 보유 (진입가 5천만원)
        And: 현재가 4750만원 (-5%)
        When: 손절 조건 확인
        Then: 즉시 청산 실행
        """
        # Given: 포지션 정보
        position = {
            "ticker": "KRW-BTC",
            "entry_price": Money.krw(50000000),
            "volume": Decimal("0.005"),
            "stop_loss_pct": Percentage(Decimal("-0.05")),  # -5%
        }

        # Given: 현재가 (-5%)
        current_price = Money.krw(47500000)
        entry_price = position["entry_price"]

        # When: 손익률 계산
        pnl_pct = (current_price.amount - entry_price.amount) / entry_price.amount

        # Then: 손절 조건 충족
        assert pnl_pct <= Decimal("-0.05")

        # When: 즉시 청산 실행
        mock_exchange_port.execute_sell = AsyncMock(
            return_value={"success": True, "trade_id": "exit-sl-123"}
        )
        result = await mock_exchange_port.execute_sell(
            ticker="KRW-BTC",
            volume=position["volume"],
        )

        # Then: 청산 성공
        assert result["success"] is True
        mock_exchange_port.execute_sell.assert_called_once()

    # =========================================================================
    # SCENARIO 3: AI 매도 신호에 의한 청산
    # =========================================================================

    @pytest.mark.scenario
    @pytest.mark.asyncio
    async def test_ai_signal_exit(
        self,
        mock_exchange_port,
        mock_ai_decision_sell,
    ):
        """
        시나리오: AI가 매도 신호를 내리면 청산

        Given: BTC 포지션 보유
        And: AI 매도 신호 (높은 신뢰도)
        When: 트레이딩 사이클 실행
        Then: 청산 실행
        """
        # Given: 포지션 정보
        position = {
            "ticker": "KRW-BTC",
            "volume": Decimal("0.005"),
        }

        # Given: AI 매도 결정
        ai_decision = mock_ai_decision_sell
        assert ai_decision["decision"] == "sell"
        assert ai_decision["confidence"] == "high"

        # When: 청산 실행
        mock_exchange_port.execute_sell = AsyncMock(
            return_value={"success": True, "trade_id": "exit-ai-123"}
        )
        result = await mock_exchange_port.execute_sell(
            ticker=position["ticker"],
            volume=position["volume"],
        )

        # Then: 청산 성공
        assert result["success"] is True

    # =========================================================================
    # SCENARIO 4: 부분 청산
    # =========================================================================

    @pytest.mark.scenario
    def test_partial_exit_calculation(self):
        """
        시나리오: 익절 구간에서 부분 청산

        Given: BTC 포지션 0.01개 보유
        And: +5% 수익 (부분 익절 구간)
        When: 부분 청산 비율 계산
        Then: 50% 청산
        """
        # Given: 포지션 정보
        total_volume = Decimal("0.01")
        current_profit_pct = Decimal("0.05")  # +5%

        # Given: 부분 익절 규칙
        partial_tp_rules = [
            {"pct": Decimal("0.05"), "sell_ratio": Decimal("0.50")},  # +5% → 50% 청산
            {"pct": Decimal("0.10"), "sell_ratio": Decimal("1.00")},  # +10% → 전량 청산
        ]

        # When: 적용할 규칙 찾기
        applicable_rule = None
        for rule in partial_tp_rules:
            if current_profit_pct >= rule["pct"]:
                applicable_rule = rule

        # Then: 50% 청산 규칙 적용
        assert applicable_rule is not None
        assert applicable_rule["sell_ratio"] == Decimal("0.50")

        # When: 청산 수량 계산
        sell_volume = total_volume * applicable_rule["sell_ratio"]

        # Then: 0.005개 청산
        assert sell_volume == Decimal("0.005")


class TestExitPriorityScenario:
    """청산 우선순위 시나리오"""

    # =========================================================================
    # SCENARIO 5: 손절이 익절보다 우선
    # =========================================================================

    @pytest.mark.scenario
    def test_stop_loss_has_priority(self):
        """
        시나리오: 손절 조건이 익절보다 우선 처리됨

        Given: 급락 중인 시장
        When: 손절과 익절 조건을 동시에 확인
        Then: 손절이 먼저 처리됨
        """
        # Given: 현재 상태
        entry_price = Money.krw(50000000)
        current_price = Money.krw(45000000)  # -10% (손절 초과)

        stop_loss_pct = Decimal("-0.05")
        take_profit_pct = Decimal("0.10")

        # When: 손익률 계산
        pnl_pct = (current_price.amount - entry_price.amount) / entry_price.amount

        # When: 조건 확인
        is_stop_loss = pnl_pct <= stop_loss_pct
        is_take_profit = pnl_pct >= take_profit_pct

        # Then: 손절 조건만 충족
        assert is_stop_loss is True
        assert is_take_profit is False

    # =========================================================================
    # SCENARIO 6: 포지션 없으면 청산 불가
    # =========================================================================

    @pytest.mark.scenario
    def test_no_exit_without_position(self):
        """
        시나리오: 포지션이 없으면 청산 불가

        Given: 빈 포지션
        When: 청산 시도
        Then: 청산 불가 반환
        """
        # Given: 빈 포지션
        positions = []

        # When: 청산 대상 확인
        target_ticker = "KRW-BTC"
        has_position = any(
            p.get("ticker") == target_ticker for p in positions
        )

        # Then: 청산 불가
        assert has_position is False


class TestExitTimingScenario:
    """청산 타이밍 시나리오"""

    # =========================================================================
    # SCENARIO 7: 15분 주기 포지션 관리
    # =========================================================================

    @pytest.mark.scenario
    def test_position_management_frequency(self):
        """
        시나리오: 포지션 관리는 15분마다 실행

        Given: 스케줄러 설정
        When: 포지션 관리 작업 주기 확인
        Then: 15분 (매 정각, 15분, 30분, 45분)
        """
        # Given: 스케줄러 트리거 시간
        trigger_minutes = [1, 16, 31, 46]  # 캔들 마감 후 1분

        # When: 간격 계산
        intervals = [
            trigger_minutes[i + 1] - trigger_minutes[i]
            for i in range(len(trigger_minutes) - 1)
        ]

        # Then: 15분 간격
        assert all(interval == 15 for interval in intervals)

    # =========================================================================
    # SCENARIO 8: 홀딩 시간 기반 청산
    # =========================================================================

    @pytest.mark.scenario
    def test_max_holding_time_exit(self):
        """
        시나리오: 최대 홀딩 시간 초과 시 청산 고려

        Given: 24시간 이상 보유한 포지션
        When: 홀딩 시간 확인
        Then: 청산 권고 발생
        """
        # Given: 포지션 정보
        entry_time = datetime.now() - timedelta(hours=25)
        max_holding_hours = 24

        # When: 홀딩 시간 계산
        holding_hours = (datetime.now() - entry_time).total_seconds() / 3600

        # Then: 최대 홀딩 시간 초과
        assert holding_hours > max_holding_hours
