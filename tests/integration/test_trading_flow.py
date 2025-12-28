"""
거래 플로우 통합 테스트
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.api.interfaces import IExchangeClient
from src.trading.service import TradingService
from src.data.collector import DataCollector
from src.ai.service import AIService
from src.position.service import PositionService
from src.config.settings import TradingConfig


@pytest.fixture
def mock_exchange_client():
    """거래소 클라이언트 모킹"""
    mock = Mock(spec=IExchangeClient)
    mock.get_balance.return_value = 1000000.0  # KRW 잔고
    mock.get_current_price.return_value = 3500000.0  # ETH 현재가
    mock.get_balances.return_value = [
        {"currency": "KRW", "balance": "1000000.0"},
        {"currency": "ETH", "balance": "0.0"}
    ]
    return mock


@pytest.fixture
def trading_service(mock_exchange_client):
    """TradingService 인스턴스"""
    return TradingService(mock_exchange_client)


@pytest.mark.integration
class TestTradingFlow:
    """거래 플로우 통합 테스트"""
    
    def test_complete_buy_flow(self, trading_service, mock_exchange_client):
        """전체 매수 플로우 테스트"""
        # Given
        ticker = TradingConfig.TICKER
        mock_exchange_client.buy_market_order.return_value = {
            "uuid": "test-uuid-123",
            "market": ticker,
            "side": "bid"
        }
        
        # When
        result = trading_service.execute_buy(ticker)
        
        # Then
        assert result['success'] is True
        assert 'trade_id' in result
        mock_exchange_client.get_balance.assert_called_with("KRW")
        mock_exchange_client.buy_market_order.assert_called_once()
    
    def test_complete_sell_flow(self, trading_service, mock_exchange_client):
        """전체 매도 플로우 테스트"""
        # Given
        ticker = TradingConfig.TICKER
        mock_exchange_client.get_balance.return_value = 0.5  # ETH 잔고
        mock_exchange_client.sell_market_order.return_value = {
            "uuid": "test-uuid-456",
            "market": ticker,
            "side": "ask"
        }
        
        # When
        result = trading_service.execute_sell(ticker)
        
        # Then
        assert result['success'] is True
        assert 'trade_id' in result
        mock_exchange_client.sell_market_order.assert_called_once()
    
    def test_trading_service_with_position_service(self, mock_exchange_client):
        """TradingService와 PositionService 연동 테스트"""
        # Given
        trading_service = TradingService(mock_exchange_client)
        position_service = PositionService(mock_exchange_client)
        
        # 매수 실행
        mock_exchange_client.buy_market_order.return_value = {"uuid": "buy-123"}
        buy_result = trading_service.execute_buy("KRW-ETH")
        
        # 포지션 조회
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "ETH",
                "balance": "0.1",
                "locked": "0.0",
                "avg_buy_price": "3500000.0"
            }
        ]
        position = position_service.get_detailed_position("KRW-ETH")
        
        # Then
        assert buy_result['success'] is True
        assert 'trade_id' in buy_result
        assert position is not None
        assert position["currency"] == "ETH"
    
    def test_insufficient_funds_flow(self, trading_service, mock_exchange_client):
        """잔고 부족 플로우 테스트"""
        # Given
        mock_exchange_client.get_balance.return_value = 1000.0  # 매우 적은 잔고
        
        # When
        result = trading_service.execute_buy("KRW-ETH")
        
        # Then
        assert result['success'] is False
        assert 'error' in result
        mock_exchange_client.buy_market_order.assert_not_called()
    
    def test_no_position_sell_flow(self, trading_service, mock_exchange_client):
        """보유량 없을 때 매도 플로우 테스트"""
        # Given
        mock_exchange_client.get_balance.return_value = 0.0  # ETH 잔고 없음
        
        # When
        result = trading_service.execute_sell("KRW-ETH")
        
        # Then
        assert result['success'] is False
        assert 'error' in result
        mock_exchange_client.sell_market_order.assert_not_called()


