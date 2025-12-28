"""
FastAPI 메인 애플리케이션
트레이딩 봇의 REST API 서버입니다.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.api.v1.api import api_router

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Sentry 초기화 (전역)
if settings.SENTRY_ENABLED and settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    def before_send_filter(event, hint):
        """민감 정보 마스킹"""
        if 'request' in event:
            headers = event['request'].get('headers', {})
            # API 키 마스킹
            for key in ['Authorization', 'X-API-Key']:
                if key in headers:
                    headers[key] = '***MASKED***'
        
        # 환경변수 마스킹
        if 'extra' in event and 'sys.argv' in event['extra']:
            # 민감한 환경변수 마스킹
            pass
        
        return event
    
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=0.1,  # 10% 트랜잭션 샘플링 (비용 절감)
        profiles_sample_rate=0.1,  # 10% 프로파일링
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            LoggingIntegration(
                level=logging.INFO,  # INFO 이상 로그 캡처
                event_level=logging.ERROR  # ERROR 이상을 Sentry 이벤트로 전송
            ),
        ],
        before_send=before_send_filter,
        # 성능 향상 설정
        send_default_pii=False,  # 개인정보 전송 안 함
        attach_stacktrace=True,  # 스택 트레이스 포함
    )
    logger.info(f"✅ Sentry 초기화 완료 (환경: {settings.SENTRY_ENVIRONMENT})")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    애플리케이션 라이프사이클 관리
    
    시작 시: 데이터베이스 연결, 스케줄러 시작
    종료 시: 리소스 정리
    """
    logger.info("🚀 애플리케이션 시작 중...")
    
    # 데이터베이스 초기화
    try:
        from backend.app.db.init_db import init_db
        await init_db()
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
        # 초기화 실패 시에도 계속 진행 (테이블이 이미 존재할 수 있음)
    
    # TODO: 스케줄러 시작 (백엔드에서는 비활성화, scheduler 컨테이너에서 실행)
    # from backend.app.core.scheduler import scheduler
    # scheduler.start()
    # logger.info("✅ 스케줄러 시작됨")
    
    logger.info("✅ 애플리케이션 시작 완료")
    
    yield
    
    # 종료 시 정리
    logger.info("🛑 애플리케이션 종료 중...")
    
    # TODO: 스케줄러 중지
    # scheduler.shutdown()
    
    logger.info("✅ 애플리케이션 종료 완료")


# FastAPI 애플리케이션 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS 설정 - API 전용 (프론트엔드 제거됨)
# Grafana, Prometheus 등 모니터링 도구에서 API 접근 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router, prefix=settings.API_V1_STR)

# Prometheus 메트릭 엔드포인트 마운트
if settings.PROMETHEUS_ENABLED:
    from backend.app.services.metrics import metrics_app
    app.mount("/metrics", metrics_app)
    logger.info("✅ Prometheus 메트릭 엔드포인트 활성화: /metrics")


@app.get("/")
async def root() -> dict:
    """루트 엔드포인트"""
    return {
        "message": "Bitcoin Trading Bot API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
    }


@app.get("/health")
async def health_check() -> dict:
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """전역 예외 처리"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Sentry에 에러 전송 (이미 자동으로 전송되지만 명시적으로 컨텍스트 추가 가능)
    if settings.SENTRY_ENABLED:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("endpoint", str(request.url))
            scope.set_context("request", {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
            })
            sentry_sdk.capture_exception(exc)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "내부 서버 오류가 발생했습니다.",
            "type": type(exc).__name__,
        },
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )

