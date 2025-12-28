"""
포지션 서비스 테스트
"""
import pytest
from unittest.mock import Mock, patch
from src.position.service import PositionService
from src.api.interfaces import IExchangeClient
from src.exceptions import APIError


@pytest.fixture
def mock_exchange_client():
    """거래소 클라이언트 모킹"""
    mock = Mock(spec=IExchangeClient)
    return mock


@pytest.mark.unit
class TestPositionService:
    """PositionService 테스트"""
    
    def test_get_detailed_position_success(self, mock_exchange_client):
        """포지션 정보 조회 성공"""
        # Given
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "ETH",
                "balance": "1.5",
                "locked": "0.0",
                "avg_buy_price": "3000000.0"
            },
            {
                "currency": "KRW",
                "balance": "500000.0",
                "locked": "0.0",
                "avg_buy_price": "0.0"
            }
        ]
        mock_exchange_client.get_current_price.return_value = 3500000.0
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is not None
        assert result["currency"] == "ETH"
        assert result["amount"] == 1.5
        assert result["avg_buy_price"] == 3000000.0
        assert result["current_price"] == 3500000.0
        assert result["profit_loss"] == 750000.0  # (3500000 - 3000000) * 1.5
        # profit_rate = (3500000 - 3000000) / 3000000 * 100 = 16.67%
        assert result["profit_rate"] == pytest.approx(16.67, rel=0.1)  # 16.67%
    
    def test_get_detailed_position_no_position(self, mock_exchange_client):
        """포지션이 없는 경우"""
        # Given
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "KRW",
                "balance": "1000000.0",
                "locked": "0.0",
                "avg_buy_price": "0.0"
            }
        ]
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is None
    
    def test_get_detailed_position_zero_avg_buy_price(self, mock_exchange_client):
        """평균 매수가가 0인 경우 (공짜로 받은 코인)"""
        # Given
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "ETH",
                "balance": "1.0",
                "locked": "0.0",
                "avg_buy_price": "0.0"
            }
        ]
        mock_exchange_client.get_current_price.return_value = 3500000.0
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is not None
        assert result["avg_buy_price"] == 0
        assert result["profit_loss"] == 0
        assert result["profit_rate"] == 0
        assert result["current_value"] == 3500000.0
    
    def test_get_detailed_position_with_locked_balance(self, mock_exchange_client):
        """잠긴 잔고가 있는 경우"""
        # Given
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "ETH",
                "balance": "1.0",
                "locked": "0.5",  # 주문 중인 잔고
                "avg_buy_price": "3000000.0"
            }
        ]
        mock_exchange_client.get_current_price.return_value = 3500000.0
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is not None
        assert result["amount"] == 1.0
        assert result["locked"] == 0.5
        assert result["total_amount"] == 1.5  # balance + locked
    
    def test_get_detailed_position_api_error(self, mock_exchange_client):
        """API 오류 발생 시"""
        # Given
        mock_exchange_client.get_balances.side_effect = APIError("Upbit", reason="Network error")
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is None
    
    def test_get_detailed_position_no_current_price(self, mock_exchange_client):
        """현재가를 가져올 수 없는 경우"""
        # Given
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "ETH",
                "balance": "1.0",
                "locked": "0.0",
                "avg_buy_price": "3000000.0"
            }
        ]
        mock_exchange_client.get_current_price.return_value = None
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is None
    
    def test_get_detailed_position_profit_calculation(self, mock_exchange_client):
        """손익 계산 정확성 검증"""
        # Given
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "ETH",
                "balance": "2.0",
                "locked": "0.0",
                "avg_buy_price": "3000000.0"
            }
        ]
        mock_exchange_client.get_current_price.return_value = 3200000.0
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is not None
        # 총 매수가: 2.0 * 3000000 = 6,000,000
        # 현재 가치: 2.0 * 3200000 = 6,400,000
        # 손익: 400,000
        # 손익률: (400,000 / 6,000,000) * 100 = 6.67%
        assert result["total_cost"] == 6000000.0
        assert result["current_value"] == 6400000.0
        assert result["profit_loss"] == 400000.0
        assert result["profit_rate"] == pytest.approx(6.67, rel=0.1)
    
    def test_get_detailed_position_loss_calculation(self, mock_exchange_client):
        """손실 계산 정확성 검증"""
        # Given
        mock_exchange_client.get_balances.return_value = [
            {
                "currency": "ETH",
                "balance": "1.0",
                "locked": "0.0",
                "avg_buy_price": "3500000.0"
            }
        ]
        mock_exchange_client.get_current_price.return_value = 3000000.0
        
        service = PositionService(mock_exchange_client)
        
        # When
        result = service.get_detailed_position("KRW-ETH")
        
        # Then
        assert result is not None
        assert result["profit_loss"] == -500000.0  # 손실
        assert result["profit_rate"] == pytest.approx(-14.29, rel=0.1)  # -14.29%

