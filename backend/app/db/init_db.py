"""
데이터베이스 초기화 모듈
애플리케이션 시작 시 데이터베이스 테이블 생성 및 초기 데이터 설정을 담당합니다.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.models import (
    Trade,
    AIDecision,
    PortfolioSnapshot,
    Order,
    SystemLog,
    BotConfig,
)

logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """
    데이터베이스 테이블 생성
    모든 SQLAlchemy 모델을 기반으로 테이블을 생성합니다.
    """
    logger.info("📦 데이터베이스 테이블 생성 시작...")
    
    async with engine.begin() as conn:
        # 모든 테이블 생성 (존재하지 않는 경우에만)
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ 데이터베이스 테이블 생성 완료")


async def init_default_config(session: AsyncSession) -> None:
    """
    기본 봇 설정 초기화
    
    Args:
        session: 데이터베이스 세션
    """
    from sqlalchemy import select
    
    logger.info("⚙️ 기본 봇 설정 초기화 중...")
    
    # 기본 설정 값
    default_configs = [
        {
            "key": "bot_status",
            "value": {"enabled": False},
            "description": "봇 활성화 상태 (true: 활성, false: 비활성)"
        },
        {
            "key": "trading_interval_minutes",
            "value": {"minutes": 60},
            "description": "거래 실행 주기 (분 단위)"
        },
        {
            "key": "max_trade_amount_krw",
            "value": {"amount": 1000000},
            "description": "1회 최대 거래 금액 (KRW)"
        },
        {
            "key": "risk_level",
            "value": {"level": "medium"},
            "description": "리스크 수준 (low, medium, high)"
        },
        {
            "key": "target_symbols",
            "value": {"symbols": ["KRW-BTC", "KRW-ETH"]},
            "description": "거래 대상 심볼 목록"
        },
    ]
    
    # 기존 설정 확인 및 추가
    for config_data in default_configs:
        query = select(BotConfig).where(BotConfig.key == config_data["key"])
        result = await session.execute(query)
        existing = result.scalar_one_or_none()
        
        if not existing:
            config = BotConfig(**config_data)
            session.add(config)
            logger.info(f"  ➕ 설정 추가: {config_data['key']}")
        else:
            logger.info(f"  ✓ 설정 존재: {config_data['key']}")
    
    await session.commit()
    logger.info("✅ 기본 봇 설정 초기화 완료")


async def init_db() -> None:
    """
    데이터베이스 초기화 메인 함수
    
    1. 테이블 생성
    2. 기본 설정 데이터 추가
    """
    try:
        logger.info("🚀 데이터베이스 초기화 시작...")
        
        # 1. 테이블 생성
        await create_tables()
        
        # 2. 기본 설정 초기화
        from backend.app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            await init_default_config(session)
        
        logger.info("✅ 데이터베이스 초기화 완료!")
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}", exc_info=True)
        raise



