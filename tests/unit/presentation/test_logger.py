"""
로거 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from src.utils.logger import Logger


class TestLogger:
    """Logger 클래스 테스트"""
    
    @pytest.mark.unit
    def test_print_investment_status_with_krw_only(self, mock_upbit_client, capsys):
        """투자 상태 출력 - 원화만 보유"""
        balances = [
            {
                'currency': 'KRW',
                'balance': '1000000',
                'locked': '0',
                'avg_buy_price': '0'
            }
        ]
        
        Logger.print_investment_status(balances, mock_upbit_client)
        
        output = capsys.readouterr().out
        assert '원화 (KRW)' in output
        assert '1,000,000' in output
        # get_current_price가 호출되지 않아야 함
        mock_upbit_client.get_current_price.assert_not_called()
    
    @pytest.mark.unit
    def test_print_investment_status_with_target_currency_filter(self, mock_upbit_client, capsys):
        """투자 상태 출력 - 특정 통화만 필터링"""
        balances = [
            {
                'currency': 'KRW',
                'balance': '1000000',
                'locked': '0',
                'avg_buy_price': '0'
            },
            {
                'currency': 'ETH',
                'balance': '1.5',
                'locked': '0.5',
                'avg_buy_price': '2000000'
            },
            {
                'currency': 'BTC',
                'balance': '0.1',
                'locked': '0',
                'avg_buy_price': '50000000'
            }
        ]
        
        mock_upbit_client.get_current_price.return_value = 2500000.0
        
        # ETH만 필터링
        Logger.print_investment_status(balances, mock_upbit_client, target_currency='ETH')
        
        output = capsys.readouterr().out
        assert '원화 (KRW)' in output
        assert 'ETH' in output
        assert 'BTC' not in output  # BTC는 표시되지 않아야 함
        # ETH에 대해서만 get_current_price 호출
        assert mock_upbit_client.get_current_price.call_count == 1
        mock_upbit_client.get_current_price.assert_called_with('KRW-ETH')
    
    @pytest.mark.unit
    def test_print_investment_status_with_coin(self, mock_upbit_client, capsys):
        """투자 상태 출력 - 코인 보유"""
        balances = [
            {
                'currency': 'KRW',
                'balance': '1000000',
                'locked': '0',
                'avg_buy_price': '0'
            },
            {
                'currency': 'ETH',
                'balance': '1.5',
                'locked': '0.5',
                'avg_buy_price': '2000000'
            }
        ]
        
        # upbit_client.get_current_price를 모킹
        mock_upbit_client.get_current_price.return_value = 2500000.0
        
        Logger.print_investment_status(balances, mock_upbit_client)
        
        output = capsys.readouterr().out
        assert 'ETH' in output
        assert '2,000,000' in output  # 평균 매수가
        assert '2,500,000' in output  # 현재가
        # upbit_client.get_current_price가 올바른 ticker로 호출되어야 함
        mock_upbit_client.get_current_price.assert_called_once_with('KRW-ETH')
    
    @pytest.mark.unit
    def test_print_investment_status_with_price_error(self, mock_upbit_client, capsys):
        """투자 상태 출력 - 가격 조회 실패"""
        balances = [
            {
                'currency': 'ETH',
                'balance': '1.0',
                'locked': '0',
                'avg_buy_price': '2000000'
            }
        ]
        
        # 가격 조회 실패 (None 반환)
        mock_upbit_client.get_current_price.return_value = None
        
        # 에러 없이 실행되어야 함
        Logger.print_investment_status(balances, mock_upbit_client)
        
        output = capsys.readouterr().out
        assert 'ETH' in output
        # 현재가가 None이면 평가금액 계산이 안 되므로 총 평가금액에 포함되지 않음
    
    @pytest.mark.unit
    def test_print_investment_status_calculates_profit_loss(self, mock_upbit_client, capsys):
        """투자 상태 출력 - 손익 계산"""
        balances = [
            {
                'currency': 'ETH',
                'balance': '1.0',
                'locked': '0',
                'avg_buy_price': '2000000'  # 평균 매수가
            }
        ]
        
        # 현재가가 평균 매수가보다 높음 (수익)
        mock_upbit_client.get_current_price.return_value = 2500000.0
        
        Logger.print_investment_status(balances, mock_upbit_client)
        
        output = capsys.readouterr().out
        assert '손익' in output
        # 수익이 발생해야 함 (2500000 - 2000000 = 500000)
        assert '+25.00%' in output or '+25.0%' in output or '25.00' in output

