"""
스케줄러 테스트
TDD 원칙: APScheduler 통합 로직을 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.core.scheduler import (
    scheduler,
    trading_job,
    portfolio_snapshot_job,
    add_jobs,
    start_scheduler,
    stop_scheduler,
    get_jobs,
)


@pytest.mark.asyncio
class TestSchedulerJobs:
    """스케줄러 작업 테스트"""
    
    async def test_trading_job_executes_without_error(self):
        """
        Given: 트레이딩 작업
        When: trading_job 실행
        Then: 에러 없이 완료
        """
        # When & Then
        # TODO 주석 처리로 인해 실제로는 로그만 출력
        await trading_job()
        # 에러 없이 완료되면 성공
    
    async def test_portfolio_snapshot_job_executes_without_error(self):
        """
        Given: 포트폴리오 스냅샷 작업
        When: portfolio_snapshot_job 실행
        Then: 에러 없이 완료
        """
        # When & Then
        await portfolio_snapshot_job()
        # 에러 없이 완료되면 성공
    
    @patch('backend.app.core.scheduler.logger')
    async def test_trading_job_logs_execution(self, mock_logger):
        """
        Given: 트레이딩 작업
        When: trading_job 실행
        Then: 시작 및 완료 로그 출력
        """
        # When
        await trading_job()
        
        # Then
        assert mock_logger.info.call_count >= 2
        # 시작 로그와 완료 로그
    
    @patch('backend.app.core.scheduler.logger')
    async def test_portfolio_snapshot_job_logs_execution(
        self,
        mock_logger,
    ):
        """
        Given: 포트폴리오 스냅샷 작업
        When: portfolio_snapshot_job 실행
        Then: 시작 및 완료 로그 출력
        """
        # When
        await portfolio_snapshot_job()
        
        # Then
        assert mock_logger.info.call_count >= 2


class TestSchedulerManagement:
    """스케줄러 관리 테스트"""
    
    def test_scheduler_instance_exists(self):
        """
        Given: 스케줄러 모듈
        When: scheduler 객체 확인
        Then: AsyncIOScheduler 인스턴스 존재
        """
        assert scheduler is not None
        assert hasattr(scheduler, 'add_job')
        assert hasattr(scheduler, 'start')
        assert hasattr(scheduler, 'shutdown')
    
    @patch('backend.app.core.scheduler.settings')
    @patch('backend.app.core.scheduler.scheduler')
    def test_add_jobs_when_enabled(self, mock_scheduler, mock_settings):
        """
        Given: 스케줄러 활성화 상태
        When: add_jobs 호출
        Then: 작업들이 등록됨
        """
        # Given
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.SCHEDULER_INTERVAL_MINUTES = 5
        mock_scheduler.add_job = MagicMock()
        
        # When
        add_jobs()
        
        # Then
        # trading_job과 portfolio_snapshot_job이 등록됨
        assert mock_scheduler.add_job.call_count >= 2
    
    @patch('backend.app.core.scheduler.settings')
    @patch('backend.app.core.scheduler.logger')
    def test_add_jobs_when_disabled(self, mock_logger, mock_settings):
        """
        Given: 스케줄러 비활성화 상태
        When: add_jobs 호출
        Then: 경고 로그 출력하고 작업 등록하지 않음
        """
        # Given
        mock_settings.SCHEDULER_ENABLED = False
        
        # When
        add_jobs()
        
        # Then
        mock_logger.warning.assert_called_once()
        assert "비활성화" in str(mock_logger.warning.call_args)
    
    @patch('backend.app.core.scheduler.scheduler')
    def test_start_scheduler(self, mock_scheduler):
        """
        Given: 스케줄러
        When: start_scheduler 호출
        Then: 작업 등록 및 스케줄러 시작
        """
        # Given
        mock_scheduler.running = False
        mock_scheduler.add_job = MagicMock()
        mock_scheduler.start = MagicMock()
        
        # When
        with patch('backend.app.core.scheduler.add_jobs'):
            start_scheduler()
        
        # Then
        mock_scheduler.start.assert_called_once()
    
    @patch('backend.app.core.scheduler.scheduler')
    @patch('backend.app.core.scheduler.logger')
    def test_start_scheduler_already_running(
        self,
        mock_logger,
        mock_scheduler,
    ):
        """
        Given: 이미 실행 중인 스케줄러
        When: start_scheduler 호출
        Then: 경고 로그만 출력
        """
        # Given
        mock_scheduler.running = True
        
        # When
        start_scheduler()
        
        # Then
        mock_logger.warning.assert_called_once()
        assert "이미 실행 중" in str(mock_logger.warning.call_args)
    
    @patch('backend.app.core.scheduler.scheduler')
    def test_stop_scheduler(self, mock_scheduler):
        """
        Given: 실행 중인 스케줄러
        When: stop_scheduler 호출
        Then: 스케줄러 종료
        """
        # Given
        mock_scheduler.running = True
        mock_scheduler.shutdown = MagicMock()
        
        # When
        stop_scheduler()
        
        # Then
        mock_scheduler.shutdown.assert_called_once_with(wait=True)
    
    @patch('backend.app.core.scheduler.scheduler')
    def test_get_jobs_returns_list(self, mock_scheduler):
        """
        Given: 등록된 작업들
        When: get_jobs 호출
        Then: 작업 정보 리스트 반환
        """
        # Given
        mock_job = MagicMock()
        mock_job.id = "trading_job"
        mock_job.name = "주기적 트레이딩 작업"
        mock_job.next_run_time = None
        mock_job.trigger = "interval[0:05:00]"
        
        mock_scheduler.get_jobs = MagicMock(return_value=[mock_job])
        
        # When
        jobs = get_jobs()
        
        # Then
        assert isinstance(jobs, list)
        assert len(jobs) == 1
        assert jobs[0]["id"] == "trading_job"
        assert jobs[0]["name"] == "주기적 트레이딩 작업"



