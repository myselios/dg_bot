"""
거래 내역 API 테스트
TDD 원칙: API 엔드포인트의 동작을 검증합니다.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from backend.app.models.trade import Trade


@pytest.mark.asyncio
class TestTradesAPI:
    """거래 내역 API 테스트 클래스"""
    
    async def test_get_trades_empty(self, client: AsyncClient):
        """
        Given: 데이터베이스에 거래 내역이 없을 때
        When: GET /api/v1/trades/ 요청
        Then: 빈 배열과 total=0을 반환해야 함
        """
        response = await client.get("/api/v1/trades/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["trades"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 50
    
    async def test_create_trade_success(
        self,
        client: AsyncClient,
        sample_trade_data: dict,
    ):
        """
        Given: 유효한 거래 데이터
        When: POST /api/v1/trades/ 요청
        Then: 거래가 생성되고 201 상태 코드 반환
        """
        response = await client.post(
            "/api/v1/trades/",
            json=sample_trade_data,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["trade_id"] == sample_trade_data["trade_id"]
        assert data["symbol"] == sample_trade_data["symbol"]
        assert data["side"] == sample_trade_data["side"]
        assert "id" in data
        assert "created_at" in data
    
    async def test_create_trade_duplicate(
        self,
        client: AsyncClient,
        sample_trade_data: dict,
    ):
        """
        Given: 이미 존재하는 trade_id
        When: 동일한 trade_id로 POST 요청
        Then: 409 Conflict 에러 반환
        """
        # 첫 번째 생성
        await client.post("/api/v1/trades/", json=sample_trade_data)
        
        # 중복 생성 시도
        response = await client.post("/api/v1/trades/", json=sample_trade_data)
        
        assert response.status_code == 409
        assert "이미 존재하는" in response.json()["detail"]
    
    async def test_get_trade_by_id(
        self,
        client: AsyncClient,
        sample_trade_data: dict,
    ):
        """
        Given: 생성된 거래 내역
        When: GET /api/v1/trades/{trade_id} 요청
        Then: 해당 거래 정보 반환
        """
        # 거래 생성
        create_response = await client.post(
            "/api/v1/trades/",
            json=sample_trade_data,
        )
        trade_id = sample_trade_data["trade_id"]
        
        # 조회
        response = await client.get(f"/api/v1/trades/{trade_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["trade_id"] == trade_id
    
    async def test_get_trade_not_found(self, client: AsyncClient):
        """
        Given: 존재하지 않는 trade_id
        When: GET /api/v1/trades/{trade_id} 요청
        Then: 404 Not Found 반환
        """
        response = await client.get("/api/v1/trades/nonexistent_trade_id")
        
        assert response.status_code == 404
        assert "찾을 수 없습니다" in response.json()["detail"]
    
    async def test_get_trades_with_pagination(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 10개의 거래 내역
        When: limit=5로 GET 요청
        Then: 5개만 반환되고 total=10이어야 함
        """
        # 10개 거래 생성
        for i in range(10):
            trade = Trade(
                trade_id=f"test_trade_{i:03d}",
                symbol="KRW-BTC",
                side="buy" if i % 2 == 0 else "sell",
                price=Decimal("95000000"),
                amount=Decimal("0.00052631"),
                total=Decimal("50000"),
                fee=Decimal("25"),
                status="completed",
            )
            async_session.add(trade)
        await async_session.commit()
        
        # 페이지네이션 조회
        response = await client.get("/api/v1/trades/?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) == 5
        assert data["total"] == 10
        assert data["page_size"] == 5
    
    async def test_get_trades_filter_by_symbol(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: BTC와 ETH 거래 내역
        When: symbol=KRW-BTC로 필터링
        Then: BTC 거래만 반환
        """
        # BTC 거래 3개
        for i in range(3):
            trade = Trade(
                trade_id=f"btc_trade_{i}",
                symbol="KRW-BTC",
                side="buy",
                price=Decimal("95000000"),
                amount=Decimal("0.00052631"),
                total=Decimal("50000"),
                fee=Decimal("25"),
                status="completed",
            )
            async_session.add(trade)
        
        # ETH 거래 2개
        for i in range(2):
            trade = Trade(
                trade_id=f"eth_trade_{i}",
                symbol="KRW-ETH",
                side="buy",
                price=Decimal("3500000"),
                amount=Decimal("0.01428571"),
                total=Decimal("50000"),
                fee=Decimal("25"),
                status="completed",
            )
            async_session.add(trade)
        
        await async_session.commit()
        
        # BTC만 조회
        response = await client.get("/api/v1/trades/?symbol=KRW-BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert all(t["symbol"] == "KRW-BTC" for t in data["trades"])
    
    async def test_get_trades_filter_by_side(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 매수/매도 거래 내역
        When: side=buy로 필터링
        Then: 매수 거래만 반환
        """
        # 매수 3개, 매도 2개
        for i in range(5):
            trade = Trade(
                trade_id=f"trade_{i}",
                symbol="KRW-BTC",
                side="buy" if i < 3 else "sell",
                price=Decimal("95000000"),
                amount=Decimal("0.00052631"),
                total=Decimal("50000"),
                fee=Decimal("25"),
                status="completed",
            )
            async_session.add(trade)
        
        await async_session.commit()
        
        # 매수만 조회
        response = await client.get("/api/v1/trades/?side=buy")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert all(t["side"] == "buy" for t in data["trades"])
    
    async def test_get_trade_statistics(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ):
        """
        Given: 여러 거래 내역
        When: GET /api/v1/trades/statistics/summary 요청
        Then: 통계 정보 반환 (총 거래 수, 거래량, 평균 가격 등)
        """
        # 매수 2개
        for i in range(2):
            trade = Trade(
                trade_id=f"buy_trade_{i}",
                symbol="KRW-BTC",
                side="buy",
                price=Decimal("95000000"),
                amount=Decimal("0.001"),
                total=Decimal("95000"),
                fee=Decimal("47.5"),
                status="completed",
            )
            async_session.add(trade)
        
        # 매도 1개
        trade = Trade(
            trade_id="sell_trade_0",
            symbol="KRW-BTC",
            side="sell",
            price=Decimal("100000000"),
            amount=Decimal("0.001"),
            total=Decimal("100000"),
            fee=Decimal("50"),
            status="completed",
        )
        async_session.add(trade)
        
        await async_session.commit()
        
        # 통계 조회
        response = await client.get("/api/v1/trades/statistics/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_trades"] == 3
        assert data["total_buy"] == 2
        assert data["total_sell"] == 1
        assert float(data["total_volume_krw"]) == 290000.0  # 95k*2 + 100k
        assert float(data["total_fee"]) == 145.0  # 47.5*2 + 50
        assert float(data["avg_buy_price"]) == 95000000.0
        assert float(data["avg_sell_price"]) == 100000000.0



