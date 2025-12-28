"""
Upbit API로 과거 데이터 수집
- 장점: 무료, 인증 불필요, 신뢰할 수 있는 데이터
- 단점: 한 번에 최대 200개 캔들만 조회 가능 (페이지네이션 필요)
"""
import pyupbit
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import Optional
from pathlib import Path


class UpbitDataCollector:
    """Upbit 과거 데이터 수집기"""
    
    @staticmethod
    def get_historical_data(
        ticker: str,
        interval: str = 'day',
        days: int = 365,
        to_time: Optional[datetime] = None,
        start_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        과거 데이터 수집 (pagination 지원)
        
        Args:
            ticker: 종목 (예: 'KRW-BTC')
            interval: 'minute1', 'minute3', 'minute5', 'minute10', 
                     'minute15', 'minute30', 'minute60', 'minute240',
                     'day', 'week', 'month'
            days: 수집할 일수
            to_time: 종료 시점 (None이면 현재)
            start_time: 시작 시점 (None이면 to_time에서 days만큼 역산)
            
        Returns:
            DataFrame with columns: [open, high, low, close, volume, value]
        """
        
        all_data = []
        count = 200  # Upbit API 한 번에 최대 200개
        
        # 시작 시간 계산
        if start_time is None:
            if to_time is None:
                to_time = datetime.now()
            start_time = to_time - timedelta(days=days)
        
        # 필요한 반복 횟수 계산 (여유있게)
        if interval == 'day':
            max_candles = days
            iterations = max(10, (max_candles + count - 1) // count)
        elif interval == 'minute60':
            max_candles = days * 24
            iterations = max(10, (max_candles + count - 1) // count)
        elif interval == 'minute15':
            max_candles = days * 24 * 4
            iterations = max(10, (max_candles + count - 1) // count)
        elif interval == 'minute240':
            max_candles = days * 6
            iterations = max(10, (max_candles + count - 1) // count)
        else:
            max_candles = days * 24 * 60
            iterations = max(10, (max_candles + count - 1) // count)
        
        current_to_time = to_time
        collected_count = 0
        
        for i in range(iterations):
            try:
                if current_to_time is None:
                    df = pyupbit.get_ohlcv(
                        ticker, 
                        interval=interval, 
                        count=count
                    )
                else:
                    # to 파라미터는 문자열 형식 필요 (날짜만)
                    to_str = current_to_time.strftime("%Y%m%d")
                    df = pyupbit.get_ohlcv(
                        ticker,
                        interval=interval,
                        count=count,
                        to=to_str
                    )
                
                if df is None or len(df) == 0:
                    print(f"  더 이상 데이터가 없습니다.")
                    break
                
                # 시작 시간 이전 데이터는 제외
                if start_time and len(df) > 0:
                    df = df[df.index >= start_time]
                    if df.empty:
                        print(f"  시작 시간({start_time})에 도달했습니다.")
                        break
                
                all_data.append(df)
                collected_count += len(df)
                
                # 다음 페이지를 위한 시간 설정 (가장 오래된 데이터의 이전 시점)
                oldest_time = df.index[0]
                
                # interval에 따라 적절한 시간 간격 설정
                if interval == 'day':
                    current_to_time = oldest_time - timedelta(days=1)
                elif interval == 'minute60':
                    current_to_time = oldest_time - timedelta(hours=1)
                elif interval == 'minute15':
                    current_to_time = oldest_time - timedelta(minutes=15)
                elif interval == 'minute240':
                    current_to_time = oldest_time - timedelta(hours=4)
                else:
                    current_to_time = oldest_time - timedelta(minutes=1)
                
                print(f"  페이지 {i+1}/{iterations}: {len(df)}개 수집 (총 {collected_count}개) - 최신: {df.index[-1]}, 최초: {oldest_time}")
                
                # 시작 시간에 도달했는지 확인
                if start_time and oldest_time <= start_time:
                    print(f"  시작 시간({start_time})에 도달했습니다.")
                    break
                
                # API 레이트 리밋 방지
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  데이터 수집 오류: {e}")
                time.sleep(1)
                continue
        
        if not all_data:
            return pd.DataFrame()
        
        # 모든 데이터 합치기
        result = pd.concat(all_data)
        result = result.sort_index()
        result = result[~result.index.duplicated(keep='first')]
        
        # 시작/종료 시간으로 필터링
        if start_time:
            result = result[result.index >= start_time]
        if to_time:
            result = result[result.index <= to_time]
        
        return result
    
    @staticmethod
    def save_to_csv(df: pd.DataFrame, filename: str):
        """CSV 파일로 저장"""
        filepath = Path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filename)
        print(f"Data saved to {filename}")
    
    @staticmethod
    def load_from_csv(filename: str) -> pd.DataFrame:
        """CSV 파일에서 로드"""
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        return df

