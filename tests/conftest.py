"""
pytest 공통 설정 및 픽스처
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock
from src.api.upbit_client import UpbitClient


@pytest.fixture
def mock_upbit_client():
    """Upbit 클라이언트 Mock"""
    client = MagicMock(spec=UpbitClient)
    return client


@pytest.fixture
def sample_chart_data():
    """샘플 차트 데이터"""
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'open': [100 + i for i in range(30)],
        'high': [105 + i for i in range(30)],
        'low': [95 + i for i in range(30)],
        'close': [102 + i for i in range(30)],
        'volume': [1000 + i * 10 for i in range(30)]
    }, index=dates)


@pytest.fixture
def sample_orderbook():
    """샘플 오더북 데이터"""
    return [{
        'orderbook_units': [
            {
                'ask_price': 105.0,
                'bid_price': 100.0,
                'ask_size': 10.0,
                'bid_size': 10.0
            },
            {
                'ask_price': 106.0,
                'bid_price': 99.0,
                'ask_size': 5.0,
                'bid_size': 5.0
            },
            {
                'ask_price': 107.0,
                'bid_price': 98.0,
                'ask_size': 3.0,
                'bid_size': 3.0
            },
            {
                'ask_price': 108.0,
                'bid_price': 97.0,
                'ask_size': 2.0,
                'bid_size': 2.0
            },
            {
                'ask_price': 109.0,
                'bid_price': 96.0,
                'ask_size': 1.0,
                'bid_size': 1.0
            }
        ]
    }]

