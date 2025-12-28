"""
통합 테스트
TDD 원칙: 전체 시스템의 통합 동작을 검증합니다.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from backend.app.models.trade import Trade
from backend.app.models.ai_decision import AIDecision


@pytest.mark.asyncio
class TestFullTradingFlow:
    """전체 트레이딩 플로우 통합 테스트"""
    
    async def test_complete_trading_cycle(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 빈 데이터베이스
        When: 거래 생성 → AI 판단 저장 → 거래 조회
        Then: 전체 플로우가 정상 동작
        """
        # 1. AI 판단 저장
        ai_decision = AIDecision(
            symbol="KRW-BTC",
            decision="buy",
            confidence=Decimal("85.0"),
            reason="RSI 과매도 구간 진입",
            market_data={"price": 95000000, "rsi": 28.5},
        )
        async_session.add(ai_decision)
        await async_session.commit()
        
        # 2. 거래 생성 (API)
        trade_data = {
            "trade_id": "integration_test_001",
            "symbol": "KRW-BTC",
            "side": "buy",
            "price": "95000000.0",
            "amount": "0.001",
            "total": "95000.0",
            "fee": "47.5",
            "status": "completed",
        }
        
        create_response = await client.post(
            "/api/v1/trades/",
            json=trade_data,
        )
        assert create_response.status_code == 201
        
        # 3. 거래 조회 (API)
        get_response = await client.get("/api/v1/trades/")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["total"] == 1
        assert data["trades"][0]["trade_id"] == "integration_test_001"
        
        # 4. 데이터베이스 직접 확인
        query = select(Trade).where(
            Trade.trade_id == "integration_test_001"
        )
        result = await async_session.execute(query)
        trade = result.scalar_one()
        
        assert trade.symbol == "KRW-BTC"
        assert trade.side == "buy"
        assert trade.price == Decimal("95000000")
    
    async def test_bot_control_and_status_check(
        self,
        client: AsyncClient,
    ):
        """
        Given: 초기 봇 상태
        When: 봇 시작 → 상태 확인 → 봇 중지
        Then: 상태가 정상적으로 변경됨
        """
        # 1. 초기 상태 확인
        status_response = await client.get("/api/v1/bot/status")
        assert status_response.status_code == 200
        initial_status = status_response.json()
        assert initial_status["is_running"] == False
        
        # 2. 봇 시작
        start_response = await client.post(
            "/api/v1/bot/control",
            json={"action": "start", "reason": "통합 테스트"},
        )
        assert start_response.status_code == 200
        
        # 3. 시작 후 상태 확인
        status_response = await client.get("/api/v1/bot/status")
        running_status = status_response.json()
        assert running_status["is_running"] == True
        
        # 4. 봇 중지
        stop_response = await client.post(
            "/api/v1/bot/control",
            json={"action": "stop", "reason": "테스트 종료"},
        )
        assert stop_response.status_code == 200
        
        # 5. 중지 후 상태 확인
        status_response = await client.get("/api/v1/bot/status")
        stopped_status = status_response.json()
        assert stopped_status["is_running"] == False
    
    async def test_trade_statistics_aggregation(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 여러 거래 내역
        When: 통계 조회
        Then: 정확한 집계 결과 반환
        """
        # 1. 여러 거래 생성
        trades = [
            {
                "trade_id": f"stats_test_{i}",
                "symbol": "KRW-BTC",
                "side": "buy" if i < 3 else "sell",
                "price": "95000000.0" if i < 3 else "100000000.0",
                "amount": "0.001",
                "total": "95000.0" if i < 3 else "100000.0",
                "fee": "47.5" if i < 3 else "50.0",
                "status": "completed",
            }
            for i in range(5)
        ]
        
        for trade_data in trades:
            await client.post("/api/v1/trades/", json=trade_data)
        
        # 2. 통계 조회
        stats_response = await client.get(
            "/api/v1/trades/statistics/summary"
        )
        assert stats_response.status_code == 200
        
        stats = stats_response.json()
        assert stats["total_trades"] == 5
        assert stats["total_buy"] == 3
        assert stats["total_sell"] == 2
        
        # 총 거래량: (95k * 3) + (100k * 2) = 485k
        assert float(stats["total_volume_krw"]) == 485000.0
        
        # 평균 매수가: 95M
        assert float(stats["avg_buy_price"]) == 95000000.0
        
        # 평균 매도가: 100M
        assert float(stats["avg_sell_price"]) == 100000000.0


@pytest.mark.asyncio
class TestErrorHandling:
    """에러 핸들링 통합 테스트"""
    
    async def test_duplicate_trade_rejection(
        self,
        client: AsyncClient,
    ):
        """
        Given: 이미 존재하는 거래
        When: 동일한 trade_id로 생성 시도
        Then: 409 Conflict 반환 및 데이터 무결성 유지
        """
        trade_data = {
            "trade_id": "duplicate_test",
            "symbol": "KRW-BTC",
            "side": "buy",
            "price": "95000000.0",
            "amount": "0.001",
            "total": "95000.0",
            "fee": "47.5",
            "status": "completed",
        }
        
        # 첫 번째 생성
        first_response = await client.post(
            "/api/v1/trades/",
            json=trade_data,
        )
        assert first_response.status_code == 201
        
        # 중복 생성 시도
        duplicate_response = await client.post(
            "/api/v1/trades/",
            json=trade_data,
        )
        assert duplicate_response.status_code == 409
        
        # 데이터 개수 확인 (1개만 존재해야 함)
        list_response = await client.get("/api/v1/trades/")
        data = list_response.json()
        assert data["total"] == 1
    
    async def test_invalid_bot_control_action(
        self,
        client: AsyncClient,
    ):
        """
        Given: 잘못된 제어 명령
        When: POST /api/v1/bot/control
        Then: 400 Bad Request 반환
        """
        response = await client.post(
            "/api/v1/bot/control",
            json={"action": "invalid_action"},
        )
        
        assert response.status_code == 400
        assert "유효하지 않은" in response.json()["detail"]
    
    async def test_nonexistent_trade_query(
        self,
        client: AsyncClient,
    ):
        """
        Given: 존재하지 않는 trade_id
        When: GET /api/v1/trades/{trade_id}
        Then: 404 Not Found 반환
        """
        response = await client.get("/api/v1/trades/nonexistent_id_12345")
        
        assert response.status_code == 404
        assert "찾을 수 없습니다" in response.json()["detail"]


@pytest.mark.asyncio
class TestDataConsistency:
    """데이터 일관성 테스트"""
    
    async def test_trade_and_ai_decision_consistency(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: AI 판단과 거래 내역
        When: 매수 판단 후 실제 매수 거래 발생
        Then: 두 데이터가 일관성 있게 저장됨
        """
        symbol = "KRW-BTC"
        
        # 1. AI 판단 저장
        ai_decision = AIDecision(
            symbol=symbol,
            decision="buy",
            confidence=Decimal("90.0"),
            reason="강력한 매수 신호",
            market_data={"price": 95000000},
        )
        async_session.add(ai_decision)
        await async_session.commit()
        await async_session.refresh(ai_decision)
        
        # 2. 거래 실행
        trade_data = {
            "trade_id": "consistency_test_001",
            "symbol": symbol,
            "side": "buy",
            "price": "95000000.0",
            "amount": "0.001",
            "total": "95000.0",
            "fee": "47.5",
            "status": "completed",
        }
        await client.post("/api/v1/trades/", json=trade_data)
        
        # 3. 데이터 일관성 확인
        # AI 판단 조회
        ai_query = select(AIDecision).where(
            AIDecision.symbol == symbol
        ).order_by(AIDecision.created_at.desc())
        ai_result = await async_session.execute(ai_query)
        latest_ai_decision = ai_result.scalar_one()
        
        # 거래 조회
        trade_query = select(Trade).where(
            Trade.symbol == symbol
        ).order_by(Trade.created_at.desc())
        trade_result = await async_session.execute(trade_query)
        latest_trade = trade_result.scalar_one()
        
        # 일관성 검증
        assert latest_ai_decision.decision == "buy"
        assert latest_trade.side == "buy"
        assert latest_ai_decision.symbol == latest_trade.symbol
        
        # 시간 순서 확인 (AI 판단이 거래보다 먼저 발생해야 함)
        assert latest_ai_decision.created_at <= latest_trade.created_at



