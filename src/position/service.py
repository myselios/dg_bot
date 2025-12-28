"""
포지션 정보 서비스
"""
from typing import Optional, Dict, Any
from ..api.interfaces import IExchangeClient
from ..utils.logger import Logger


class PositionService:
    """포지션 정보 관리 클래스"""
    
    def __init__(self, exchange_client: IExchangeClient):
        """
        포지션 서비스 초기화
        
        Args:
            exchange_client: 거래소 클라이언트 인터페이스 (의존성 역전 원칙 적용)
        """
        self.exchange = exchange_client
    
    def get_detailed_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        상세 포지션 정보 조회
        
        Args:
            ticker: 거래 종목 (예: "KRW-ETH")
            
        Returns:
            포지션 정보 딕셔너리 또는 None
        """
        try:
            balances = self.exchange.get_balances()
            if not balances:
                return None
            
            currency = ticker.split('-')[1]  # ETH
            
            for balance in balances:
                if balance['currency'] == currency:
                    amount = float(balance['balance'])
                    locked = float(balance['locked'])
                    avg_buy_price = float(balance['avg_buy_price'])
                    total_amount = amount + locked
                    
                    current_price = self.exchange.get_current_price(ticker)
                    
                    if current_price and avg_buy_price > 0:
                        current_value = total_amount * current_price
                        total_cost = total_amount * avg_buy_price
                        profit_loss = current_value - total_cost
                        profit_rate = (profit_loss / total_cost) * 100 if total_cost > 0 else 0
                        
                        return {
                            'currency': currency,
                            'amount': amount,
                            'locked': locked,
                            'total_amount': total_amount,
                            'avg_buy_price': avg_buy_price,
                            'current_price': current_price,
                            'current_value': current_value,
                            'total_cost': total_cost,
                            'profit_loss': profit_loss,
                            'profit_rate': profit_rate
                        }
                    elif current_price:
                        # 매수가가 0인 경우 (공짜로 받은 코인 등)
                        return {
                            'currency': currency,
                            'amount': amount,
                            'locked': locked,
                            'total_amount': total_amount,
                            'avg_buy_price': 0,
                            'current_price': current_price,
                            'current_value': total_amount * current_price,
                            'total_cost': 0,
                            'profit_loss': 0,
                            'profit_rate': 0
                        }
            
            return None
            
        except Exception as e:
            Logger.print_error(f"포지션 정보 조회 실패: {str(e)}")
            return None

