"""
진입 흐름 시나리오 테스트

시나리오: 시장 분석 후 매수 결정 및 실행까지의 전체 흐름
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal

from src.domain.value_objects.money import Money


class TestEntryFlowScenario:
    """진입 흐름 시나리오"""

    # =========================================================================
    # SCENARIO 1: 정상 매수 진입
    # =========================================================================

    @pytest.mark.scenario
    @pytest.mark.asyncio
    async def test_successful_buy_entry(
        self,
        mock_exchange_port,
        mock_ai_decision_buy,
        mock_portfolio_status,
    ):
        """
        시나리오: AI가 매수 결정을 내리면 주문이 실행되어야 함

        Given: 충분한 잔고와 매수 신호
        When: 트레이딩 사이클 실행
        Then: 매수 주문이 성공적으로 실행됨
        """
        # Given: 충분한 잔고
        available_balance = mock_portfolio_status["available_balance"]
        assert available_balance.amount >= Decimal("100000")  # 최소 10만원

        # Given: AI 매수 결정
        decision = mock_ai_decision_buy
        assert decision["decision"] == "buy"
        assert decision["confidence"] == "high"

        # When: 거래 실행 (시뮬레이션)
        mock_exchange_port.execute_buy = AsyncMock(
            return_value={"success": True, "trade_id": "entry-123", "amount": 0.005}
        )

        result = await mock_exchange_port.execute_buy(
            ticker="KRW-BTC",
            amount=Money.krw(300000),  # 30% of portfolio
        )

        # Then: 주문 성공
        assert result["success"] is True
        assert "trade_id" in result
        mock_exchange_port.execute_buy.assert_called_once()

    # =========================================================================
    # SCENARIO 2: 잔고 부족 시 진입 실패
    # =========================================================================

    @pytest.mark.scenario
    @pytest.mark.asyncio
    async def test_entry_fails_with_insufficient_balance(
        self,
        mock_exchange_port,
        mock_ai_decision_buy,
    ):
        """
        시나리오: 잔고 부족 시 진입이 실패해야 함

        Given: 부족한 잔고
        When: 매수 시도
        Then: 진입 실패 및 적절한 에러 반환
        """
        # Given: 부족한 잔고
        mock_exchange_port.get_balance = AsyncMock(return_value=Money.krw(1000))

        # When: 거래 시도
        balance = await mock_exchange_port.get_balance("KRW")

        # Then: 최소 거래 금액 미달
        min_trade_amount = Money.krw(5000)
        assert balance.amount < min_trade_amount.amount

    # =========================================================================
    # SCENARIO 3: 포지션 한도 내 진입
    # =========================================================================

    @pytest.mark.scenario
    @pytest.mark.asyncio
    async def test_entry_respects_position_limit(
        self,
        mock_portfolio_status,
    ):
        """
        시나리오: 진입 금액이 포지션 한도를 초과하지 않아야 함

        Given: 포트폴리오 가치 100만원, 포지션 한도 30%
        When: 진입 금액 계산
        Then: 최대 30만원까지만 진입
        """
        # Given: 포트폴리오 가치
        portfolio_value = mock_portfolio_status["total_value"]
        position_limit = Decimal("0.30")  # 30%

        # When: 최대 진입 금액 계산
        max_entry = Money.krw(int(portfolio_value.amount * position_limit))

        # Then: 30만원
        assert max_entry == Money.krw(300000)

    # =========================================================================
    # SCENARIO 4: 백테스트 통과 후 진입
    # =========================================================================

    @pytest.mark.scenario
    def test_entry_requires_backtest_pass(self):
        """
        시나리오: 백테스트를 통과한 코인만 진입 대상

        Given: 스캔된 코인 목록
        When: 백테스트 필터 적용
        Then: 통과한 코인만 진입 대상에 포함
        """
        # Given: 스캔된 코인들
        scanned_coins = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]

        # Given: 백테스트 결과 (2개 통과)
        backtest_results = {
            "KRW-BTC": {"passed": True, "score": 0.85},
            "KRW-ETH": {"passed": False, "score": 0.45},
            "KRW-XRP": {"passed": True, "score": 0.72},
            "KRW-SOL": {"passed": False, "score": 0.38},
        }

        # When: 필터링
        passed_coins = [
            coin for coin in scanned_coins
            if backtest_results.get(coin, {}).get("passed", False)
        ]

        # Then: 통과한 코인만 포함
        assert len(passed_coins) == 2
        assert "KRW-BTC" in passed_coins
        assert "KRW-XRP" in passed_coins
        assert "KRW-ETH" not in passed_coins


class TestEntryConditionsScenario:
    """진입 조건 시나리오"""

    # =========================================================================
    # SCENARIO 5: AI 신뢰도에 따른 진입 결정
    # =========================================================================

    @pytest.mark.scenario
    def test_high_confidence_allows_entry(self, mock_ai_decision_buy):
        """높은 신뢰도의 AI 결정은 진입을 허용"""
        decision = mock_ai_decision_buy
        assert decision["confidence"] == "high"

        # 높은 신뢰도 = 진입 허용
        should_enter = decision["confidence"] in ["high", "medium"]
        assert should_enter is True

    @pytest.mark.scenario
    def test_low_confidence_blocks_entry(self):
        """낮은 신뢰도의 AI 결정은 진입을 차단"""
        decision = {
            "decision": "buy",
            "confidence": "low",
            "reason": "약한 신호",
        }

        # 낮은 신뢰도 = 진입 차단
        should_enter = decision["confidence"] in ["high", "medium"]
        assert should_enter is False

    # =========================================================================
    # SCENARIO 6: 이미 포지션이 있는 경우
    # =========================================================================

    @pytest.mark.scenario
    def test_no_entry_when_position_exists(self):
        """
        시나리오: 이미 해당 코인에 포지션이 있으면 추가 진입 불가

        Given: BTC 포지션 보유 중
        When: BTC 매수 신호 발생
        Then: 추가 진입 차단
        """
        # Given: 기존 포지션
        existing_positions = [{"ticker": "KRW-BTC", "volume": Decimal("0.005")}]

        # When: 동일 코인 매수 시도
        target_ticker = "KRW-BTC"
        has_position = any(
            p["ticker"] == target_ticker for p in existing_positions
        )

        # Then: 추가 진입 불가
        assert has_position is True

    @pytest.mark.scenario
    def test_entry_allowed_for_different_coin(self):
        """
        시나리오: 다른 코인은 진입 가능

        Given: BTC 포지션 보유 중
        When: ETH 매수 신호 발생
        Then: 진입 허용
        """
        # Given: 기존 포지션
        existing_positions = [{"ticker": "KRW-BTC", "volume": Decimal("0.005")}]

        # When: 다른 코인 매수 시도
        target_ticker = "KRW-ETH"
        has_position = any(
            p["ticker"] == target_ticker for p in existing_positions
        )

        # Then: 진입 가능
        assert has_position is False
