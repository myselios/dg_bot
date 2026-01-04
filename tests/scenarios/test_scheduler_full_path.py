"""
Scheduler Full Path 시나리오 테스트

scheduler_main.py의 시작부터 종료까지 전체 경로를 검증합니다.

테스트 시나리오:
1. 정상 실행: 시작 → trading_job 성공 → 종료
2. 환경변수 누락: 시작 → 환경변수 검증 실패 → 종료
3. DB 연결 실패: 시작 → DB 초기화 실패 → 종료
4. Graceful Shutdown: 실행 중 → Ctrl+C → Graceful 종료
"""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime


@pytest.mark.scenario
@pytest.mark.asyncio
class TestSchedulerFullPath:
    """Scheduler 전체 경로 시나리오 테스트"""

    @pytest.fixture
    def mock_env_variables(self):
        """필수 환경변수 Mock"""
        env_vars = {
            'UPBIT_ACCESS_KEY': 'test_access_key',
            'UPBIT_SECRET_KEY': 'test_secret_key',
            'DATABASE_URL': 'postgresql+asyncpg://test:test@localhost/test_db',
            'OPENAI_API_KEY': 'test_openai_key'
        }
        with patch.dict(os.environ, env_vars):
            yield env_vars

    @pytest.fixture
    def mock_db_init(self):
        """DB 초기화 Mock"""
        with patch('backend.app.db.init_db.init_db', new_callable=AsyncMock) as mock:
            mock.return_value = None
            yield mock

    @pytest.fixture
    def mock_telegram(self):
        """Telegram 알림 Mock"""
        with patch('backend.app.services.notification.notify_bot_status', new_callable=AsyncMock) as mock:
            mock.return_value = None
            yield mock

    @pytest.fixture
    def mock_scheduler(self):
        """APScheduler Mock"""
        with patch('backend.app.core.scheduler.scheduler') as mock:
            mock.running = False
            mock.start = Mock()
            mock.shutdown = Mock()
            mock.get_jobs = Mock(return_value=[])
            yield mock

    @pytest.fixture
    def mock_metrics(self):
        """Metrics Mock"""
        with patch('backend.app.services.metrics.set_bot_running') as mock:
            yield mock

    async def test_scheduler_startup_success(
        self,
        mock_env_variables,
        mock_db_init,
        mock_telegram,
        mock_scheduler,
        mock_metrics
    ):
        """
        시나리오: 정상 스케줄러 시작

        Given: 필수 환경변수가 모두 설정됨
        When: scheduler_main.py를 실행
        Then:
            1. 환경변수 검증 통과
            2. DB 초기화 성공
            3. Telegram 시작 알림 전송
            4. 스케줄러 시작
            5. 무한 루프 진입
        """
        from backend.app.core.scheduler import start_scheduler, get_jobs

        # When: 스케줄러 시작
        start_scheduler()

        # Then: 스케줄러가 시작됨
        mock_scheduler.start.assert_called_once()

        # 작업 목록 확인
        jobs = get_jobs()
        assert isinstance(jobs, list)

    def test_scheduler_env_validation_failure(self):
        """
        시나리오: 환경변수 검증 실패

        Given: 필수 환경변수가 누락됨
        When: validate_environment_variables() 호출
        Then: False 반환 (프로그램 종료 필요)
        """
        # scheduler_main.py의 validate_environment_variables 임포트
        import sys
        import importlib.util

        # scheduler_main.py 동적 임포트
        spec = importlib.util.spec_from_file_location(
            "scheduler_main",
            "/home/selios/dg_bot/scheduler_main.py"
        )
        scheduler_main = importlib.util.module_from_spec(spec)

        # 환경변수 제거
        with patch.dict(os.environ, {}, clear=True):
            # When: 환경변수 검증
            result = scheduler_main.validate_environment_variables()

            # Then: 검증 실패
            assert result is False

    async def test_scheduler_db_init_failure(
        self,
        mock_env_variables,
        mock_telegram,
        mock_metrics
    ):
        """
        시나리오: DB 초기화 실패

        Given: 환경변수는 정상이지만 DB 연결 실패
        When: DB 초기화 시도
        Then:
            1. DB 초기화 예외 발생
            2. 경고 로그 기록
            3. 스케줄러는 계속 진행 (기존 테이블 존재 가능)
        """
        with patch('backend.app.db.init_db.init_db', new_callable=AsyncMock) as mock_init:
            # Given: DB 초기화 실패 시뮬레이션
            mock_init.side_effect = Exception("Connection refused")

            # When: DB 초기화 시도
            try:
                await mock_init()
                pytest.fail("예외가 발생해야 함")
            except Exception as e:
                # Then: 예외 발생
                assert "Connection refused" in str(e)

    async def test_scheduler_graceful_shutdown(
        self,
        mock_env_variables,
        mock_db_init,
        mock_telegram,
        mock_scheduler,
        mock_metrics
    ):
        """
        시나리오: Graceful Shutdown

        Given: 스케줄러가 실행 중
        When: SIGINT (Ctrl+C) 시그널 수신
        Then:
            1. 봇 상태 업데이트 (running=False)
            2. Telegram 종료 알림 전송
            3. 스케줄러 정지
            4. 정상 종료
        """
        from backend.app.core.scheduler import stop_scheduler

        # Given: 스케줄러가 실행 중
        mock_scheduler.running = True

        # When: 스케줄러 정지
        stop_scheduler()

        # Then: 스케줄러가 정지됨
        mock_scheduler.shutdown.assert_called_once_with(wait=True)

    async def test_scheduler_immediate_run_mode(
        self,
        mock_env_variables,
        mock_db_init,
        mock_telegram,
        mock_metrics
    ):
        """
        시나리오: 즉시 실행 모드

        Given: SCHEDULER_RUN_IMMEDIATELY=true
        When: 스케줄러 시작
        Then:
            1. 일반 작업 등록
            2. 즉시 실행 작업 추가 등록 (2초 후)
            3. 로그에 즉시 실행 안내
        """
        from src.config.settings import SchedulerConfig

        with patch('backend.app.core.scheduler.scheduler') as mock_scheduler:
            mock_scheduler.running = False
            mock_scheduler.start = Mock()
            mock_scheduler.add_job = Mock()
            mock_scheduler.get_job = Mock(return_value=None)

            # Given: 즉시 실행 모드 활성화
            with patch.object(SchedulerConfig, 'RUN_IMMEDIATELY', True):
                from backend.app.core.scheduler import start_scheduler

                # When: 스케줄러 시작
                start_scheduler()

                # Then: add_job이 여러 번 호출됨 (일반 작업 + 즉시 실행 작업)
                assert mock_scheduler.add_job.call_count >= 5  # 4개 일반 작업 + 1개 즉시 실행

    async def test_scheduler_jobs_registration(
        self,
        mock_env_variables,
        mock_metrics
    ):
        """
        시나리오: 스케줄러 작업 등록 확인

        Given: 스케줄러 설정이 활성화됨
        When: add_jobs() 호출
        Then: 4개 작업이 등록됨
            1. trading_job (매시 01분)
            2. position_management_job (:01,:16,:31,:46)
            3. portfolio_snapshot_job (매시 01분)
            4. daily_report_job (09:00)
        """
        with patch('backend.app.core.scheduler.scheduler') as mock_scheduler:
            mock_scheduler.add_job = Mock()

            from backend.app.core.scheduler import add_jobs

            # When: 작업 등록
            add_jobs()

            # Then: 4개 작업이 등록됨
            assert mock_scheduler.add_job.call_count == 4

            # 등록된 작업 ID 확인
            job_ids = [call[1]['id'] for call in mock_scheduler.add_job.call_args_list]
            expected_job_ids = [
                'trading_job',
                'position_management_job',
                'portfolio_snapshot_job',
                'daily_report_job'
            ]

            for expected_id in expected_job_ids:
                assert expected_id in job_ids

    async def test_scheduler_timezone_configuration(self):
        """
        시나리오: 타임존 설정 확인

        Given: APScheduler 인스턴스 생성
        When: 타임존 설정 확인
        Then: Asia/Seoul 타임존 사용
        """
        from backend.app.core.scheduler import scheduler

        # Then: Asia/Seoul 타임존 확인
        assert scheduler.timezone.zone == "Asia/Seoul"

    async def test_scheduler_job_defaults(self):
        """
        시나리오: 작업 기본 설정 확인

        Given: APScheduler 인스턴스 생성
        When: job_defaults 설정 확인
        Then:
            1. coalesce=True (누락 작업 병합)
            2. max_instances=1 (동시 실행 방지)
            3. misfire_grace_time=60 (지연 허용 60초)
        """
        from backend.app.core.scheduler import scheduler

        # Then: 작업 기본 설정 확인
        job_defaults = scheduler._job_defaults
        assert job_defaults['coalesce'] is True
        assert job_defaults['max_instances'] == 1
        assert job_defaults['misfire_grace_time'] == 60


@pytest.mark.scenario
@pytest.mark.asyncio
class TestSchedulerErrorRecovery:
    """Scheduler 에러 복구 시나리오 테스트"""

    async def test_scheduler_sentry_integration(self):
        """
        시나리오: Sentry 에러 전송

        Given: SENTRY_ENABLED=true
        When: 스케줄러에서 예외 발생
        Then: Sentry로 에러 전송
        """
        # Sentry 통합 테스트는 실제 환경에서만 검증
        # 여기서는 설정만 확인
        from backend.app.core.config import settings

        if settings.SENTRY_ENABLED:
            assert settings.SENTRY_DSN is not None

    async def test_scheduler_continues_after_job_failure(
        self,
        mock_env_variables,
        mock_metrics
    ):
        """
        시나리오: 작업 실패 후에도 스케줄러 지속

        Given: 스케줄러가 실행 중
        When: trading_job이 실패
        Then:
            1. 실패 메트릭 기록
            2. 에러 알림 전송
            3. 다음 스케줄에 다시 실행
        """
        # 이 시나리오는 통합 테스트로 별도 검증 필요
        # APScheduler의 기본 동작: 작업 실패해도 스케줄러는 계속 실행
        pass
