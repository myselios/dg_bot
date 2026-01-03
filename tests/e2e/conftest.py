"""
E2E 테스트 공통 픽스처

실제 운용 흐름 검증을 위한 테스트 픽스처
Paper trading 모드 지원
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal


@pytest.fixture
def paper_trading_config():
    """Paper trading 설정"""
    return {
        "mode": "paper",
        "initial_balance": Decimal("1000000"),  # 100만원
        "max_position_size_pct": Decimal("0.30"),  # 30%
        "stop_loss_pct": Decimal("-0.05"),  # -5%
        "take_profit_pct": Decimal("0.10"),  # +10%
    }


@pytest.fixture
def mock_paper_exchange():
    """Paper trading용 거래소 Mock"""
    exchange = MagicMock()
    exchange.mode = "paper"
    exchange.balance = Decimal("1000000")
    exchange.positions = []

    async def mock_buy(ticker, amount):
        return {
            "success": True,
            "trade_id": f"paper-{ticker}-buy",
            "amount": amount,
        }

    async def mock_sell(ticker, volume):
        return {
            "success": True,
            "trade_id": f"paper-{ticker}-sell",
            "volume": volume,
        }

    exchange.buy = AsyncMock(side_effect=mock_buy)
    exchange.sell = AsyncMock(side_effect=mock_sell)
    exchange.get_balance = AsyncMock(return_value=Decimal("1000000"))

    return exchange
