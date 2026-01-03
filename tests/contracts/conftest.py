"""
Contracts 테스트 공통 픽스처

계약 테스트는 시스템의 핵심 보장을 검증합니다.
이 테스트들이 실패하면 거래를 즉시 중단해야 합니다.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal


@pytest.fixture
def mock_exchange_port():
    """거래소 포트 Mock"""
    port = MagicMock()
    port.get_balance = AsyncMock(return_value=Decimal("1000000"))
    port.execute_order = AsyncMock()
    return port


@pytest.fixture
def mock_idempotency_port():
    """Idempotency 포트 Mock"""
    port = MagicMock()
    port.check_key = AsyncMock(return_value=False)
    port.mark_key = AsyncMock()
    port.cleanup_expired = AsyncMock(return_value=0)
    return port


@pytest.fixture
def mock_lock_port():
    """Lock 포트 Mock"""
    port = MagicMock()
    port.acquire = AsyncMock(return_value=True)
    port.release = AsyncMock()
    port.is_locked = AsyncMock(return_value=False)
    return port


@pytest.fixture
def sample_trade_params():
    """샘플 거래 파라미터"""
    return {
        "ticker": "KRW-BTC",
        "action": "buy",
        "amount": Decimal("100000"),
        "price": Decimal("50000000"),
    }
