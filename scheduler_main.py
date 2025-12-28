"""
스케줄러 전용 실행 파일

main.py 로직을 1시간마다 자동 실행합니다.

사용법:
    python scheduler_main.py

중지:
    Ctrl + C (SIGINT)
"""
import asyncio
import signal
import sys
import logging
import os
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.app.core.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_jobs
)
from backend.app.services.notification import notify_bot_status
from backend.app.services.metrics import set_bot_running
from src.utils.logger import Logger

# 로그 디렉토리 생성
log_dir = project_root / "logs" / "scheduler"
log_dir.mkdir(parents=True, exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Sentry 초기화
from backend.app.core.config import settings

if settings.SENTRY_ENABLED and settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment="scheduler",
        traces_sample_rate=0.1,  # 10% 샘플링
        integrations=[
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            ),
        ],
        before_send=lambda event, hint: event,  # 민감 정보는 이미 backend에서 필터링됨
    )
    logger.info(f"✅ Sentry 초기화 완료 (Scheduler 환경)")


class GracefulKiller:
    """Graceful Shutdown 핸들러"""
    
    kill_now = False
    
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
    
    def exit_gracefully(self, signum, frame):
        """시그널 핸들러 (Ctrl+C 처리)"""
        self.kill_now = True


async def main():
    """스케줄러 메인 함수"""
    
    killer = GracefulKiller()
    
    try:
        # 프로그램 시작 배너
        print("\n" + "=" * 60)
        print("🤖 AI 자동 트레이딩 스케줄러")
        print("=" * 60)
        print(f"시작 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"실행 주기: 1시간 (60분)")
        print(f"중지 방법: Ctrl + C")
        print("=" * 60 + "\n")
        
        logger.info("=" * 60)
        logger.info("🤖 자동 트레이딩 스케줄러 시작")
        logger.info("=" * 60)
        
        # 데이터베이스 초기화
        try:
            from backend.app.db.init_db import init_db
            await init_db()
            logger.info("✅ 데이터베이스 초기화 완료")
        except Exception as e:
            logger.warning(f"데이터베이스 초기화 실패 (테이블이 이미 존재할 수 있음): {e}")
        
        # 봇 상태 업데이트
        set_bot_running(True)
        
        # Telegram 알림
        try:
            await notify_bot_status(
                status="started",
                message="스케줄러가 시작되었습니다. (주기: 1시간)"
            )
            logger.info("✅ Telegram 시작 알림 전송 완료")
        except Exception as e:
            logger.warning(f"Telegram 알림 전송 실패: {e}")
        
        # 스케줄러 시작
        start_scheduler()
        
        # 등록된 작업 확인
        jobs = get_jobs()
        logger.info(f"\n등록된 작업 목록 ({len(jobs)}개):")
        for job in jobs:
            logger.info(f"  - {job['id']}: {job['name']}")
            logger.info(f"    다음 실행: {job['next_run_time']}")
        logger.info("")
        
        # 무한 루프 (스케줄러 유지)
        logger.info("⏰ 스케줄러가 실행 중입니다... (Ctrl+C로 종료)")
        print("⏰ 스케줄러가 실행 중입니다... (Ctrl+C로 종료)\n")
        
        while not killer.kill_now:
            await asyncio.sleep(10)  # 10초마다 상태 체크
            
        # 종료 처리
        logger.info("\n시그널 수신: 스케줄러 종료 중...")
        print("\n시그널 수신: 스케줄러 종료 중...")
        
        # 봇 상태 업데이트
        set_bot_running(False)
        
        # Telegram 알림
        try:
            await notify_bot_status(
                status="stopped",
                message="사용자가 스케줄러를 중지했습니다."
            )
            logger.info("✅ Telegram 종료 알림 전송 완료")
        except Exception as e:
            logger.warning(f"Telegram 알림 전송 실패: {e}")
        
        # 스케줄러 정지
        stop_scheduler()
        
        logger.info("✅ 스케줄러가 안전하게 종료되었습니다.")
        print("✅ 스케줄러가 안전하게 종료되었습니다.\n")
        
    except Exception as e:
        logger.error(f"스케줄러 오류 발생: {e}", exc_info=True)
        print(f"\n❌ 스케줄러 오류 발생: {e}\n")
        
        # Sentry로 에러 전송
        if settings.SENTRY_ENABLED:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("component", "scheduler")
                scope.set_context("scheduler_info", {
                    "jobs_count": len(get_jobs()),
                    "error_time": datetime.now().isoformat(),
                })
                sentry_sdk.capture_exception(e)
                logger.info("✅ Sentry로 에러 전송 완료")
        
        # 에러 알림
        try:
            await notify_bot_status(
                status="stopped",
                message=f"오류로 인해 스케줄러가 중지되었습니다: {str(e)}"
            )
        except Exception as telegram_error:
            logger.warning(f"Telegram 에러 알림 전송 실패: {telegram_error}")
        
        # 봇 상태 업데이트
        set_bot_running(False)
        
        # 스케줄러 정지
        stop_scheduler()
        
        sys.exit(1)


def validate_environment_variables():
    """
    필수 환경변수 검증
    
    다이어그램 02-scheduler-module-flow.mmd와 일치:
    - 환경변수 누락 시 프로그램 종료
    
    Returns:
        bool: 모든 필수 환경변수가 존재하면 True
    """
    required_vars = {
        'UPBIT_ACCESS_KEY': 'Upbit API 액세스 키',
        'UPBIT_SECRET_KEY': 'Upbit API 시크릿 키',
        'DATABASE_URL': '데이터베이스 연결 URL',
        'OPENAI_API_KEY': 'OpenAI API 키'
    }
    
    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.getenv(var_name):
            missing_vars.append(f"  - {var_name}: {description}")
    
    if missing_vars:
        logger.error("=" * 60)
        logger.error("❌ 필수 환경변수가 누락되었습니다")
        logger.error("=" * 60)
        for var in missing_vars:
            logger.error(var)
        logger.error("=" * 60)
        logger.error("\n.env 파일을 확인하거나 환경변수를 설정해주세요.")
        logger.error("참고: .env.example 파일을 복사하여 .env 파일을 생성하세요.\n")
        return False
    
    logger.info("✅ 필수 환경변수 검증 완료")
    return True


if __name__ == "__main__":
    # .env 파일 확인 (선택적 - Docker에서는 env_file로 환경변수가 주입됨)
    if os.path.exists(".env"):
        # 로컬 실행 시 .env 파일에서 환경변수 로드
        from dotenv import load_dotenv
        load_dotenv()
    
    # 필수 환경변수 검증 (다이어그램 02-scheduler-module-flow.mmd)
    if not validate_environment_variables():
        logger.error("❌ 환경변수 검증 실패로 프로그램을 종료합니다.")
        sys.exit(1)
    
    # 비동기 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ 스케줄러가 종료되었습니다.\n")
        sys.exit(0)

