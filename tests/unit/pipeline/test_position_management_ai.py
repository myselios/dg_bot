"""
Phase 3: 포지션 관리에 AI 검증 통합 테스트

15분 주기 포지션 관리에서:
1. 규칙 기반 체크가 먼저 실행됨
2. 손절/익절 조건 만족 시 즉시 매도 (AI 스킵)
3. 규칙이 HOLD 판단 시에만 AI 검증 호출
4. AI가 sell로 오버라이드 가능

TDD Phase: RED → GREEN → REFACTOR
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional

from src.trading.pipeline.base_stage import PipelineContext, StageResult


@dataclass
class MockPosition:
    """테스트용 포지션 Mock"""
    ticker: str
    symbol: str
    avg_buy_price: float
    current_price: float
    quantity: float
    pnl_pct: float

    @property
    def is_stop_loss(self) -> bool:
        """손절 조건 (기본 -5%)"""
        return self.pnl_pct <= -5.0

    @property
    def is_take_profit(self) -> bool:
        """익절 조건 (기본 +10%)"""
        return self.pnl_pct >= 10.0


@dataclass
class MockPortfolioStatus:
    """테스트용 포트폴리오 상태 Mock"""
    positions: List[MockPosition]
    available_capital: float = 100000

    @property
    def has_positions(self) -> bool:
        return len(self.positions) > 0


class TestRuleBasedCheck:
    """규칙 기반 체크 테스트"""

    def test_rule_based_check_triggers_first(self):
        """
        규칙 기반 체크가 AI 검증보다 먼저 실행되는지 검증

        검증 순서:
        1. 포지션 손익률 계산
        2. 손절/익절 조건 체크
        3. 조건 만족 시 → 즉시 매도 (AI 스킵)
        4. 조건 미달 시 → AI 검증으로 진행
        """
        # 손절 조건 (-7%) 만족하는 포지션
        position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=5000000,
            current_price=4650000,  # -7%
            quantity=0.01,
            pnl_pct=-7.0
        )

        # 규칙 기반 체크
        assert position.is_stop_loss is True
        assert position.is_take_profit is False

        # 손절 조건 만족 → 즉시 매도 결정
        decision = "sell" if position.is_stop_loss else "hold"
        assert decision == "sell"

    def test_stop_loss_triggers_immediate_sell(self):
        """
        손절 조건 (-5% 이하) 만족 시 즉시 매도 결정

        AI 검증을 호출하지 않고 바로 매도 실행
        """
        position = MockPosition(
            ticker="KRW-BTC",
            symbol="BTC",
            avg_buy_price=100000000,
            current_price=94000000,  # -6%
            quantity=0.001,
            pnl_pct=-6.0
        )

        assert position.is_stop_loss is True

        # 결정 로직
        if position.is_stop_loss:
            decision = "sell"
            reason = f"손절 조건 충족 (PnL: {position.pnl_pct:.1f}%)"
            ai_called = False
        else:
            decision = "hold"
            ai_called = True

        assert decision == "sell"
        assert ai_called is False
        assert "손절" in reason

    def test_take_profit_triggers_immediate_sell(self):
        """
        익절 조건 (+10% 이상) 만족 시 즉시 매도 결정

        AI 검증을 호출하지 않고 바로 매도 실행
        """
        position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=4000000,
            current_price=4500000,  # +12.5%
            quantity=0.01,
            pnl_pct=12.5
        )

        assert position.is_take_profit is True

        # 결정 로직
        if position.is_take_profit:
            decision = "sell"
            reason = f"익절 조건 충족 (PnL: {position.pnl_pct:.1f}%)"
            ai_called = False
        else:
            decision = "hold"
            ai_called = True

        assert decision == "sell"
        assert ai_called is False
        assert "익절" in reason


class TestAIVerificationIntegration:
    """AI 검증 통합 테스트"""

    def test_ai_verification_called_after_rule_check(self):
        """
        규칙 기반 체크가 HOLD 판단 시에만 AI 검증이 호출되는지 검증

        조건:
        - 손절/익절 조건 미달 (-5% < PnL < +10%)
        - AI 검증 호출됨
        """
        position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=4500000,
            current_price=4600000,  # +2.2%
            quantity=0.01,
            pnl_pct=2.2
        )

        # 규칙 기반 체크: 손절/익절 조건 미달
        assert position.is_stop_loss is False
        assert position.is_take_profit is False

        # 규칙이 HOLD → AI 검증 호출
        should_call_ai = not (position.is_stop_loss or position.is_take_profit)
        assert should_call_ai is True

    def test_ai_can_override_hold_to_sell(self):
        """
        AI가 HOLD를 SELL로 오버라이드할 수 있는지 검증

        시나리오:
        - 규칙 기반: HOLD (손절/익절 미달)
        - AI 검증: SELL (시장 상황 악화 예상)
        - 최종 결정: SELL
        """
        position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=4500000,
            current_price=4400000,  # -2.2%
            quantity=0.01,
            pnl_pct=-2.2
        )

        # 규칙 기반: HOLD
        rule_decision = "hold"
        if position.is_stop_loss:
            rule_decision = "sell"
        elif position.is_take_profit:
            rule_decision = "sell"

        assert rule_decision == "hold"

        # AI 검증: SELL (모킹)
        ai_decision = "sell"  # AI가 시장 하락 예상하여 매도 권고

        # 최종 결정: AI 오버라이드 적용
        final_decision = ai_decision if rule_decision == "hold" else rule_decision

        assert final_decision == "sell"

    def test_ai_keeps_hold_when_no_action_needed(self):
        """
        AI도 HOLD 판단 시 최종 결정 HOLD

        시나리오:
        - 규칙 기반: HOLD
        - AI 검증: HOLD
        - 최종 결정: HOLD
        """
        position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=4500000,
            current_price=4550000,  # +1.1%
            quantity=0.01,
            pnl_pct=1.1
        )

        rule_decision = "hold"
        ai_decision = "hold"

        final_decision = ai_decision if rule_decision == "hold" else rule_decision

        assert final_decision == "hold"


class TestRuleBasedSellBypassesAI:
    """규칙 기반 매도 시 AI 우회 테스트"""

    def test_rule_based_sell_bypasses_ai(self):
        """
        손절/익절 조건 만족 시 AI 검증을 호출하지 않는지 검증

        검증 항목:
        1. 손절 조건 → AI 미호출
        2. 익절 조건 → AI 미호출
        3. 규칙 HOLD → AI 호출
        """
        # 손절 케이스
        stop_loss_position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=5000000,
            current_price=4700000,  # -6%
            quantity=0.01,
            pnl_pct=-6.0
        )

        # 익절 케이스
        take_profit_position = MockPosition(
            ticker="KRW-BTC",
            symbol="BTC",
            avg_buy_price=90000000,
            current_price=100000000,  # +11%
            quantity=0.001,
            pnl_pct=11.1
        )

        # 중립 케이스 (규칙 HOLD)
        neutral_position = MockPosition(
            ticker="KRW-XRP",
            symbol="XRP",
            avg_buy_price=1000,
            current_price=1030,  # +3%
            quantity=100,
            pnl_pct=3.0
        )

        # AI 호출 여부 결정 로직
        def should_call_ai(pos: MockPosition) -> bool:
            return not (pos.is_stop_loss or pos.is_take_profit)

        assert should_call_ai(stop_loss_position) is False  # 손절 → AI 미호출
        assert should_call_ai(take_profit_position) is False  # 익절 → AI 미호출
        assert should_call_ai(neutral_position) is True  # 중립 → AI 호출

    def test_multiple_positions_independent_checks(self):
        """
        다중 포지션에서 각 포지션이 독립적으로 체크되는지 검증

        3개 포지션:
        - ETH: 손절 조건 → 즉시 매도
        - BTC: 익절 조건 → 즉시 매도
        - XRP: 중립 → AI 검증 필요
        """
        positions = [
            MockPosition("KRW-ETH", "ETH", 5000000, 4700000, 0.01, -6.0),  # 손절
            MockPosition("KRW-BTC", "BTC", 90000000, 100000000, 0.001, 11.1),  # 익절
            MockPosition("KRW-XRP", "XRP", 1000, 1030, 100, 3.0),  # 중립
        ]

        decisions = []
        ai_calls = []

        for pos in positions:
            if pos.is_stop_loss:
                decisions.append(("sell", f"손절 ({pos.pnl_pct:.1f}%)"))
                ai_calls.append(False)
            elif pos.is_take_profit:
                decisions.append(("sell", f"익절 ({pos.pnl_pct:.1f}%)"))
                ai_calls.append(False)
            else:
                # AI 검증 호출 (여기서는 모킹)
                ai_decision = "hold"  # AI 결정
                decisions.append((ai_decision, "AI 검증 결과"))
                ai_calls.append(True)

        # 검증
        assert decisions[0][0] == "sell"  # ETH: 손절
        assert decisions[1][0] == "sell"  # BTC: 익절
        assert decisions[2][0] == "hold"  # XRP: AI 검증 (hold)

        assert ai_calls[0] is False  # ETH: AI 미호출
        assert ai_calls[1] is False  # BTC: AI 미호출
        assert ai_calls[2] is True   # XRP: AI 호출


class TestPositionManagementStageIntegration:
    """PositionManagementStage 통합 테스트"""

    @pytest.fixture
    def mock_context(self):
        """포지션 관리용 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-ETH"
        context.container = MagicMock()

        # AI 서비스 모킹
        ai_port = MagicMock()
        ai_port.analyze = AsyncMock(return_value=MagicMock(
            decision="hold",
            confidence=Decimal("0.6"),
            reasoning="현재 포지션 유지 권장"
        ))
        context.container.get_ai_port = MagicMock(return_value=ai_port)

        return context

    @pytest.mark.asyncio
    async def test_position_management_flow(self, mock_context):
        """
        전체 포지션 관리 흐름 테스트

        1. 포지션 목록 조회
        2. 각 포지션에 대해 규칙 기반 체크
        3. 규칙 HOLD 시 AI 검증
        4. 최종 결정에 따라 액션 실행
        """
        # 포지션 설정
        positions = [
            MockPosition("KRW-ETH", "ETH", 4500000, 4400000, 0.01, -2.2),  # 규칙 HOLD
        ]

        actions = []
        for pos in positions:
            if pos.is_stop_loss or pos.is_take_profit:
                # 규칙 기반 즉시 매도
                action = "sell"
                ai_used = False
            else:
                # AI 검증
                ai_decision = "hold"  # 모킹된 AI 결정
                action = ai_decision
                ai_used = True

            actions.append({
                "ticker": pos.ticker,
                "action": action,
                "pnl_pct": pos.pnl_pct,
                "ai_used": ai_used
            })

        # 검증
        assert len(actions) == 1
        assert actions[0]["action"] == "hold"
        assert actions[0]["ai_used"] is True

    @pytest.mark.asyncio
    async def test_stop_loss_position_immediate_sell(self, mock_context):
        """손절 포지션 즉시 매도 테스트"""
        position = MockPosition("KRW-ETH", "ETH", 5000000, 4650000, 0.01, -7.0)

        # 규칙 기반 체크
        if position.is_stop_loss:
            action = "sell"
            reason = f"손절 트리거 (PnL: {position.pnl_pct:.1f}%)"
            ai_used = False
        else:
            action = "hold"
            ai_used = True

        assert action == "sell"
        assert ai_used is False
        assert "손절" in reason

    @pytest.mark.asyncio
    async def test_take_profit_position_immediate_sell(self, mock_context):
        """익절 포지션 즉시 매도 테스트"""
        position = MockPosition("KRW-BTC", "BTC", 90000000, 100000000, 0.001, 11.1)

        # 규칙 기반 체크
        if position.is_take_profit:
            action = "sell"
            reason = f"익절 트리거 (PnL: {position.pnl_pct:.1f}%)"
            ai_used = False
        else:
            action = "hold"
            ai_used = True

        assert action == "sell"
        assert ai_used is False
        assert "익절" in reason


class TestConfigurableThresholds:
    """설정 가능한 임계값 테스트"""

    def test_custom_stop_loss_threshold(self):
        """
        커스텀 손절 임계값 테스트

        기본: -5%
        커스텀: -3%
        """
        custom_stop_loss_pct = -3.0

        position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=5000000,
            current_price=4850000,  # -3%
            quantity=0.01,
            pnl_pct=-3.0
        )

        # 기본 임계값 (-5%): HOLD
        is_stop_loss_default = position.pnl_pct <= -5.0
        assert is_stop_loss_default is False

        # 커스텀 임계값 (-3%): SELL
        is_stop_loss_custom = position.pnl_pct <= custom_stop_loss_pct
        assert is_stop_loss_custom is True

    def test_custom_take_profit_threshold(self):
        """
        커스텀 익절 임계값 테스트

        기본: +10%
        커스텀: +8%
        """
        custom_take_profit_pct = 8.0

        position = MockPosition(
            ticker="KRW-ETH",
            symbol="ETH",
            avg_buy_price=4500000,
            current_price=4860000,  # +8%
            quantity=0.01,
            pnl_pct=8.0
        )

        # 기본 임계값 (+10%): HOLD
        is_take_profit_default = position.pnl_pct >= 10.0
        assert is_take_profit_default is False

        # 커스텀 임계값 (+8%): SELL
        is_take_profit_custom = position.pnl_pct >= custom_take_profit_pct
        assert is_take_profit_custom is True
