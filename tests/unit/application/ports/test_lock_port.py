"""
LockPort 테스트

TDD Red Phase - 실패하는 테스트 먼저 작성
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.application.ports.outbound.lock_port import LockPort, LOCK_IDS


class TestLockPortInterface:
    """LockPort 인터페이스 테스트"""

    def test_port_is_abstract(self):
        """Port는 추상 클래스여야 함"""
        with pytest.raises(TypeError):
            LockPort()

    def test_port_has_acquire_method(self):
        """acquire 메서드가 정의되어 있어야 함"""
        assert hasattr(LockPort, 'acquire')

    def test_port_has_release_method(self):
        """release 메서드가 정의되어 있어야 함"""
        assert hasattr(LockPort, 'release')

    def test_port_has_is_locked_method(self):
        """is_locked 메서드가 정의되어 있어야 함"""
        assert hasattr(LockPort, 'is_locked')

    def test_port_has_lock_context_manager(self):
        """lock context manager가 정의되어 있어야 함"""
        assert hasattr(LockPort, 'lock')


class TestLockIds:
    """Lock ID 상수 테스트"""

    def test_trading_cycle_lock_id_exists(self):
        """trading_cycle 락 ID가 정의되어 있어야 함"""
        assert "trading_cycle" in LOCK_IDS

    def test_position_management_lock_id_exists(self):
        """position_management 락 ID가 정의되어 있어야 함"""
        assert "position_management" in LOCK_IDS

    def test_lock_ids_are_unique(self):
        """락 ID들은 서로 달라야 함"""
        ids = list(LOCK_IDS.values())
        assert len(ids) == len(set(ids))


class TestInMemoryLockAdapter:
    """InMemory Lock Adapter 테스트 (단위 테스트용)"""

    @pytest.fixture
    def adapter(self):
        """테스트용 InMemory 어댑터"""
        from src.infrastructure.adapters.persistence.memory_lock_adapter import (
            InMemoryLockAdapter
        )
        return InMemoryLockAdapter()

    @pytest.mark.asyncio
    async def test_acquire_lock_returns_true_when_available(self, adapter):
        """사용 가능한 락 획득 시 True 반환"""
        result = await adapter.acquire("test_lock")
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_lock_returns_false_when_held(self, adapter):
        """이미 점유된 락 획득 시도 시 False 반환"""
        await adapter.acquire("test_lock")
        result = await adapter.acquire("test_lock")
        assert result is False

    @pytest.mark.asyncio
    async def test_release_lock_releases_lock(self, adapter):
        """release 후 락이 해제됨"""
        await adapter.acquire("test_lock")
        await adapter.release("test_lock")
        result = await adapter.acquire("test_lock")
        assert result is True

    @pytest.mark.asyncio
    async def test_context_manager_acquires_and_releases(self, adapter):
        """context manager가 락을 획득하고 해제함"""
        async with adapter.lock("test_lock"):
            # 락이 점유된 상태
            assert await adapter.is_locked("test_lock") is True

        # context 종료 후 락이 해제됨
        assert await adapter.is_locked("test_lock") is False

    @pytest.mark.asyncio
    async def test_context_manager_releases_on_exception(self, adapter):
        """예외 발생 시에도 락이 해제됨"""
        try:
            async with adapter.lock("test_lock"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # 예외 후에도 락이 해제됨
        assert await adapter.is_locked("test_lock") is False

    @pytest.mark.asyncio
    async def test_is_locked_returns_correct_state(self, adapter):
        """is_locked가 올바른 상태 반환"""
        assert await adapter.is_locked("test_lock") is False
        await adapter.acquire("test_lock")
        assert await adapter.is_locked("test_lock") is True
        await adapter.release("test_lock")
        assert await adapter.is_locked("test_lock") is False
