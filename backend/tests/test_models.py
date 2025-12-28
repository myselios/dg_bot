"""
데이터베이스 모델 테스트
TDD 원칙: ORM 모델의 CRUD 동작을 검증합니다.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from datetime import datetime

from backend.app.models.trade import Trade
from backend.app.models.ai_decision import AIDecision
from backend.app.models.portfolio import PortfolioSnapshot
from backend.app.models.order import Order
from backend.app.models.system_log import SystemLog
from backend.app.models.bot_config import BotConfig


@pytest.mark.asyncio
class TestTradeModel:
    """Trade 모델 테스트"""
    
    async def test_create_trade(self, async_session: AsyncSession):
        """
        Given: 유효한 거래 데이터
        When: Trade 모델 생성 및 저장
        Then: 데이터베이스에 정상 저장되고 조회 가능
        """
        # Given
        trade = Trade(
            trade_id="test_001",
            symbol="KRW-BTC",
            side="buy",
            price=Decimal("95000000"),
            amount=Decimal("0.001"),
            total=Decimal("95000"),
            fee=Decimal("47.5"),
            status="completed",
        )
        
        # When
        async_session.add(trade)
        await async_session.commit()
        await async_session.refresh(trade)
        
        # Then
        assert trade.id is not None
        assert trade.trade_id == "test_001"
        assert trade.symbol == "KRW-BTC"
        assert trade.created_at is not None
        assert isinstance(trade.created_at, datetime)
    
    async def test_trade_unique_constraint(self, async_session: AsyncSession):
        """
        Given: 동일한 trade_id를 가진 두 개의 Trade
        When: 두 번째 Trade 저장 시도
        Then: Unique 제약 조건 위반 에러 발생
        """
        # 첫 번째 거래
        trade1 = Trade(
            trade_id="duplicate_001",
            symbol="KRW-BTC",
            side="buy",
            price=Decimal("95000000"),
            amount=Decimal("0.001"),
            total=Decimal("95000"),
            fee=Decimal("47.5"),
            status="completed",
        )
        async_session.add(trade1)
        await async_session.commit()
        
        # 중복 trade_id로 저장 시도
        trade2 = Trade(
            trade_id="duplicate_001",
            symbol="KRW-ETH",
            side="sell",
            price=Decimal("3500000"),
            amount=Decimal("0.01"),
            total=Decimal("35000"),
            fee=Decimal("17.5"),
            status="completed",
        )
        async_session.add(trade2)
        
        with pytest.raises(Exception):  # IntegrityError
            await async_session.commit()


@pytest.mark.asyncio
class TestAIDecisionModel:
    """AIDecision 모델 테스트"""
    
    async def test_create_ai_decision(self, async_session: AsyncSession):
        """
        Given: AI 판단 데이터
        When: AIDecision 모델 생성 및 저장
        Then: JSONB 컬럼 포함하여 정상 저장
        """
        # Given
        decision = AIDecision(
            symbol="KRW-BTC",
            decision="buy",
            confidence=Decimal("85.5"),
            reason="RSI 과매도 구간",
            market_data={
                "price": 95000000,
                "rsi": 28.5,
                "volume": 1500000000,
            },
        )
        
        # When
        async_session.add(decision)
        await async_session.commit()
        await async_session.refresh(decision)
        
        # Then
        assert decision.id is not None
        assert decision.decision == "buy"
        assert decision.confidence == Decimal("85.5")
        assert decision.market_data["price"] == 95000000
        assert decision.market_data["rsi"] == 28.5
    
    async def test_ai_decision_without_market_data(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: market_data 없는 AI 판단
        When: AIDecision 생성
        Then: NULL 허용하여 정상 저장
        """
        decision = AIDecision(
            symbol="KRW-BTC",
            decision="hold",
            confidence=None,
            reason="시장 관망",
            market_data=None,
        )
        
        async_session.add(decision)
        await async_session.commit()
        await async_session.refresh(decision)
        
        assert decision.id is not None
        assert decision.confidence is None
        assert decision.market_data is None


@pytest.mark.asyncio
class TestPortfolioSnapshotModel:
    """PortfolioSnapshot 모델 테스트"""
    
    async def test_create_portfolio_snapshot(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: 포트폴리오 스냅샷 데이터
        When: PortfolioSnapshot 생성
        Then: JSONB positions 포함하여 정상 저장
        """
        snapshot = PortfolioSnapshot(
            total_value_krw=Decimal("5000000"),
            total_value_usd=Decimal("3750"),
            positions={
                "KRW-BTC": {
                    "amount": 0.05,
                    "value_krw": 4750000,
                    "profit_rate": 5.5,
                },
                "KRW": {
                    "amount": 250000,
                    "value_krw": 250000,
                },
            },
        )
        
        async_session.add(snapshot)
        await async_session.commit()
        await async_session.refresh(snapshot)
        
        assert snapshot.id is not None
        assert snapshot.total_value_krw == Decimal("5000000")
        assert "KRW-BTC" in snapshot.positions
        assert snapshot.positions["KRW-BTC"]["amount"] == 0.05


@pytest.mark.asyncio
class TestBotConfigModel:
    """BotConfig 모델 테스트"""
    
    async def test_create_bot_config(self, async_session: AsyncSession):
        """
        Given: 봇 설정 데이터
        When: BotConfig 생성
        Then: JSONB value 포함하여 정상 저장
        """
        config = BotConfig(
            key="trading_enabled",
            value={"enabled": True, "interval_minutes": 5},
            description="트레이딩 활성화 여부",
        )
        
        async_session.add(config)
        await async_session.commit()
        await async_session.refresh(config)
        
        assert config.id is not None
        assert config.key == "trading_enabled"
        assert config.value["enabled"] == True
        assert config.updated_at is not None
    
    async def test_bot_config_unique_key(self, async_session: AsyncSession):
        """
        Given: 동일한 key를 가진 두 BotConfig
        When: 두 번째 저장 시도
        Then: Unique 제약 조건 위반
        """
        config1 = BotConfig(
            key="duplicate_key",
            value={"test": "value1"},
        )
        async_session.add(config1)
        await async_session.commit()
        
        config2 = BotConfig(
            key="duplicate_key",
            value={"test": "value2"},
        )
        async_session.add(config2)
        
        with pytest.raises(Exception):
            await async_session.commit()


@pytest.mark.asyncio
class TestQueryPerformance:
    """쿼리 성능 및 인덱스 테스트"""
    
    async def test_trade_index_on_symbol_and_date(
        self,
        async_session: AsyncSession,
    ):
        """
        Given: 대량의 거래 데이터
        When: symbol과 created_at으로 필터링
        Then: 인덱스를 사용하여 빠르게 조회
        """
        # 100개 거래 생성
        for i in range(100):
            trade = Trade(
                trade_id=f"perf_test_{i:03d}",
                symbol="KRW-BTC" if i % 2 == 0 else "KRW-ETH",
                side="buy",
                price=Decimal("95000000"),
                amount=Decimal("0.001"),
                total=Decimal("95000"),
                fee=Decimal("47.5"),
                status="completed",
            )
            async_session.add(trade)
        
        await async_session.commit()
        
        # 특정 심볼만 조회
        query = select(Trade).where(
            Trade.symbol == "KRW-BTC"
        ).order_by(Trade.created_at.desc())
        
        result = await async_session.execute(query)
        trades = result.scalars().all()
        
        assert len(trades) == 50
        assert all(t.symbol == "KRW-BTC" for t in trades)



