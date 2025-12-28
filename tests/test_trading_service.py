"""
거래 서비스 테스트
"""
import pytest
from unittest.mock import MagicMock
from src.trading.service import TradingService
from src.api.upbit_client import UpbitClient


class TestTradingService:
    """TradingService 클래스 테스트"""
    
    def test_calculate_fee(self, mock_upbit_client):
        """수수료 계산 테스트"""
        service = TradingService(mock_upbit_client)
        
        # 비율 수수료가 최소 수수료보다 큰 경우
        fee1 = service.calculate_fee(10000000)  # 0.05% = 5000원
        assert fee1 == 5000
        
        # 비율 수수료가 최소 수수료보다 작은 경우
        fee2 = service.calculate_fee(1000000)  # 0.05% = 500원, 최소 5000원
        assert fee2 == 5000
    
    def test_calculate_available_buy_amount_insufficient(self, mock_upbit_client):
        """매수 가능 금액 계산 - 잔고 부족"""
        service = TradingService(mock_upbit_client)
        
        # 최소 필요 금액보다 적은 잔고
        result = service.calculate_available_buy_amount(5000)
        assert result == 0
    
    def test_calculate_available_buy_amount_sufficient(self, mock_upbit_client):
        """매수 가능 금액 계산 - 잔고 충분"""
        service = TradingService(mock_upbit_client)
        
        # 충분한 잔고
        balance = 1000000
        result = service.calculate_available_buy_amount(balance)
        
        assert result > 0
        assert result <= balance
        # 30% 매수 비율 적용
        expected_min = balance * 0.3 - (balance * 0.3 * 0.0005)
        assert result >= expected_min * 0.9  # 약간의 오차 허용
    
    @pytest.mark.unit
    def test_execute_buy_insufficient_balance(self, mock_upbit_client):
        """매수 실행 - 잔고 부족"""
        service = TradingService(mock_upbit_client)
        mock_upbit_client.get_balance.return_value = 1000
        
        result = service.execute_buy("KRW-ETH")
        
        assert result['success'] is False
        assert 'error' in result
    
    @pytest.mark.unit
    def test_execute_sell_no_coin(self, mock_upbit_client, capsys):
        """매도 실행 - 코인 없음 (에러 메시지 없이 정보 메시지 출력)"""
        service = TradingService(mock_upbit_client)
        mock_upbit_client.get_balance.return_value = 0
        
        result = service.execute_sell("KRW-ETH")
        
        assert result['success'] is False
        assert 'error' in result
        output = capsys.readouterr().out
        # 에러 메시지가 아닌 정보 메시지가 출력되어야 함
        assert "매도 실패" not in output
        assert "매도를 수행하지 않습니다" in output or "보유한" in output
    
    def test_execute_hold(self, mock_upbit_client):
        """보유 유지 테스트"""
        service = TradingService(mock_upbit_client)
        
        # 예외가 발생하지 않아야 함
        service.execute_hold()

