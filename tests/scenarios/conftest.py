"""
Scenarios 테스트 공통 픽스처

시나리오 테스트는 트레이더 관점의 핵심 비즈니스 흐름을 검증합니다.
Given-When-Then 패턴을 엄격히 따릅니다.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal
from datetime import datetime

from src.domain.value_objects.money import Money
from src.domain.value_objects.percentage import Percentage


@pytest.fixture
def mock_market_data():
    """시장 데이터 Mock"""
    return {
        "ticker": "KRW-BTC",
        "current_price": Decimal("50000000"),
        "volume_24h": Decimal("1000000000"),
        "change_24h": Percentage(Decimal("0.02")),  # +2%
    }


@pytest.fixture
def mock_ohlcv_data():
    """OHLCV 데이터 Mock"""
    import pandas as pd
    dates = pd.date_range("2024-01-01", periods=100, freq="h")
    return pd.DataFrame({
        "open": [50000000 + i * 10000 for i in range(100)],
        "high": [50100000 + i * 10000 for i in range(100)],
        "low": [49900000 + i * 10000 for i in range(100)],
        "close": [50050000 + i * 10000 for i in range(100)],
        "volume": [100 + i for i in range(100)],
    }, index=dates)


@pytest.fixture
def mock_ai_decision_buy():
    """AI 매수 결정 Mock"""
    return {
        "decision": "buy",
        "confidence": "high",
        "reason": "강한 상승 추세 감지",
        "target_price": Decimal("55000000"),
        "stop_loss": Decimal("47500000"),
    }


@pytest.fixture
def mock_ai_decision_sell():
    """AI 매도 결정 Mock"""
    return {
        "decision": "sell",
        "confidence": "high",
        "reason": "익절 목표 도달",
        "exit_price": Decimal("55000000"),
    }


@pytest.fixture
def mock_ai_decision_hold():
    """AI 홀드 결정 Mock"""
    return {
        "decision": "hold",
        "confidence": "medium",
        "reason": "시장 불확실성 높음",
    }


@pytest.fixture
def mock_portfolio_status():
    """포트폴리오 상태 Mock"""
    return {
        "total_value": Money.krw(1000000),
        "available_balance": Money.krw(700000),
        "positions": [],
        "daily_pnl": Money.krw(0),
    }


@pytest.fixture
def mock_exchange_port():
    """거래소 포트 Mock"""
    port = MagicMock()
    port.get_balance = AsyncMock(return_value=Money.krw(700000))
    port.get_current_price = AsyncMock(return_value=Money.krw(50000000))
    port.execute_buy = AsyncMock(return_value={"success": True, "trade_id": "test-123"})
    port.execute_sell = AsyncMock(return_value={"success": True, "trade_id": "test-456"})
    return port


@pytest.fixture
def mock_ai_port():
    """AI 포트 Mock"""
    port = MagicMock()
    port.analyze = AsyncMock()
    return port


@pytest.fixture
def mock_data_port():
    """데이터 포트 Mock"""
    port = MagicMock()
    port.get_ohlcv = AsyncMock()
    port.get_orderbook = AsyncMock()
    return port
