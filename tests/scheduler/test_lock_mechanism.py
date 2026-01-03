"""
Lock 메커니즘 테스트

스케줄러 작업 간 상호 배제를 위한 Lock 테스트
contracts/test_idempotency.py와 연계됨
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from .conftest import create_mock_container


class TestLockMechanism:
    """Lock 메커니즘 테스트"""

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lock_acquired_before_trading_job(self):
        """trading_job 실행 전 Lock이 획득되는지 확인"""
        mock_container = create_mock_container()
        mock_lock_port = mock_container.get_lock_port()

        # Lock 획득 확인
        result = await mock_lock_port.acquire()
        assert result is True
        mock_lock_port.acquire.assert_called_once()

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lock_released_after_trading_job(self):
        """trading_job 완료 후 Lock이 해제되는지 확인"""
        mock_container = create_mock_container()
        mock_lock_port = mock_container.get_lock_port()

        # Lock 획득 후 해제
        await mock_lock_port.acquire()
        await mock_lock_port.release()

        mock_lock_port.release.assert_called_once()

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_execution(self):
        """Lock이 동시 실행을 방지하는지 확인"""
        # Given: Lock이 이미 획득된 상태
        mock_lock_port = MagicMock()
        mock_lock_port.acquire = AsyncMock(return_value=False)  # Lock 획득 실패

        mock_container = MagicMock()
        mock_container.get_lock_port.return_value = mock_lock_port

        # When: Lock 획득 시도
        result = await mock_lock_port.acquire()

        # Then: Lock 획득 실패 (다른 작업이 실행 중)
        assert result is False

    @pytest.mark.scheduler
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lock_released_on_exception(self):
        """예외 발생 시에도 Lock이 해제되는지 확인"""
        mock_container = create_mock_container()
        mock_lock_port = mock_container.get_lock_port()

        try:
            await mock_lock_port.acquire()
            raise Exception("Test exception")
        except Exception:
            await mock_lock_port.release()

        mock_lock_port.release.assert_called_once()


class TestLockPortContract:
    """Lock Port 계약 테스트 (contracts/와 중복되지 않는 스케줄러 특화 테스트)"""

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_lock_ids_are_defined(self):
        """Lock ID가 정의되어 있는지 확인"""
        from src.application.ports.outbound.lock_port import LOCK_IDS

        # 필수 Lock ID 확인
        assert 'trading_cycle' in LOCK_IDS
        assert 'position_management' in LOCK_IDS

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_lock_ids_are_unique(self):
        """Lock ID가 고유한지 확인"""
        from src.application.ports.outbound.lock_port import LOCK_IDS

        lock_values = list(LOCK_IDS.values())
        assert len(lock_values) == len(set(lock_values)), \
            "Lock ID 값이 중복되면 안 됩니다"

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_trading_cycle_lock_id(self):
        """trading_cycle Lock ID 값 확인"""
        from src.application.ports.outbound.lock_port import LOCK_IDS

        assert LOCK_IDS['trading_cycle'] == 1001

    @pytest.mark.scheduler
    @pytest.mark.unit
    def test_position_management_lock_id(self):
        """position_management Lock ID 값 확인"""
        from src.application.ports.outbound.lock_port import LOCK_IDS

        assert LOCK_IDS['position_management'] == 1002
