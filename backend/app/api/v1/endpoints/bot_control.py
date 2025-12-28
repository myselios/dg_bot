"""
봇 제어 API 엔드포인트
봇의 시작/중지 및 설정 변경을 처리합니다.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Dict, Any

from backend.app.db.session import get_db
from backend.app.models.bot_config import BotConfig

router = APIRouter()


class BotStatus(BaseModel):
    """봇 상태 응답"""
    is_running: bool = Field(..., description="봇 실행 여부")
    symbol: str = Field(..., description="거래 중인 심볼")
    interval_minutes: int = Field(..., description="실행 주기 (분)")
    last_run: str | None = Field(None, description="마지막 실행 시각")
    next_run: str | None = Field(None, description="다음 실행 예정 시각")


class BotControlRequest(BaseModel):
    """봇 제어 요청"""
    action: str = Field(..., description="제어 명령: start, stop, pause")
    reason: str | None = Field(None, description="제어 사유")


class ConfigUpdateRequest(BaseModel):
    """설정 업데이트 요청"""
    key: str = Field(..., description="설정 키")
    value: Dict[str, Any] = Field(..., description="설정 값 (JSON)")
    description: str | None = Field(None, description="설정 설명")


@router.get("/status", response_model=BotStatus)
async def get_bot_status(
    db: AsyncSession = Depends(get_db),
) -> BotStatus:
    """
    현재 봇 상태 조회
    
    실행 여부, 거래 심볼, 실행 주기 등의 정보를 반환합니다.
    """
    # 봇 설정 조회
    query = select(BotConfig).where(BotConfig.key == "bot_status")
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    
    if not config:
        # 기본값 반환
        return BotStatus(
            is_running=False,
            symbol="KRW-BTC",
            interval_minutes=5,
            last_run=None,
            next_run=None,
        )
    
    # config.value에서 필드 추출, 누락된 경우 기본값 사용
    value = config.value
    return BotStatus(
        is_running=value.get("is_running", False),
        symbol=value.get("symbol", "KRW-BTC"),
        interval_minutes=value.get("interval_minutes", 5),
        last_run=value.get("last_run"),
        next_run=value.get("next_run"),
    )


@router.post("/control", response_model=Dict[str, str])
async def control_bot(
    request: BotControlRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """
    봇 제어
    
    - **start**: 봇 시작
    - **stop**: 봇 중지
    - **pause**: 일시 정지
    """
    if request.action not in ["start", "stop", "pause"]:
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 제어 명령입니다. (start, stop, pause 중 선택)"
        )
    
    # 현재 상태 조회
    query = select(BotConfig).where(BotConfig.key == "bot_status")
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    
    if not config:
        # 새로 생성
        config = BotConfig(
            key="bot_status",
            value={
                "is_running": request.action == "start",
                "symbol": "KRW-BTC",
                "interval_minutes": 5,
                "last_run": None,
                "next_run": None,
            },
            description="봇 실행 상태",
        )
        db.add(config)
    else:
        # 상태 업데이트
        config.value["is_running"] = request.action == "start"
    
    await db.commit()
    
    # TODO: 실제 스케줄러 제어 로직 추가
    # from backend.app.core.scheduler import scheduler
    # if request.action == "start":
    #     scheduler.resume()
    # elif request.action == "stop":
    #     scheduler.pause()
    
    return {
        "status": "success",
        "message": f"봇이 {request.action} 되었습니다.",
    }


@router.get("/config/{key}")
async def get_config(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """특정 설정 조회"""
    query = select(BotConfig).where(BotConfig.key == key)
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="설정을 찾을 수 없습니다.")
    
    return {
        "key": config.key,
        "value": config.value,
        "description": config.description,
        "updated_at": config.updated_at.isoformat(),
    }


@router.post("/config", response_model=Dict[str, str])
async def update_config(
    request: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """
    봇 설정 업데이트
    
    런타임에 봇 동작을 변경할 수 있습니다.
    """
    # 기존 설정 조회
    query = select(BotConfig).where(BotConfig.key == request.key)
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    
    if not config:
        # 새로 생성
        config = BotConfig(
            key=request.key,
            value=request.value,
            description=request.description,
        )
        db.add(config)
    else:
        # 업데이트
        config.value = request.value
        if request.description:
            config.description = request.description
    
    await db.commit()
    
    return {
        "status": "success",
        "message": f"설정 '{request.key}'가 업데이트되었습니다.",
    }

