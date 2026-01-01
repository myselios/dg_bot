"""
과거 데이터 제공 클래스
백테스팅용 데이터를 로드하며, 캐시된 파일이 있으면 우선 사용
"""
import pyupbit
import pandas as pd
import numpy as np
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from pathlib import Path
from ..utils.logger import Logger


class HistoricalDataProvider:
    """과거 데이터 제공 클래스"""
    
    def __init__(self, data_dir: str = 'backtest_data'):
        """
        Args:
            data_dir: 백테스팅 데이터 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.daily_dir = self.data_dir / 'daily'
        self.hourly_dir = self.data_dir / 'hourly'
        self.minute_dir = self.data_dir / 'minute'
    
    def load_historical_data(
        self,
        ticker: str,
        days: int = 365,
        interval: str = "day",
        use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        과거 데이터 로드
        캐시된 파일이 있으면 우선 사용, 없으면 API에서 수집
        
        Args:
            ticker: 거래 종목 (예: 'KRW-BTC')
            days: 조회할 일수
            interval: 시간 간격 ('day', 'minute60', 'minute15' 등)
            use_cache: 캐시된 파일 사용 여부
            
        Returns:
            과거 데이터 DataFrame
        """
        try:
            # 캐시된 파일 찾기
            if use_cache:
                df = self._load_from_cache(ticker, interval)
                if df is not None and not df.empty:
                    Logger.print_info(f"캐시된 데이터 로드: {ticker} ({interval})")
                    return df
            
            # 캐시가 없거나 use_cache=False인 경우 API에서 수집
            Logger.print_info(f"API에서 데이터 수집 중: {ticker} ({interval})")
            
            # pyupbit의 get_ohlcv는 count 파라미터로 조회 개수를 지정
            # 일봉의 경우 최대 200개씩 조회 가능
            if interval == "day":
                # 일봉 데이터
                count = min(days, 200)  # 최대 200개
                df = pyupbit.get_ohlcv(ticker, interval="day", count=count)
                
                # 더 많은 데이터가 필요한 경우 반복 조회
                if days > 200:
                    all_data = [df]
                    remaining = days - 200
                    
                    while remaining > 0:
                        # 이전 데이터의 시작 시점
                        last_date = df.index[0]
                        prev_date = last_date - timedelta(days=1)
                        
                        # 다음 배치 조회
                        batch_count = min(remaining, 200)
                        prev_df = pyupbit.get_ohlcv(
                            ticker, 
                            interval="day", 
                            count=batch_count,
                            to=prev_date.strftime("%Y%m%d")
                        )
                        
                        if prev_df is None or len(prev_df) == 0:
                            break
                        
                        all_data.insert(0, prev_df)
                        remaining -= len(prev_df)
                        df = prev_df
                    
                    # 모든 데이터 합치기
                    df = pd.concat(all_data).sort_index()
                    df = df[~df.index.duplicated(keep='last')]
            else:
                # 분봉 데이터
                df = pyupbit.get_ohlcv(ticker, interval=interval, count=days)
            
            if df is None or len(df) == 0:
                Logger.print_error(f"{ticker} 과거 데이터를 가져올 수 없습니다.")
                return None
            
            Logger.print_info(f"{ticker} 과거 데이터 {len(df)}개 로드 완료")
            Logger.print_info(f"기간: {df.index[0]} ~ {df.index[-1]}")
            
            return df
            
        except Exception as e:
            Logger.print_error(f"과거 데이터 로드 실패: {str(e)}")
            return None
    
    def _load_from_cache(self, ticker: str, interval: str) -> Optional[pd.DataFrame]:
        """
        캐시된 데이터 파일 로드
        전체 기간 파일들을 찾아서 모두 합쳐서 반환 (예: 2024년 + 2025년)
        
        Args:
            ticker: 종목
            interval: 시간 간격
            
        Returns:
            DataFrame 또는 None
        """
        try:
            # interval에 따라 디렉토리 선택
            if interval == "day":
                cache_dir = self.daily_dir
                pattern = f"{ticker}_*.csv"
            elif interval == "minute60":
                cache_dir = self.hourly_dir
                pattern = f"{ticker}_*.csv"
            elif interval == "minute15":
                cache_dir = self.minute_dir
                pattern = f"{ticker}_15min_*.csv"
            else:
                return None
            
            if not cache_dir.exists():
                return None
            
            matching_files = list(cache_dir.glob(pattern))
            if not matching_files:
                return None
            
            # 전체 기간 파일 찾기 (300일 이상인 파일들)
            # 파일명에서 날짜 범위 추출하여 정렬
            file_info_list = []
            for file in matching_files:
                # 파일명에서 날짜 추출 (예: KRW-ETH_2024-01-01_2024-12-31.csv)
                parts = file.stem.split('_')
                if len(parts) >= 3:
                    try:
                        start_date_str = parts[-2]
                        end_date_str = parts[-1]
                        # 날짜 형식 확인 (YYYY-MM-DD)
                        if len(start_date_str) == 10 and len(end_date_str) == 10:
                            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                            days_diff = (end_date - start_date).days
                            # 300일 이상 차이나는 파일을 전체 기간 파일로 간주
                            if days_diff >= 300:
                                file_info_list.append({
                                    'file': file,
                                    'start': start_date,
                                    'end': end_date,
                                    'days': days_diff
                                })
                    except (ValueError, IndexError):
                        continue
            
            if not file_info_list:
                # 전체 기간 파일이 없으면 가장 최근 파일 사용
                selected_file = max(matching_files, key=lambda p: p.stat().st_mtime)
                Logger.print_info(f"최근 데이터 파일 로드: {selected_file.name}")
                df = pd.read_csv(selected_file, index_col=0, parse_dates=True)
                return df
            
            # 시작 날짜 순으로 정렬
            file_info_list.sort(key=lambda x: x['start'])
            
            # 여러 파일을 합치기
            all_dataframes = []
            for file_info in file_info_list:
                df = pd.read_csv(file_info['file'], index_col=0, parse_dates=True)
                if not df.empty:
                    all_dataframes.append(df)
                    Logger.print_info(f"데이터 파일 로드: {file_info['file'].name} ({file_info['start'].date()} ~ {file_info['end'].date()})")
            
            if not all_dataframes:
                return None
            
            # 모든 데이터프레임 합치기
            combined_df = pd.concat(all_dataframes, axis=0)
            
            # 인덱스 중복 제거 (겹치는 날짜가 있을 수 있음)
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            
            # 날짜 순으로 정렬
            combined_df = combined_df.sort_index()
            
            total_days = (combined_df.index[-1] - combined_df.index[0]).days
            Logger.print_info(f"전체 데이터 로드 완료: {len(combined_df)}개 (기간: {combined_df.index[0].date()} ~ {combined_df.index[-1].date()}, 총 {total_days}일)")

            return combined_df

        except Exception as e:
            Logger.print_warning(f"캐시 로드 실패: {str(e)}")
            return None

    @staticmethod
    def validate_ohlcv_data(
        df: pd.DataFrame,
        fix_errors: bool = True,
        log_warnings: bool = True
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        OHLCV 데이터 무결성 검증 및 수정

        Args:
            df: OHLCV 데이터프레임
            fix_errors: True면 오류를 자동 수정, False면 검증만 수행
            log_warnings: True면 경고 로깅

        Returns:
            (수정된 데이터프레임, 발견된 오류 목록)

        검증 항목:
            1. OHLC 논리 검증 (High >= max(Open, Close), Low <= min(Open, Close))
            2. 결측치 검사
            3. 음수 값 검사
            4. 시간 순서 검증
            5. 시간 갭 검사
        """
        errors = []
        validated_df = df.copy()

        # 필수 컬럼 확인
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_columns if col not in validated_df.columns]
        if missing_cols:
            errors.append(f"필수 컬럼 누락: {missing_cols}")
            return validated_df, errors

        # 1. OHLC 논리 검증
        # High가 Open, Close 중 최대값보다 작은 경우
        invalid_high = validated_df[validated_df['high'] < validated_df[['open', 'close']].max(axis=1)]
        if len(invalid_high) > 0:
            errors.append(f"High < max(Open, Close): {len(invalid_high)}건")
            if fix_errors:
                validated_df.loc[invalid_high.index, 'high'] = validated_df.loc[invalid_high.index, ['open', 'close', 'high']].max(axis=1)

        # Low가 Open, Close 중 최소값보다 큰 경우
        invalid_low = validated_df[validated_df['low'] > validated_df[['open', 'close']].min(axis=1)]
        if len(invalid_low) > 0:
            errors.append(f"Low > min(Open, Close): {len(invalid_low)}건")
            if fix_errors:
                validated_df.loc[invalid_low.index, 'low'] = validated_df.loc[invalid_low.index, ['open', 'close', 'low']].min(axis=1)

        # High < Low인 경우 (치명적 오류)
        invalid_range = validated_df[validated_df['high'] < validated_df['low']]
        if len(invalid_range) > 0:
            errors.append(f"High < Low (치명적): {len(invalid_range)}건")
            if fix_errors:
                # High와 Low 교환
                high_vals = validated_df.loc[invalid_range.index, 'high'].copy()
                validated_df.loc[invalid_range.index, 'high'] = validated_df.loc[invalid_range.index, 'low']
                validated_df.loc[invalid_range.index, 'low'] = high_vals

        # 2. 결측치 검사
        nulls = validated_df[required_columns].isnull().sum()
        null_cols = nulls[nulls > 0]
        if len(null_cols) > 0:
            errors.append(f"결측치 발견: {null_cols.to_dict()}")
            if fix_errors:
                # 전방 채움 후 후방 채움
                validated_df[required_columns] = validated_df[required_columns].ffill().bfill()

        # 3. 음수 값 검사 (가격은 음수일 수 없음)
        for col in ['open', 'high', 'low', 'close']:
            negative = validated_df[validated_df[col] < 0]
            if len(negative) > 0:
                errors.append(f"{col} 음수값: {len(negative)}건")
                if fix_errors:
                    validated_df.loc[negative.index, col] = validated_df.loc[negative.index, col].abs()

        # 거래량 음수 검사
        negative_vol = validated_df[validated_df['volume'] < 0]
        if len(negative_vol) > 0:
            errors.append(f"volume 음수값: {len(negative_vol)}건")
            if fix_errors:
                validated_df.loc[negative_vol.index, 'volume'] = 0

        # 4. 시간 순서 검증
        if not validated_df.index.is_monotonic_increasing:
            errors.append("시간 순서 오류 (비단조증가)")
            if fix_errors:
                validated_df = validated_df.sort_index()

        # 5. 시간 갭 검사 (일봉 기준 3일 이상 갭 경고)
        if len(validated_df) > 1 and isinstance(validated_df.index, pd.DatetimeIndex):
            time_diffs = validated_df.index.to_series().diff()
            # 일봉 기준 3일 이상 갭
            large_gaps = time_diffs[time_diffs > pd.Timedelta(days=3)]
            if len(large_gaps) > 0:
                gap_info = [(str(idx.date()), str(gap)) for idx, gap in large_gaps.items()]
                errors.append(f"시간 갭 경고 (3일 초과): {len(large_gaps)}건")
                if log_warnings:
                    for idx, gap in gap_info[:5]:  # 최대 5개만 로깅
                        Logger.print_warning(f"시간 갭: {idx}에서 {gap}")

        # 결과 로깅
        if log_warnings and errors:
            Logger.print_warning(f"데이터 검증 결과: {len(errors)}개 이슈 발견")
            for error in errors:
                Logger.print_warning(f"  - {error}")
        elif log_warnings:
            Logger.print_info("데이터 검증 완료: 이슈 없음")

        return validated_df, errors

    def load_and_validate(
        self,
        ticker: str,
        days: int = 365,
        interval: str = "day",
        use_cache: bool = True,
        fix_errors: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        데이터 로드 및 무결성 검증 통합 메서드

        Args:
            ticker: 거래 종목
            days: 조회할 일수
            interval: 시간 간격
            use_cache: 캐시 사용 여부
            fix_errors: 오류 자동 수정 여부

        Returns:
            검증된 데이터프레임 또는 None
        """
        # 데이터 로드
        df = self.load_historical_data(ticker, days, interval, use_cache)

        if df is None or df.empty:
            return None

        # 데이터 검증 및 수정
        validated_df, errors = self.validate_ohlcv_data(df, fix_errors=fix_errors)

        return validated_df
    

