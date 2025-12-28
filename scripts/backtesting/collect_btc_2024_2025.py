"""
Upbit 비트코인 데이터 수집 스크립트
2024, 2025년 일봉 데이터를 월별로 수집하고 저장합니다.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
import argparse
from calendar import monthrange

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 현재 디렉토리를 scripts/backtesting으로 설정
os.chdir(project_root)

from scripts.backtesting.data_collector import UpbitDataCollector
from scripts.backtesting.data_quality import DataQualityChecker
import pandas as pd


def get_month_range(year: int, month: int):
    """특정 년/월의 시작일과 종료일 반환"""
    start_date = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    return start_date, end_date


def collect_monthly_data(
    ticker: str,
    year: int,
    month: int,
    interval: str,
    manager_dir: Path,
    force_update: bool = False
):
    """월별 데이터 수집 및 저장"""
    start_date, end_date = get_month_range(year, month)
    
    # 월별 파일명 생성
    month_str = f"{year}-{month:02d}"
    if interval == 'day':
        filename = f"{ticker}_{year}-{month:02d}-01_{year}-{month:02d}-{monthrange(year, month)[1]}.csv"
        file_path = manager_dir / filename
    else:
        return None
    
    # 강제 업데이트가 아닐 때만 캐시 사용
    if file_path.exists() and not force_update:
        print(f"  [{interval}] {month_str}: 캐시된 파일 사용 - {file_path.name}")
        try:
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            return df
        except Exception as e:
            print(f"  [{interval}] {month_str}: 캐시 파일 읽기 실패, 재수집: {e}")
    
    # 강제 업데이트일 때 기존 파일 삭제
    if force_update and file_path.exists():
        file_path.unlink()
        print(f"  [{interval}] {month_str}: 기존 파일 삭제 후 재수집 - {file_path.name}")
    
    # 데이터 수집
    days = (end_date - start_date).days + 1
    print(f"  [{interval}] {month_str}: 데이터 수집 중... (예상 일수: {days}일)")
    
    df = UpbitDataCollector.get_historical_data(
        ticker=ticker,
        interval=interval,
        days=days,
        to_time=end_date,
        start_time=start_date
    )
    
    if df.empty:
        print(f"  [{interval}] {month_str}: 데이터 없음")
        return None
    
    # 해당 월의 데이터만 필터링
    df = df[(df.index >= start_date) & (df.index <= end_date)]
    
    if df.empty:
        print(f"  [{interval}] {month_str}: 필터링 후 데이터 없음")
        return None
    
    # 품질 검사 및 정제
    checker = DataQualityChecker()
    cleaned_df = checker.clean_data(df)
    
    # CSV 저장
    cleaned_df.to_csv(file_path)
    print(f"  [{interval}] {month_str}: 저장 완료 - {len(cleaned_df)}행 ({file_path.name})")
    
    return cleaned_df


def collect_year_data(
    ticker: str,
    year: int,
    daily_dir: Path,
    force_update: bool = False
):
    """연도별 데이터 수집"""
    all_daily_data = []
    
    # 현재 날짜 확인 (미래 월은 스킵)
    current_date = datetime.now()
    max_month = current_date.month if year == current_date.year else 12
    
    for month in range(1, max_month + 1):
        print(f"\n[{year}년 {month}월]")
        
        # 일봉 데이터
        daily_df = collect_monthly_data(ticker, year, month, 'day', daily_dir, force_update)
        if daily_df is not None and not daily_df.empty:
            all_daily_data.append(daily_df)
    
    return all_daily_data


def main():
    """비트코인 데이터 수집 (2024, 2025년 일봉)"""
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description='Upbit 비트코인 일봉 데이터 수집 스크립트 (2024, 2025)')
    parser.add_argument('--years', nargs='+', type=int, default=[2024, 2025], 
                       help='수집할 연도 리스트 (기본값: 2024 2025)')
    parser.add_argument('--force', action='store_true', 
                       help='기존 파일을 삭제하고 강제로 재수집')
    args = parser.parse_args()
    
    years = sorted(set(args.years))  # 중복 제거 및 정렬
    force_update = args.force
    
    print("="*60)
    print(f"Upbit 비트코인 일봉 데이터 수집 (년도: {', '.join(map(str, years))})")
    print("="*60)
    print()
    
    ticker = 'KRW-BTC'
    
    # 데이터 디렉토리 설정
    data_dir = Path('backtest_data')
    daily_dir = data_dir / 'daily'
    
    # 디렉토리 생성
    daily_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"종목: {ticker}")
    print(f"수집 연도: {', '.join(map(str, years))}")
    print(f"인터벌: 일봉만")
    if force_update:
        print(f"강제 재수집: 활성화 (기존 파일 삭제 후 재생성)")
    print(f"저장 위치: {data_dir.absolute()}")
    print()
    
    # 전체 데이터 수집
    all_daily_data = []
    
    print("="*60)
    print("월별 데이터 수집 시작...")
    print("="*60)
    
    # 각 년도별로 데이터 수집
    for year in years:
        print(f"\n{'='*60}")
        print(f"[{year}년 데이터 수집 시작]")
        print(f"{'='*60}")
        
        year_data = collect_year_data(ticker, year, daily_dir, force_update)
        all_daily_data.extend(year_data)
    
    # 전체 데이터 통합 및 저장
    print("\n" + "="*60)
    print("전체 데이터 통합 및 저장")
    print("="*60)
    
    # 일봉 통합
    if all_daily_data:
        combined_daily = pd.concat(all_daily_data)
        combined_daily = combined_daily.sort_index()
        combined_daily = combined_daily[~combined_daily.index.duplicated(keep='first')]
        
        # 실제 데이터 범위에 맞게 파일명 생성
        actual_start = combined_daily.index.min().strftime('%Y-%m-%d')
        actual_end = combined_daily.index.max().strftime('%Y-%m-%d')
        daily_file = daily_dir / f"{ticker}_{actual_start}_{actual_end}.csv"
        
        # 강제 업데이트일 때 기존 파일 삭제
        if force_update and daily_file.exists():
            daily_file.unlink()
            print(f"\n[day] 기존 통합 파일 삭제: {daily_file.name}")
        
        combined_daily.to_csv(daily_file)
        print(f"\n[day] 전체 통합 파일 저장: {daily_file.name} ({len(combined_daily)}행)")
        print(f"  기간: {combined_daily.index.min()} ~ {combined_daily.index.max()}")
        
        # 년도별 통합 파일도 저장
        for year in years:
            year_data = combined_daily[combined_daily.index.year == year]
            if not year_data.empty:
                year_start = year_data.index.min().strftime('%Y-%m-%d')
                year_end = year_data.index.max().strftime('%Y-%m-%d')
                year_file = daily_dir / f"{ticker}_{year_start}_{year_end}.csv"
                
                if force_update and year_file.exists():
                    year_file.unlink()
                    print(f"\n[day] {year}년 기존 통합 파일 삭제: {year_file.name}")
                
                year_file.parent.mkdir(parents=True, exist_ok=True)
                year_data.to_csv(year_file)
                print(f"\n[day] {year}년 통합 파일 저장: {year_file.name} ({len(year_data)}행)")
                print(f"  기간: {year_data.index.min()} ~ {year_data.index.max()}")
    else:
        print("\n⚠️ 수집된 데이터가 없습니다.")
    
    print("\n" + "="*60)
    print("✅ 데이터 수집 완료!")
    print("="*60)
    print(f"\n데이터 저장 위치: {data_dir.absolute()}")
    print(f"  - 일봉: {daily_dir}")


if __name__ == "__main__":
    main()



