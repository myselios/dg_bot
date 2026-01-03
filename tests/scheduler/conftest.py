"""
Scheduler 테스트 공통 픽스처

스케줄러 테스트에서 사용하는 공통 Mock 객체와 헬퍼 함수
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


def create_mock_orchestrator(result):
    """TradingOrchestrator Mock 생성 헬퍼"""
    mock_orchestrator = MagicMock()
    mock_orchestrator.execute_trading_cycle = AsyncMock(return_value=result)
    mock_orchestrator.set_on_backtest_complete = MagicMock()
    return mock_orchestrator


def create_mock_container():
    """Container Mock 생성 헬퍼 (Lock/Idempotency 포함)"""
    mock_lock_port = MagicMock()
    mock_lock_port.acquire = AsyncMock(return_value=True)
    mock_lock_port.release = AsyncMock()

    mock_container = MagicMock()
    mock_container.get_lock_port.return_value = mock_lock_port
    return mock_container


async def create_mock_db():
    """Mock DB 세션 생성 (async generator)"""
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.rollback = AsyncMock()
    yield mock_db


@pytest.fixture
def mock_success_result():
    """성공적인 매수 거래 결과"""
    return {
        'status': 'success',
        'decision': 'buy',
        'confidence': 'high',
        'reason': 'Test reason',
        'price': 50000000,
        'amount': 0.001,
        'total': 50000,
        'fee': 25,
        'trade_id': 'test-trade-123',
        'trade_success': True
    }


@pytest.fixture
def mock_hold_result():
    """Hold 결정 결과"""
    return {
        'status': 'success',
        'decision': 'hold',
        'confidence': 'medium',
        'reason': 'Market is stable'
    }


@pytest.fixture
def mock_failure_result():
    """실패 결과"""
    return {
        'status': 'failed',
        'error': 'Network timeout'
    }


@pytest.fixture
def mock_orchestrator(mock_success_result):
    """기본 TradingOrchestrator Mock"""
    return create_mock_orchestrator(mock_success_result)


@pytest.fixture
def mock_container():
    """기본 Container Mock"""
    return create_mock_container()
