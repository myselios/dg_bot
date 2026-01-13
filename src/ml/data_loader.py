"""
ML 파이프라인용 데이터 로더

Parquet 파일에서 히스토리컬 데이터를 로드하고
Walk-Forward Validation을 위한 데이터 분할을 지원한다.
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MLDataLoader:
    """
    ML 최적화용 데이터 로더

    Features:
    - Parquet 파일에서 멀티코인 데이터 로드
    - Walk-Forward용 train/validate/holdout 분할
    - 데이터 무결성 검증
    """

    def __init__(self, data_dir: str = "data/historical"):
        """
        Args:
            data_dir: 히스토리컬 데이터 디렉토리
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise ValueError(f"데이터 디렉토리 없음: {data_dir}")

        logger.info(f"MLDataLoader 초기화: {data_dir}")

    def list_available_tickers(self) -> List[str]:
        """
        사용 가능한 티커 목록 반환

        Returns:
            티커 리스트 (예: ['BTC', 'ETH', 'SOL'])
        """
        parquet_files = list(self.data_dir.glob("*_day.parquet"))
        tickers = [f.stem.replace("_day", "") for f in parquet_files]

        logger.info(f"발견된 티커: {len(tickers)}개")
        return sorted(tickers)

    def load_ticker_data(
        self,
        ticker: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[pd.DataFrame]:
        """
        단일 티커 데이터 로드

        Args:
            ticker: 티커 심볼 (예: 'BTC')
            start_date: 시작일 (None이면 전체)
            end_date: 종료일 (None이면 전체)

        Returns:
            OHLCV DataFrame 또는 None
        """
        file_path = self.data_dir / f"{ticker}_day.parquet"

        if not file_path.exists():
            logger.warning(f"데이터 파일 없음: {file_path}")
            return None

        try:
            df = pd.read_parquet(file_path)

            # 날짜 필터링
            if start_date:
                df = df[df.index >= start_date]
            if end_date:
                df = df[df.index <= end_date]

            # 데이터 검증
            df = self._validate_data(df, ticker)

            logger.info(
                f"{ticker}: {len(df)} rows ({df.index[0].date()} ~ {df.index[-1].date()})"
            )
            return df

        except Exception as e:
            logger.error(f"{ticker} 데이터 로드 실패: {e}")
            return None

    def load_all_tickers(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_rows: int = 100,
    ) -> Dict[str, pd.DataFrame]:
        """
        모든 티커 데이터 로드

        Args:
            start_date: 시작일
            end_date: 종료일
            min_rows: 최소 데이터 행 수 (미만이면 제외)

        Returns:
            {ticker: DataFrame} 딕셔너리
        """
        data_dict = {}
        tickers = self.list_available_tickers()

        for ticker in tickers:
            df = self.load_ticker_data(ticker, start_date, end_date)

            if df is not None and len(df) >= min_rows:
                data_dict[ticker] = df
            else:
                logger.warning(f"{ticker} 제외: 데이터 부족 ({len(df) if df is not None else 0} < {min_rows})")

        logger.info(f"로드 완료: {len(data_dict)}/{len(tickers)} 티커")
        return data_dict

    def split_for_walk_forward(
        self,
        data: pd.DataFrame,
        train_months: int = 6,
        validate_months: int = 3,
        holdout_months: int = 3,
        purge_days: int = 7,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Walk-Forward용 데이터 분할

        Args:
            data: 전체 데이터
            train_months: 학습 기간 (월)
            validate_months: 검증 기간 (월)
            holdout_months: Hold-out 기간 (월)
            purge_days: Purge 버퍼 (일)

        Returns:
            (train_data, validate_data, holdout_data)
        """
        end_date = data.index.max()

        # Hold-out 분리 (마지막 N개월)
        holdout_start = end_date - timedelta(days=holdout_months * 30)
        holdout_data = data[data.index >= holdout_start]

        # Validate 분리 (Hold-out 이전 N개월)
        validate_end = holdout_start - timedelta(days=purge_days)
        validate_start = validate_end - timedelta(days=validate_months * 30)
        validate_data = data[(data.index >= validate_start) & (data.index < validate_end)]

        # Train 분리 (Validate 이전)
        train_end = validate_start - timedelta(days=purge_days)
        train_start = train_end - timedelta(days=train_months * 30)
        train_data = data[(data.index >= train_start) & (data.index < train_end)]

        logger.info(
            f"데이터 분할: Train={len(train_data)}, "
            f"Validate={len(validate_data)}, "
            f"Holdout={len(holdout_data)}"
        )

        return train_data, validate_data, holdout_data

    def get_data_summary(self) -> Dict[str, Dict]:
        """
        데이터 요약 정보 반환

        Returns:
            {ticker: {'rows': N, 'start': date, 'end': date, 'years': float}}
        """
        summary = {}
        tickers = self.list_available_tickers()

        for ticker in tickers:
            df = self.load_ticker_data(ticker)
            if df is not None and len(df) > 0:
                days = (df.index[-1] - df.index[0]).days
                summary[ticker] = {
                    'rows': len(df),
                    'start': df.index[0].date(),
                    'end': df.index[-1].date(),
                    'days': days,
                    'years': round(days / 365.25, 2),
                }

        return summary

    def _validate_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        데이터 무결성 검증 및 수정

        Args:
            df: 원본 데이터
            ticker: 티커 (로깅용)

        Returns:
            검증된 데이터
        """
        # 필수 컬럼 확인
        required = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"{ticker}: 필수 컬럼 누락 {missing}")

        # 결측치 처리
        null_count = df[required].isnull().sum().sum()
        if null_count > 0:
            logger.warning(f"{ticker}: 결측치 {null_count}개 → 전방 채움")
            df = df.ffill().bfill()

        # OHLC 논리 검증 (High >= max(Open, Close), Low <= min(Open, Close))
        invalid_high = df['high'] < df[['open', 'close']].max(axis=1)
        invalid_low = df['low'] > df[['open', 'close']].min(axis=1)

        if invalid_high.sum() > 0:
            logger.warning(f"{ticker}: High < max(O,C) {invalid_high.sum()}건 → 수정")
            df.loc[invalid_high, 'high'] = df.loc[invalid_high, ['open', 'close', 'high']].max(axis=1)

        if invalid_low.sum() > 0:
            logger.warning(f"{ticker}: Low > min(O,C) {invalid_low.sum()}건 → 수정")
            df.loc[invalid_low, 'low'] = df.loc[invalid_low, ['open', 'close', 'low']].min(axis=1)

        # 시간 순서 정렬
        if not df.index.is_monotonic_increasing:
            logger.warning(f"{ticker}: 시간 순서 오류 → 정렬")
            df = df.sort_index()

        return df

    def convert_to_upbit_format(self, ticker: str) -> str:
        """
        티커를 Upbit 형식으로 변환

        Args:
            ticker: 심볼 (예: 'BTC')

        Returns:
            Upbit 형식 (예: 'KRW-BTC')
        """
        return f"KRW-{ticker}"


def load_optimization_data(
    data_dir: str = "data/historical",
    min_rows: int = 200,
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict]]:
    """
    최적화용 데이터 로드 헬퍼 함수

    Args:
        data_dir: 데이터 디렉토리
        min_rows: 최소 데이터 행 수

    Returns:
        (data_dict, summary)
    """
    loader = MLDataLoader(data_dir)
    data_dict = loader.load_all_tickers(min_rows=min_rows)
    summary = loader.get_data_summary()

    return data_dict, summary
