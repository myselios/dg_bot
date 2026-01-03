"""
Idempotency 계약 테스트

계약: 동일한 캔들에 대해 동일한 주문은 한 번만 실행되어야 함

이 테스트가 실패하면:
- 중복 주문 발생 가능
- 거래 즉시 중단 필요
"""
import pytest
from datetime import datetime, timedelta

from src.application.ports.outbound.idempotency_port import (
    IdempotencyPort,
    make_idempotency_key
)


class TestIdempotencyContract:
    """Idempotency 핵심 계약"""

    # =========================================================================
    # CONTRACT 1: 동일 키는 중복 실행 방지
    # =========================================================================

    @pytest.mark.contract
    def test_same_key_prevents_duplicate_execution(self):
        """동일한 Idempotency 키는 중복 실행을 방지해야 함"""
        # Given: 동일한 파라미터
        ticker = "KRW-BTC"
        timeframe = "1h"
        candle_ts = 1704067200
        action = "buy"

        # When: 같은 파라미터로 키 생성
        key1 = make_idempotency_key(ticker, timeframe, candle_ts, action)
        key2 = make_idempotency_key(ticker, timeframe, candle_ts, action)

        # Then: 동일한 키 생성
        assert key1 == key2
        assert key1 == "KRW-BTC-1h-1704067200-buy"

    @pytest.mark.contract
    def test_different_candle_generates_different_key(self):
        """다른 캔들은 다른 키를 생성해야 함"""
        # Given: 다른 캔들 타임스탬프
        candle_ts_1 = 1704067200
        candle_ts_2 = 1704070800  # 1시간 후

        # When: 다른 캔들로 키 생성
        key1 = make_idempotency_key("KRW-BTC", "1h", candle_ts_1, "buy")
        key2 = make_idempotency_key("KRW-BTC", "1h", candle_ts_2, "buy")

        # Then: 다른 키 생성
        assert key1 != key2

    @pytest.mark.contract
    def test_different_action_generates_different_key(self):
        """다른 액션은 다른 키를 생성해야 함"""
        # Given: 동일 캔들, 다른 액션
        candle_ts = 1704067200

        # When: 다른 액션으로 키 생성
        buy_key = make_idempotency_key("KRW-BTC", "1h", candle_ts, "buy")
        sell_key = make_idempotency_key("KRW-BTC", "1h", candle_ts, "sell")

        # Then: 다른 키 생성
        assert buy_key != sell_key

    # =========================================================================
    # CONTRACT 2: Port 인터페이스 계약
    # =========================================================================

    @pytest.mark.contract
    def test_port_is_abstract(self):
        """IdempotencyPort는 추상 클래스여야 함"""
        with pytest.raises(TypeError):
            IdempotencyPort()

    @pytest.mark.contract
    def test_port_has_required_methods(self):
        """Port는 필수 메서드를 정의해야 함"""
        assert hasattr(IdempotencyPort, 'check_key')
        assert hasattr(IdempotencyPort, 'mark_key')
        assert hasattr(IdempotencyPort, 'cleanup_expired')


class TestIdempotencyAdapterContract:
    """Idempotency Adapter 계약 테스트"""

    @pytest.fixture
    def adapter(self):
        """InMemory Idempotency Adapter"""
        from src.infrastructure.adapters.persistence.memory_idempotency_adapter import (
            InMemoryIdempotencyAdapter
        )
        return InMemoryIdempotencyAdapter()

    # =========================================================================
    # CONTRACT 3: 새 키는 실행 허용
    # =========================================================================

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_new_key_allows_execution(self, adapter):
        """새로운 키는 실행을 허용해야 함 (False 반환)"""
        # Given: 새로운 키
        key = "new-unique-key-12345"

        # When: 키 확인
        exists = await adapter.check_key(key)

        # Then: 존재하지 않음 = 실행 허용
        assert exists is False

    # =========================================================================
    # CONTRACT 4: 마킹된 키는 실행 차단
    # =========================================================================

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_marked_key_blocks_execution(self, adapter):
        """마킹된 키는 실행을 차단해야 함 (True 반환)"""
        # Given: 마킹된 키
        key = "marked-key-12345"
        await adapter.mark_key(key)

        # When: 키 확인
        exists = await adapter.check_key(key)

        # Then: 존재함 = 실행 차단
        assert exists is True

    # =========================================================================
    # CONTRACT 5: 만료된 키는 실행 허용
    # =========================================================================

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_expired_key_allows_execution(self, adapter):
        """만료된 키는 실행을 허용해야 함"""
        # Given: 즉시 만료되는 키 (TTL=0)
        key = "expired-key-12345"
        await adapter.mark_key(key, ttl_hours=0)

        # When: 키 확인
        exists = await adapter.check_key(key)

        # Then: 만료됨 = 실행 허용
        assert exists is False

    # =========================================================================
    # CONTRACT 6: 클린업은 만료된 키만 제거
    # =========================================================================

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_cleanup_removes_only_expired_keys(self, adapter):
        """클린업은 만료된 키만 제거해야 함"""
        # Given: 만료된 키와 유효한 키
        await adapter.mark_key("expired-key", ttl_hours=0)
        await adapter.mark_key("valid-key", ttl_hours=24)

        # When: 클린업 실행
        removed = await adapter.cleanup_expired()

        # Then: 만료된 키만 제거
        assert removed >= 1
        assert await adapter.check_key("expired-key") is False
        assert await adapter.check_key("valid-key") is True
