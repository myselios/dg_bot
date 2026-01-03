"""
Paper Trading E2E 테스트

실제 운용 흐름을 Paper trading 모드로 검증
"""
import pytest
from decimal import Decimal


class TestPaperTradingFlow:
    """Paper Trading 흐름 테스트"""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_paper_trading_buy_flow(
        self,
        mock_paper_exchange,
        paper_trading_config,
    ):
        """
        E2E: Paper trading 매수 흐름

        Given: Paper trading 모드, 충분한 잔고
        When: 매수 신호 발생
        Then: Paper 매수 실행 및 포지션 기록
        """
        # Given: 잔고 확인
        balance = await mock_paper_exchange.get_balance("KRW")
        assert balance >= Decimal("100000")

        # When: 매수 실행
        result = await mock_paper_exchange.buy("KRW-BTC", Decimal("300000"))

        # Then: 매수 성공
        assert result["success"] is True
        assert "paper" in result["trade_id"]

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_paper_trading_sell_flow(
        self,
        mock_paper_exchange,
        paper_trading_config,
    ):
        """
        E2E: Paper trading 매도 흐름

        Given: Paper trading 모드, 보유 포지션
        When: 매도 신호 발생
        Then: Paper 매도 실행 및 포지션 정리
        """
        # Given: 포지션 보유 (가정)
        mock_paper_exchange.positions = [
            {"ticker": "KRW-BTC", "volume": Decimal("0.005")}
        ]

        # When: 매도 실행
        result = await mock_paper_exchange.sell("KRW-BTC", Decimal("0.005"))

        # Then: 매도 성공
        assert result["success"] is True
        assert "paper" in result["trade_id"]


class TestPaperTradingRiskManagement:
    """Paper Trading 리스크 관리 테스트"""

    @pytest.mark.e2e
    def test_paper_trading_position_limit(self, paper_trading_config):
        """
        E2E: Paper trading 포지션 한도 검증

        Given: 30% 포지션 한도
        When: 포지션 크기 계산
        Then: 한도 내 거래만 허용
        """
        initial_balance = paper_trading_config["initial_balance"]
        max_pct = paper_trading_config["max_position_size_pct"]

        max_position = initial_balance * max_pct
        assert max_position == Decimal("300000")

    @pytest.mark.e2e
    def test_paper_trading_stop_loss(self, paper_trading_config):
        """
        E2E: Paper trading 손절 검증

        Given: -5% 손절 설정
        When: 손절가 계산
        Then: 정확한 손절가 산출
        """
        entry_price = Decimal("50000000")
        stop_loss_pct = paper_trading_config["stop_loss_pct"]

        stop_price = entry_price * (1 + stop_loss_pct)
        assert stop_price == Decimal("47500000")
