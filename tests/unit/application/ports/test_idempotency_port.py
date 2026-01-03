"""
IdempotencyPort 테스트

TDD Red Phase - 실패하는 테스트 먼저 작성
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.application.ports.outbound.idempotency_port import IdempotencyPort


class TestIdempotencyPortInterface:
    """IdempotencyPort 인터페이스 테스트"""

    def test_port_is_abstract(self):
        """Port는 추상 클래스여야 함"""
        with pytest.raises(TypeError):
            IdempotencyPort()

    def test_port_has_check_key_method(self):
        """check_key 메서드가 정의되어 있어야 함"""
        assert hasattr(IdempotencyPort, 'check_key')

    def test_port_has_mark_key_method(self):
        """mark_key 메서드가 정의되어 있어야 함"""
        assert hasattr(IdempotencyPort, 'mark_key')

    def test_port_has_cleanup_expired_method(self):
        """cleanup_expired 메서드가 정의되어 있어야 함"""
        assert hasattr(IdempotencyPort, 'cleanup_expired')


class TestIdempotencyKeyHelper:
    """Idempotency 키 생성 헬퍼 테스트"""

    def test_make_idempotency_key_format(self):
        """키 형식이 올바른지 확인"""
        from src.application.ports.outbound.idempotency_port import make_idempotency_key

        key = make_idempotency_key(
            ticker="KRW-BTC",
            timeframe="1h",
            candle_ts=1704067200,
            action="buy"
        )

        assert key == "KRW-BTC-1h-1704067200-buy"

    def test_make_idempotency_key_different_actions(self):
        """다른 액션은 다른 키를 생성해야 함"""
        from src.application.ports.outbound.idempotency_port import make_idempotency_key

        buy_key = make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")
        sell_key = make_idempotency_key("KRW-BTC", "1h", 1704067200, "sell")

        assert buy_key != sell_key

    def test_make_idempotency_key_different_candles(self):
        """다른 캔들은 다른 키를 생성해야 함"""
        from src.application.ports.outbound.idempotency_port import make_idempotency_key

        key1 = make_idempotency_key("KRW-BTC", "1h", 1704067200, "buy")
        key2 = make_idempotency_key("KRW-BTC", "1h", 1704070800, "buy")

        assert key1 != key2


class TestInMemoryIdempotencyAdapter:
    """InMemory Idempotency Adapter 테스트 (단위 테스트용)"""

    @pytest.fixture
    def adapter(self):
        """테스트용 InMemory 어댑터"""
        from src.infrastructure.adapters.persistence.memory_idempotency_adapter import (
            InMemoryIdempotencyAdapter
        )
        return InMemoryIdempotencyAdapter()

    @pytest.mark.asyncio
    async def test_check_key_not_exists_returns_false(self, adapter):
        """존재하지 않는 키는 False 반환"""
        result = await adapter.check_key("non-existent-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_key_creates_record(self, adapter):
        """mark_key 후 키가 존재해야 함"""
        await adapter.mark_key("test-key")
        result = await adapter.check_key("test-key")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_key_exists_returns_true(self, adapter):
        """존재하는 키는 True 반환"""
        await adapter.mark_key("existing-key")
        result = await adapter.check_key("existing-key")
        assert result is True

    @pytest.mark.asyncio
    async def test_expired_key_returns_false(self, adapter):
        """만료된 키는 False 반환"""
        # TTL 0시간으로 설정하여 즉시 만료
        await adapter.mark_key("expired-key", ttl_hours=0)
        result = await adapter.check_key("expired-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_keys(self, adapter):
        """cleanup_expired가 만료된 키를 제거"""
        # 만료된 키 생성
        await adapter.mark_key("expired-key", ttl_hours=0)
        # 유효한 키 생성
        await adapter.mark_key("valid-key", ttl_hours=24)

        # 클린업 실행
        removed = await adapter.cleanup_expired()

        # 만료된 키는 제거되고 유효한 키는 유지
        assert removed >= 1
        assert await adapter.check_key("expired-key") is False
        assert await adapter.check_key("valid-key") is True
