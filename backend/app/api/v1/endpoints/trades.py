"""
거래 내역 API 엔드포인트
"""
from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from backend.app.db.session import get_db
from backend.app.models.trade import Trade
from backend.app.schemas.trade import (
    TradeCreate,
    TradeResponse,
    TradeListResponse,
    TradeStatistics,
)

router = APIRouter()


@router.get("/", response_model=TradeListResponse)
async def get_trades(
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(50, ge=1, le=100, description="페이지당 항목 수"),
    symbol: str | None = Query(None, description="거래 심볼 필터"),
    side: str | None = Query(None, description="거래 방향 필터 (buy/sell)"),
    status: str | None = Query(None, description="거래 상태 필터"),
    from_date: datetime | None = Query(None, description="시작 날짜"),
    to_date: datetime | None = Query(None, description="종료 날짜"),
    db: AsyncSession = Depends(get_db),
) -> TradeListResponse:
    """
    거래 내역 목록 조회
    
    - **skip**: 페이지네이션을 위한 오프셋
    - **limit**: 페이지당 항목 수 (최대 100)
    - **symbol**: 특정 심볼만 필터링
    - **side**: buy 또는 sell 필터
    - **status**: 거래 상태 필터
    - **from_date**: 시작 날짜 (ISO 8601 형식)
    - **to_date**: 종료 날짜 (ISO 8601 형식)
    """
    # 기본 쿼리
    query = select(Trade)
    count_query = select(func.count(Trade.id))
    
    # 필터 적용
    conditions = []
    if symbol:
        conditions.append(Trade.symbol == symbol)
    if side:
        conditions.append(Trade.side == side)
    if status:
        conditions.append(Trade.status == status)
    if from_date:
        conditions.append(Trade.created_at >= from_date)
    if to_date:
        conditions.append(Trade.created_at <= to_date)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # 정렬 및 페이지네이션
    query = query.order_by(Trade.created_at.desc()).offset(skip).limit(limit)
    
    # 실행
    result = await db.execute(query)
    trades = result.scalars().all()
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    return TradeListResponse(
        trades=[TradeResponse.model_validate(trade) for trade in trades],
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: str,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    """특정 거래 내역 조회"""
    query = select(Trade).where(Trade.trade_id == trade_id)
    result = await db.execute(query)
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다.")
    
    return TradeResponse.model_validate(trade)


@router.post("/", response_model=TradeResponse, status_code=201)
async def create_trade(
    trade_in: TradeCreate,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    """
    새 거래 내역 생성
    
    거래 실행 후 결과를 데이터베이스에 저장합니다.
    """
    # 중복 거래 ID 확인
    query = select(Trade).where(Trade.trade_id == trade_in.trade_id)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=409, detail="이미 존재하는 거래 ID입니다.")
    
    # 거래 생성
    trade = Trade(**trade_in.model_dump())
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    
    return TradeResponse.model_validate(trade)


@router.get("/statistics/summary", response_model=TradeStatistics)
async def get_trade_statistics(
    symbol: str | None = Query(None, description="거래 심볼 필터"),
    days: int = Query(30, ge=1, le=365, description="기간 (일)"),
    db: AsyncSession = Depends(get_db),
) -> TradeStatistics:
    """
    거래 통계 조회
    
    - **symbol**: 특정 심볼만 집계
    - **days**: 최근 N일간의 데이터 집계
    """
    # 기간 필터
    from_date = datetime.utcnow() - timedelta(days=days)
    conditions = [Trade.created_at >= from_date, Trade.status == "completed"]
    
    if symbol:
        conditions.append(Trade.symbol == symbol)
    
    # 전체 통계
    total_query = select(func.count(Trade.id)).where(and_(*conditions))
    total_result = await db.execute(total_query)
    total_trades = total_result.scalar() or 0
    
    # 매수 통계
    buy_query = select(func.count(Trade.id)).where(
        and_(Trade.side == "buy", *conditions)
    )
    buy_result = await db.execute(buy_query)
    total_buy = buy_result.scalar() or 0
    
    # 매도 통계
    sell_query = select(func.count(Trade.id)).where(
        and_(Trade.side == "sell", *conditions)
    )
    sell_result = await db.execute(sell_query)
    total_sell = sell_result.scalar() or 0
    
    # 총 거래량 및 수수료
    sum_query = select(
        func.sum(Trade.total),
        func.sum(Trade.fee),
    ).where(and_(*conditions))
    sum_result = await db.execute(sum_query)
    total_volume, total_fee = sum_result.one()
    
    # 평균 매수가
    avg_buy_query = select(func.avg(Trade.price)).where(
        and_(Trade.side == "buy", *conditions)
    )
    avg_buy_result = await db.execute(avg_buy_query)
    avg_buy_price = avg_buy_result.scalar()
    
    # 평균 매도가
    avg_sell_query = select(func.avg(Trade.price)).where(
        and_(Trade.side == "sell", *conditions)
    )
    avg_sell_result = await db.execute(avg_sell_query)
    avg_sell_price = avg_sell_result.scalar()
    
    return TradeStatistics(
        total_trades=total_trades,
        total_buy=total_buy,
        total_sell=total_sell,
        total_volume_krw=total_volume or Decimal("0"),
        total_fee=total_fee or Decimal("0"),
        avg_buy_price=avg_buy_price,
        avg_sell_price=avg_sell_price,
    )



