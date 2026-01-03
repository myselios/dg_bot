"""
스케줄러 설정 테스트

스케줄러의 기본 설정이 올바르게 되어 있는지 확인
"""
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.app.core.scheduler import scheduler


class TestSchedulerConfiguration:
    """스케줄러 설정 테스트"""

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_scheduler_instance_exists(self):
        """스케줄러 인스턴스가 생성되어 있는지 확인"""
        assert scheduler is not None
        assert isinstance(scheduler, AsyncIOScheduler)

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_scheduler_timezone(self):
        """스케줄러 타임존이 Asia/Seoul로 설정되어 있는지 확인"""
        assert str(scheduler.timezone) == "Asia/Seoul"

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_scheduler_job_defaults(self):
        """스케줄러 기본 설정 확인"""
        job_defaults = scheduler._job_defaults
        assert job_defaults.get('coalesce') is True
        assert job_defaults.get('max_instances') == 1
        assert job_defaults.get('misfire_grace_time') == 60

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_max_instances_is_one(self):
        """동시 실행 방지를 위해 max_instances가 1인지 확인"""
        job_defaults = scheduler._job_defaults
        assert job_defaults.get('max_instances') == 1, \
            "동시 실행 방지를 위해 max_instances는 1이어야 합니다"

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_coalesce_enabled(self):
        """누적된 작업 병합이 활성화되어 있는지 확인"""
        job_defaults = scheduler._job_defaults
        assert job_defaults.get('coalesce') is True, \
            "누적된 작업 병합을 위해 coalesce는 True여야 합니다"
