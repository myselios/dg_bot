"""
시장 데이터 수집
"""
import pyupbit
import pandas as pd
import requests
from typing import Optional, Dict
from ..config.settings import DataConfig
from ..utils.logger import Logger


class DataCollector:
    """시장 데이터 수집 클래스"""
    
    @staticmethod
    def get_chart_data(ticker: str) -> Optional[Dict[str, pd.DataFrame]]:
        """
        차트 데이터 수집
        
        Args:
            ticker: 거래 종목
            
        Returns:
            차트 데이터 딕셔너리 (day, minute60, minute15)
        """
        try:
            df_day = pyupbit.get_ohlcv(
                ticker, interval="day", count=DataConfig.DAY_CHART_COUNT
            )
            df_minute60 = pyupbit.get_ohlcv(
                ticker, interval="minute60", count=DataConfig.HOUR_CHART_COUNT
            )
            df_minute15 = pyupbit.get_ohlcv(
                ticker, interval="minute15", count=DataConfig.MINUTE15_CHART_COUNT
            )
            
            Logger.print_chart_stats(ticker, df_day)
            
            return {
                'day': df_day,
                'minute60': df_minute60,
                'minute15': df_minute15
            }
        except Exception as e:
            Logger.print_error(f"차트 데이터 조회 실패: {str(e)}")
            return None
    
    @staticmethod
    def get_btc_chart_data() -> Optional[Dict[str, pd.DataFrame]]:
        """
        BTC 차트 데이터 수집 (Phase 2)
        
        Returns:
            BTC 차트 데이터 딕셔너리 (day, minute60, minute15)
        """
        return DataCollector.get_chart_data("KRW-BTC")
    
    @staticmethod
    def get_chart_data_with_btc(ticker: str) -> Optional[Dict[str, Dict[str, pd.DataFrame]]]:
        """
        ETH + BTC 차트 데이터 동시 수집 (Phase 2)
        
        Args:
            ticker: 거래 종목 (예: KRW-ETH)
            
        Returns:
            {
                'eth': {'day': df, 'minute60': df, 'minute15': df},
                'btc': {'day': df, 'minute60': df, 'minute15': df}
            }
        """
        try:
            # ETH 데이터 수집
            eth_data = DataCollector.get_chart_data(ticker)
            if eth_data is None:
                Logger.print_error(f"{ticker} 데이터 조회 실패")
                return None
            
            # BTC 데이터 수집
            btc_data = DataCollector.get_btc_chart_data()
            if btc_data is None:
                Logger.print_error("BTC 데이터 조회 실패")
                return None
            
            return {
                'eth': eth_data,
                'btc': btc_data
            }
        except Exception as e:
            Logger.print_error(f"차트 데이터 조회 실패: {str(e)}")
            return None
    
    @staticmethod
    def get_orderbook(ticker: str) -> Optional[list]:
        """
        오더북 정보 조회
        
        Args:
            ticker: 거래 종목
            
        Returns:
            오더북 정보 리스트
        """
        try:
            orderbook = pyupbit.get_orderbook(ticker)
            Logger.print_orderbook(ticker, orderbook)
            return orderbook
        except Exception as e:
            Logger.print_error(f"오더북 조회 실패: {str(e)}")
            return None
    
    @staticmethod
    def get_orderbook_summary(orderbook: Optional[list], depth: int = None) -> Dict:
        """
        오더북 요약 정보 추출
        
        Args:
            orderbook: 오더북 데이터
            depth: 조회할 호가 깊이
            
        Returns:
            오더북 요약 딕셔너리
        """
        if depth is None:
            depth = DataConfig.ORDERBOOK_DEPTH
        
        if not orderbook:
            return {
                "ask_prices": [],
                "bid_prices": [],
                "ask_volumes": [],
                "bid_volumes": []
            }
        
        orderbook_units = orderbook[0]['orderbook_units'][:depth]
        
        return {
            "ask_prices": [unit['ask_price'] for unit in orderbook_units],
            "bid_prices": [unit['bid_price'] for unit in orderbook_units],
            "ask_volumes": [unit['ask_size'] for unit in orderbook_units],
            "bid_volumes": [unit['bid_size'] for unit in orderbook_units]
        }
    
    @staticmethod
    def get_fear_greed_index() -> Optional[Dict[str, any]]:
        """
        공포탐욕지수 (Fear & Greed Index) 조회
        
        Returns:
            공포탐욕지수 딕셔너리 (value, classification) 또는 None
        """
        try:
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('metadata', {}).get('error'):
                Logger.print_error(f"공포탐욕지수 API 에러: {data['metadata']['error']}")
                return None
            
            if not data.get('data') or len(data['data']) == 0:
                Logger.print_error("공포탐욕지수 데이터가 없습니다.")
                return None
            
            latest = data['data'][0]
            
            return {
                'value': int(latest['value']),
                'classification': latest['value_classification'],
                'timestamp': int(latest['timestamp'])
            }
        except requests.exceptions.RequestException as e:
            Logger.print_error(f"공포탐욕지수 조회 실패: {str(e)}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            Logger.print_error(f"공포탐욕지수 데이터 파싱 실패: {str(e)}")
            return None
        except Exception as e:
            Logger.print_error(f"공포탐욕지수 조회 중 예상치 못한 오류: {str(e)}")
            return None

