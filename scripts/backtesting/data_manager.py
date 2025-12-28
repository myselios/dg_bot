"""
백테스팅을 위한 종합 데이터 수집 시스템
"""
import os
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
from datetime import datetime, timedelta
import time
import pyupbit
from .data_collector import UpbitDataCollector


class BacktestDataManager:
    """백테스팅 데이터 관리자"""
    
    def __init__(self, data_dir: str = 'backtest_data'):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 타임프레임별 디렉토리
        self.daily_dir = self.data_dir / 'daily'
        self.hourly_dir = self.data_dir / 'hourly'
        self.minute_dir = self.data_dir / 'minute'
        
        for directory in [self.daily_dir, self.hourly_dir, self.minute_dir]:
            directory.mkdir(exist_ok=True)
    
    def collect_and_cache(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime = None,
        force_update: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        데이터 수집 및 캐싱
        
        Args:
            ticker: 종목 (예: 'KRW-BTC')
            start_date: 시작 날짜
            end_date: 종료 날짜 (None이면 현재)
            force_update: 강제 업데이트 여부
            
        Returns:
            {'day': df, 'minute60': df, 'minute15': df}
        """
        
        if end_date is None:
            end_date = datetime.now()
        
        days = (end_date - start_date).days
        
        result = {}
        
        # 1. 일봉 데이터
        daily_file = self.daily_dir / f"{ticker}_{start_date.date()}_{end_date.date()}.csv"
        if daily_file.exists() and not force_update:
            print(f"Loading cached daily data: {daily_file}")
            result['day'] = pd.read_csv(daily_file, index_col=0, parse_dates=True)
        else:
            print(f"Collecting daily data for {ticker}...")
            result['day'] = UpbitDataCollector.get_historical_data(
                ticker=ticker,
                interval='day',
                days=days,
                to_time=end_date
            )
            if not result['day'].empty:
                result['day'].to_csv(daily_file)
                print(f"Saved to {daily_file}")
        
        # 2. 시간봉 데이터
        hourly_file = self.hourly_dir / f"{ticker}_{start_date.date()}_{end_date.date()}.csv"
        if hourly_file.exists() and not force_update:
            print(f"Loading cached hourly data: {hourly_file}")
            result['minute60'] = pd.read_csv(hourly_file, index_col=0, parse_dates=True)
        else:
            print(f"Collecting hourly data for {ticker}...")
            result['minute60'] = UpbitDataCollector.get_historical_data(
                ticker=ticker,
                interval='minute60',
                days=min(days, 30),  # 시간봉은 최대 30일
                to_time=end_date
            )
            if not result['minute60'].empty:
                result['minute60'].to_csv(hourly_file)
                print(f"Saved to {hourly_file}")
        
        # 3. 15분봉 데이터
        min15_file = self.minute_dir / f"{ticker}_15min_{start_date.date()}_{end_date.date()}.csv"
        if min15_file.exists() and not force_update:
            print(f"Loading cached 15min data: {min15_file}")
            result['minute15'] = pd.read_csv(min15_file, index_col=0, parse_dates=True)
        else:
            print(f"Collecting 15min data for {ticker}...")
            result['minute15'] = UpbitDataCollector.get_historical_data(
                ticker=ticker,
                interval='minute15',
                days=min(days, 7),  # 15분봉은 최대 7일
                to_time=end_date
            )
            if not result['minute15'].empty:
                result['minute15'].to_csv(min15_file)
                print(f"Saved to {min15_file}")
        
        return result
    
    def get_available_tickers(self) -> list:
        """사용 가능한 종목 목록"""
        return pyupbit.get_tickers(fiat="KRW")
    
    def collect_multiple_tickers(
        self,
        tickers: list,
        start_date: datetime,
        end_date: datetime = None,
        force_update: bool = False
    ):
        """여러 종목 데이터 일괄 수집"""
        
        for ticker in tickers:
            try:
                print(f"\n{'='*60}")
                print(f"Collecting data for {ticker}")
                print(f"{'='*60}")
                
                self.collect_and_cache(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    force_update=force_update
                )
                
                # API 레이트 리밋 방지
                time.sleep(1)
                
            except Exception as e:
                print(f"Error collecting {ticker}: {e}")
                import traceback
                traceback.print_exc()
                continue

