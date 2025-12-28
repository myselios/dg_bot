"""
Pytest 설정 및 공통 픽스처
TDD 원칙: 재사용 가능한 테스트 데이터와 Mock 객체를 정의합니다.
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.core.config import settings

# 테스트용 데이터베이스 URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    이벤트 루프 픽스처
    비동기 테스트를 위한 이벤트 루프를 생성합니다.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """
    테스트용 비동기 엔진
    인메모리 SQLite 데이터베이스를 사용합니다.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    테스트용 비동기 세션
    각 테스트마다 독립적인 세션을 제공합니다.
    """
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    테스트용 HTTP 클라이언트
    FastAPI 앱에 대한 비동기 HTTP 요청을 수행합니다.
    """
    async def override_get_db():
        yield async_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


# 샘플 데이터 픽스처
@pytest.fixture
def sample_trade_data():
    """샘플 거래 데이터"""
    return {
        "trade_id": "test_trade_001",
        "symbol": "KRW-BTC",
        "side": "buy",
        "price": "95000000.0",
        "amount": "0.00052631",
        "total": "50000.0",
        "fee": "25.0",
        "status": "completed",
    }


@pytest.fixture
def sample_ai_decision_data():
    """샘플 AI 판단 데이터"""
    return {
        "symbol": "KRW-BTC",
        "decision": "buy",
        "confidence": "85.5",
        "reason": "RSI 과매도 구간, MACD 골든크로스 발생",
        "market_data": {
            "price": 95000000,
            "rsi": 28.5,
            "macd": {"value": 1.2, "signal": 0.8},
        },
    }


@pytest.fixture
def sample_portfolio_data():
    """샘플 포트폴리오 데이터"""
    return {
        "total_value_krw": "5000000.0",
        "total_value_usd": "3750.0",
        "positions": {
            "KRW-BTC": {
                "amount": "0.05",
                "value_krw": "4750000.0",
                "avg_buy_price": "95000000.0",
                "profit_rate": "5.5",
                "profit_amount": "250000.0",
            },
            "KRW": {
                "amount": "250000.0",
                "value_krw": "250000.0",
            },
        },
    }



