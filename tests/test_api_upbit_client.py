"""
Upbit API 클라이언트 테스트
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.api.upbit_client import UpbitClient
from src.api.interfaces import IExchangeClient
from src.exceptions import (
    APIError, AuthenticationError, RateLimitError,
    OrderExecutionError, DataCollectionError
)
from src.config.settings import APIConfig


@pytest.fixture
def mock_pyupbit():
    """pyupbit 모듈 모킹"""
    with patch('src.api.upbit_client.pyupbit') as mock:
        yield mock


@pytest.fixture
def mock_api_config():
    """API 설정 모킹"""
    with patch('src.api.upbit_client.APIConfig') as mock:
        mock.UPBIT_ACCESS_KEY = "test_access_key"
        mock.UPBIT_SECRET_KEY = "test_secret_key"
        mock.validate = Mock()
        yield mock


@pytest.mark.unit
class TestUpbitClient:
    """UpbitClient 테스트"""
    
    def test_upbit_client_implements_interface(self, mock_pyupbit, mock_api_config):
        """UpbitClient가 IExchangeClient 인터페이스를 구현하는지 확인"""
        mock_pyupbit.Upbit = Mock(return_value=Mock())
        client = UpbitClient()
        assert isinstance(client, IExchangeClient)
    
    def test_upbit_client_initialization_success(self, mock_pyupbit, mock_api_config):
        """UpbitClient 초기화 성공"""
        mock_client = Mock()
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        
        assert client.client == mock_client
        mock_api_config.validate.assert_called_once()
        mock_pyupbit.Upbit.assert_called_once_with(
            "test_access_key",
            "test_secret_key"
        )
    
    def test_upbit_client_initialization_failure(self, mock_pyupbit, mock_api_config):
        """UpbitClient 초기화 실패 (인증 오류)"""
        mock_api_config.validate.side_effect = Exception("Invalid credentials")
        
        with pytest.raises(AuthenticationError) as exc_info:
            UpbitClient()
        
        assert "인증 정보 설정 실패" in str(exc_info.value)
    
    def test_get_balances_success(self, mock_pyupbit, mock_api_config):
        """잔고 조회 성공"""
        mock_client = Mock()
        mock_client.get_balances.return_value = [
            {"currency": "KRW", "balance": "1000000"},
            {"currency": "ETH", "balance": "1.5"}
        ]
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        result = client.get_balances()
        
        assert len(result) == 2
        assert result[0]["currency"] == "KRW"
    
    def test_get_balances_rate_limit_error(self, mock_pyupbit, mock_api_config):
        """잔고 조회 시 레이트 리밋 오류"""
        mock_client = Mock()
        error = Exception("Rate limit exceeded")
        error.retry_after = 60
        mock_client.get_balances.side_effect = error
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        
        with pytest.raises(RateLimitError) as exc_info:
            client.get_balances()
        
        assert exc_info.value.retry_after == 60
    
    def test_get_balance_success(self, mock_pyupbit, mock_api_config):
        """특정 화폐 잔고 조회 성공"""
        mock_client = Mock()
        mock_client.get_balance.return_value = 1000000.0
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        result = client.get_balance("KRW")
        
        assert result == 1000000.0
    
    def test_get_balance_returns_zero_on_error(self, mock_pyupbit, mock_api_config):
        """잔고 조회 실패 시 0 반환"""
        mock_client = Mock()
        mock_client.get_balance.side_effect = Exception("Error")
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        result = client.get_balance("KRW")
        
        assert result == 0.0
    
    def test_get_current_price_success(self, mock_pyupbit, mock_api_config):
        """현재가 조회 성공"""
        mock_pyupbit.Upbit = Mock(return_value=Mock())
        mock_pyupbit.get_current_price.return_value = 3500000.0
        
        client = UpbitClient()
        result = client.get_current_price("KRW-ETH")
        
        assert result == 3500000.0
    
    def test_get_current_price_failure(self, mock_pyupbit, mock_api_config):
        """현재가 조회 실패"""
        mock_pyupbit.Upbit = Mock(return_value=Mock())
        mock_pyupbit.get_current_price.side_effect = Exception("Network error")
        
        client = UpbitClient()
        
        with pytest.raises(DataCollectionError) as exc_info:
            client.get_current_price("KRW-ETH")
        
        assert "현재가 조회 실패" in str(exc_info.value)
    
    def test_buy_market_order_success(self, mock_pyupbit, mock_api_config):
        """매수 주문 성공"""
        mock_client = Mock()
        mock_client.buy_market_order.return_value = {
            "uuid": "order-uuid-123",
            "market": "KRW-ETH",
            "side": "bid"
        }
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        result = client.buy_market_order("KRW-ETH", 100000)
        
        assert result["uuid"] == "order-uuid-123"
        mock_client.buy_market_order.assert_called_once_with("KRW-ETH", 100000)
    
    def test_buy_market_order_insufficient_funds(self, mock_pyupbit, mock_api_config):
        """매수 주문 실패 - 잔고 부족"""
        mock_client = Mock()
        error = Exception("insufficient funds")
        mock_client.buy_market_order.side_effect = error
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        
        with pytest.raises(OrderExecutionError) as exc_info:
            client.buy_market_order("KRW-ETH", 100000)
        
        assert exc_info.value.order_type == "buy"
        assert exc_info.value.ticker == "KRW-ETH"
        assert "잔고 부족" in exc_info.value.reason
    
    def test_sell_market_order_success(self, mock_pyupbit, mock_api_config):
        """매도 주문 성공"""
        mock_client = Mock()
        mock_client.sell_market_order.return_value = {
            "uuid": "order-uuid-456",
            "market": "KRW-ETH",
            "side": "ask"
        }
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        result = client.sell_market_order("KRW-ETH", 0.1)
        
        assert result["uuid"] == "order-uuid-456"
        mock_client.sell_market_order.assert_called_once_with("KRW-ETH", 0.1)
    
    def test_sell_market_order_insufficient_balance(self, mock_pyupbit, mock_api_config):
        """매도 주문 실패 - 보유량 부족"""
        mock_client = Mock()
        error = Exception("insufficient balance")
        mock_client.sell_market_order.side_effect = error
        mock_pyupbit.Upbit = Mock(return_value=mock_client)
        
        client = UpbitClient()
        
        with pytest.raises(OrderExecutionError) as exc_info:
            client.sell_market_order("KRW-ETH", 0.1)
        
        assert exc_info.value.order_type == "sell"
        assert "보유량 부족" in exc_info.value.reason

