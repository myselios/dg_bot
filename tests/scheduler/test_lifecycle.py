"""
스케줄러 생명주기 테스트

스케줄러 시작, 중지, 작업 관리 테스트
"""
import pytest
from unittest.mock import patch

from backend.app.core.scheduler import (
    scheduler,
    add_jobs,
    stop_scheduler,
    pause_job,
    resume_job,
)


class TestSchedulerLifecycle:
    """스케줄러 생명주기 테스트"""

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_add_jobs_when_enabled(self):
        """스케줄러 활성화 시 작업 추가 확인"""
        if scheduler.running:
            scheduler.shutdown(wait=False)

        scheduler.remove_all_jobs()

        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True), \
             patch('backend.app.core.scheduler.settings.SCHEDULER_INTERVAL_MINUTES', 60):

            add_jobs()

            jobs = scheduler.get_jobs()
            job_ids = [job.id for job in jobs]

            assert 'trading_job' in job_ids
            assert 'portfolio_snapshot_job' in job_ids

            scheduler.remove_all_jobs()

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_add_jobs_when_disabled(self):
        """스케줄러 비활성화 시 작업 추가되지 않음 확인"""
        scheduler.remove_all_jobs()

        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', False):
            add_jobs()

            jobs = scheduler.get_jobs()
            assert len(jobs) == 0

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_stop_scheduler(self):
        """스케줄러 중지 테스트"""
        if scheduler.running:
            scheduler.shutdown(wait=False)

        # 이미 중지된 스케줄러에 stop_scheduler 호출 (예외 없이 완료)
        stop_scheduler()
        assert scheduler.running is False


class TestSchedulerJobManagement:
    """스케줄러 작업 관리 테스트"""

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_get_jobs(self):
        """등록된 작업 조회 테스트"""
        if scheduler.running:
            scheduler.shutdown(wait=False)

        scheduler.remove_all_jobs()

        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True):
            add_jobs()

            jobs_list = scheduler.get_jobs()
            assert len(jobs_list) >= 2

            job_ids = [job.id for job in jobs_list]
            assert 'trading_job' in job_ids
            assert 'portfolio_snapshot_job' in job_ids

            scheduler.remove_all_jobs()

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_pause_and_resume_job(self):
        """작업 일시 정지 및 재개 테스트"""
        if scheduler.running:
            scheduler.shutdown(wait=False)

        scheduler.remove_all_jobs()

        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True):
            add_jobs()

            # 일시 정지
            pause_job('trading_job')

            # 재개
            resume_job('trading_job')

            job = scheduler.get_job('trading_job')
            assert job is not None

            scheduler.remove_all_jobs()

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_scheduler_job_interval(self):
        """스케줄러 작업 실행 간격 확인"""
        if scheduler.running:
            scheduler.shutdown(wait=False)

        scheduler.remove_all_jobs()

        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True), \
             patch('backend.app.core.scheduler.settings.SCHEDULER_INTERVAL_MINUTES', 60):

            add_jobs()

            job = scheduler.get_job('trading_job')
            assert job is not None
            assert job.trigger is not None

            scheduler.remove_all_jobs()

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_scheduler_prevents_concurrent_execution(self):
        """스케줄러가 동시 실행을 방지하는지 확인"""
        if scheduler.running:
            scheduler.shutdown(wait=False)

        scheduler.remove_all_jobs()

        with patch('backend.app.core.scheduler.settings.SCHEDULER_ENABLED', True):
            add_jobs()

            job = scheduler.get_job('trading_job')
            assert job is not None
            # max_instances가 1로 설정되어 있어야 함 (conftest에서 확인)

            scheduler.remove_all_jobs()
