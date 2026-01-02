"""
과거 데이터 동기화 관리자 (Historical Data Sync)

백테스팅을 위한 과거 데이터를 수집하고 관리합니다.

주요 기능:
- 신규 코인: 전체 데이터 다운로드 (최대 2년)
- 기존 코인: 증분 업데이트
- 데이터 유효성 검증
- 오래된 데이터 정리 (3년 이상)
- 타임아웃 처리 (API 무응답 방지)
"""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pandas as pd
import pyupbit

from src.utils.logger import Logger


@dataclass
class SyncStatus:
    """데이터 동기화 상태"""
    ticker: str
    symbol: str
    status: str  # 'success', 'partial', 'failed', 'skipped'
    rows_before: int
    rows_after: int
    rows_added: int
    date_range: Optional[Tuple[datetime, datetime]] = None
    error_message: Optional[str] = None
    sync_time: datetime = field(default_factory=datetime.now)


class HistoricalDataSync:
    """
    과거 데이터 동기화 관리자

    백테스팅을 위한 과거 데이터를 수집하고 관리합니다.

    사용 예시:
        sync = HistoricalDataSync(data_dir="./data/historical")
        status = await sync.sync_coin_data("KRW-BTC", years=2)
        print(f"동기화 결과: {status.status}, 추가된 행: {status.rows_added}")
    """

    # Upbit API 제한
    MAX_CANDLES_PER_REQUEST = 200  # 한 번에 가져올 수 있는 최대 캔들 수
    API_DELAY_SECONDS = 0.15  # API 호출 간격
    API_TIMEOUT_SECONDS = 30  # API 호출 타임아웃 (초)
    SYNC_TIMEOUT_SECONDS = 60  # 단일 코인 동기화 타임아웃 (초)

    def __init__(
        self,
        data_dir: str = "./data/historical",
        default_years: int = 2,
        max_years: int = 3
    ):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
            default_years: 기본 데이터 수집 기간 (년)
            max_years: 최대 보관 기간 (년), 초과 시 삭제
        """
        self.data_dir = Path(data_dir)
        self.default_years = default_years
        self.max_years = max_years
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="data_sync")

        # 데이터 디렉토리 생성
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_data_path(self, ticker: str, interval: str = "day") -> Path:
        """데이터 파일 경로 반환"""
        symbol = ticker.replace("KRW-", "")
        return self.data_dir / f"{symbol}_{interval}.parquet"

    async def sync_coin_data(
        self,
        ticker: str,
        years: Optional[int] = None,
        interval: str = "day",
        force_full: bool = False
    ) -> SyncStatus:
        """
        특정 코인 데이터 동기화

        Args:
            ticker: 코인 티커 (예: KRW-BTC)
            years: 수집 기간 (None이면 기본값 사용)
            interval: 데이터 간격 ('day', 'minute60', 'minute240')
            force_full: True면 전체 재다운로드

        Returns:
            SyncStatus: 동기화 결과
        """
        symbol = ticker.replace("KRW-", "")
        years = years or self.default_years
        data_path = self.get_data_path(ticker, interval)

        Logger.print_info(f"📥 [{symbol}] 데이터 동기화 시작...")

        try:
            # 기존 데이터 확인
            existing_df = None
            rows_before = 0

            if data_path.exists() and not force_full:
                existing_df = pd.read_parquet(data_path)
                rows_before = len(existing_df)
                Logger.print_info(f"  기존 데이터: {rows_before}행")

            # 시작 날짜 결정
            if existing_df is not None and len(existing_df) > 0:
                # 증분 업데이트: 마지막 데이터 다음 날부터
                last_date = pd.Timestamp(existing_df.index[-1])
                start_date = last_date + timedelta(days=1)
                Logger.print_info(f"  증분 업데이트: {start_date.date()} ~")
            else:
                # 전체 다운로드: years년 전부터
                start_date = datetime.now() - timedelta(days=years * 365)
                Logger.print_info(f"  전체 다운로드: {start_date.date()} ~")

            # 현재 날짜
            end_date = datetime.now()

            # 데이터 수집 필요 여부 확인
            if start_date >= end_date:
                return SyncStatus(
                    ticker=ticker,
                    symbol=symbol,
                    status='skipped',
                    rows_before=rows_before,
                    rows_after=rows_before,
                    rows_added=0,
                    date_range=(existing_df.index[0], existing_df.index[-1]) if existing_df is not None else None
                )

            # 데이터 수집
            new_df = await self._fetch_historical_data(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                interval=interval
            )

            if new_df is None or len(new_df) == 0:
                Logger.print_warning(f"  새로운 데이터 없음")
                return SyncStatus(
                    ticker=ticker,
                    symbol=symbol,
                    status='skipped' if rows_before > 0 else 'failed',
                    rows_before=rows_before,
                    rows_after=rows_before,
                    rows_added=0
                )

            # 데이터 병합
            if existing_df is not None and len(existing_df) > 0:
                # 중복 제거하며 병합
                combined_df = pd.concat([existing_df, new_df])
                combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                combined_df = combined_df.sort_index()
            else:
                combined_df = new_df

            # 오래된 데이터 정리
            cutoff_date = datetime.now() - timedelta(days=self.max_years * 365)
            combined_df = combined_df[combined_df.index >= cutoff_date]

            # 저장
            combined_df.to_parquet(data_path)
            rows_after = len(combined_df)

            Logger.print_success(f"  완료: {rows_after}행 (추가: {rows_after - rows_before}행)")

            return SyncStatus(
                ticker=ticker,
                symbol=symbol,
                status='success',
                rows_before=rows_before,
                rows_after=rows_after,
                rows_added=rows_after - rows_before,
                date_range=(combined_df.index[0], combined_df.index[-1])
            )

        except Exception as e:
            Logger.print_error(f"  동기화 실패: {str(e)}")
            return SyncStatus(
                ticker=ticker,
                symbol=symbol,
                status='failed',
                rows_before=rows_before,
                rows_after=rows_before,
                rows_added=0,
                error_message=str(e)
            )

    async def sync_multiple_coins(
        self,
        tickers: List[str],
        years: Optional[int] = None,
        interval: str = "day",
        max_concurrent: int = 3
    ) -> List[SyncStatus]:
        """
        여러 코인 데이터 동기화

        Args:
            tickers: 코인 티커 목록
            years: 수집 기간
            interval: 데이터 간격
            max_concurrent: 동시 처리 수 (API 제한 고려)

        Returns:
            SyncStatus 리스트
        """
        Logger.print_header(f"📦 멀티 코인 데이터 동기화 ({len(tickers)}개)")

        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def sync_with_semaphore(ticker: str) -> SyncStatus:
            """타임아웃이 적용된 동기화"""
            async with semaphore:
                try:
                    # 개별 코인 동기화에 타임아웃 적용
                    return await asyncio.wait_for(
                        self.sync_coin_data(ticker, years, interval),
                        timeout=self.SYNC_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    symbol = ticker.replace("KRW-", "")
                    Logger.print_error(f"  [{symbol}] ⏰ 동기화 타임아웃 ({self.SYNC_TIMEOUT_SECONDS}초)")
                    return SyncStatus(
                        ticker=ticker,
                        symbol=symbol,
                        status='failed',
                        rows_before=0,
                        rows_after=0,
                        rows_added=0,
                        error_message=f"동기화 타임아웃 ({self.SYNC_TIMEOUT_SECONDS}초)"
                    )
                except Exception as e:
                    symbol = ticker.replace("KRW-", "")
                    Logger.print_error(f"  [{symbol}] ❌ 동기화 실패: {str(e)}")
                    return SyncStatus(
                        ticker=ticker,
                        symbol=symbol,
                        status='failed',
                        rows_before=0,
                        rows_after=0,
                        rows_added=0,
                        error_message=str(e)
                    )

        # 병렬 처리 (전체에도 타임아웃 적용)
        tasks = [sync_with_semaphore(ticker) for ticker in tickers]
        try:
            # 전체 동기화 작업에 3분 타임아웃
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=180  # 3분
            )
        except asyncio.TimeoutError:
            Logger.print_error(f"❌ 전체 동기화 타임아웃 (3분)")
            # 완료되지 않은 작업은 실패로 처리
            results = []
            for ticker in tickers:
                results.append(SyncStatus(
                    ticker=ticker,
                    symbol=ticker.replace("KRW-", ""),
                    status='failed',
                    rows_before=0,
                    rows_after=0,
                    rows_added=0,
                    error_message="전체 동기화 타임아웃"
                ))

        # 예외 처리
        final_results = []
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                Logger.print_error(f"  [{ticker}] 예외 발생: {str(result)}")
                final_results.append(SyncStatus(
                    ticker=ticker,
                    symbol=ticker.replace("KRW-", ""),
                    status='failed',
                    rows_before=0,
                    rows_after=0,
                    rows_added=0,
                    error_message=str(result)
                ))
            else:
                final_results.append(result)

        # 결과 요약
        success_count = sum(1 for r in final_results if r.status == 'success')
        failed_count = sum(1 for r in final_results if r.status == 'failed')
        Logger.print_info(f"\n📊 동기화 완료: 성공 {success_count}/{len(tickers)}, 실패 {failed_count}")

        return final_results

    async def _fetch_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> Optional[pd.DataFrame]:
        """과거 데이터 수집 (페이징 처리, 타임아웃 적용)"""
        all_data = []
        current_to = end_date
        max_retries = 3

        def fetch_ohlcv(t: str, intv: str, cnt: int, to_str: str):
            """동기 API 호출 (클로저 문제 방지를 위해 명시적 인자 전달)"""
            return pyupbit.get_ohlcv(t, interval=intv, count=cnt, to=to_str)

        while current_to > start_date:
            retry_count = 0
            df = None

            while retry_count < max_retries:
                try:
                    # 타임아웃이 있는 API 호출
                    to_str = current_to.strftime("%Y-%m-%d %H:%M:%S")
                    df = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            self._executor,
                            fetch_ohlcv,
                            ticker,
                            interval,
                            self.MAX_CANDLES_PER_REQUEST,
                            to_str
                        ),
                        timeout=self.API_TIMEOUT_SECONDS
                    )
                    break  # 성공 시 루프 탈출

                except asyncio.TimeoutError:
                    retry_count += 1
                    if retry_count >= max_retries:
                        Logger.print_warning(f"  [{ticker}] API 타임아웃 (재시도 {max_retries}회 실패)")
                        return None if not all_data else pd.concat(all_data).sort_index()
                    await asyncio.sleep(1)  # 재시도 전 대기

                except Exception as e:
                    Logger.print_warning(f"  데이터 수집 오류: {str(e)}")
                    return None if not all_data else pd.concat(all_data).sort_index()

            if df is None or len(df) == 0:
                break

            # 시작 날짜 이후 데이터만 필터링
            df = df[df.index >= start_date]
            all_data.append(df)

            # 다음 페이지 계산
            earliest = df.index[0]
            if earliest <= start_date:
                break

            current_to = earliest - timedelta(seconds=1)

            # API 제한 방지
            await asyncio.sleep(self.API_DELAY_SECONDS)

        if not all_data:
            return None

        # 데이터 병합 및 정렬
        combined = pd.concat(all_data)
        combined = combined[~combined.index.duplicated(keep='first')]
        combined = combined.sort_index()

        return combined

    def load_data(self, ticker: str, interval: str = "day") -> Optional[pd.DataFrame]:
        """
        저장된 데이터 로드

        Args:
            ticker: 코인 티커
            interval: 데이터 간격

        Returns:
            DataFrame 또는 None
        """
        data_path = self.get_data_path(ticker, interval)

        if not data_path.exists():
            return None

        try:
            return pd.read_parquet(data_path)
        except Exception as e:
            Logger.print_error(f"데이터 로드 실패 ({ticker}): {str(e)}")
            return None

    def get_data_info(self, ticker: str, interval: str = "day") -> Optional[Dict]:
        """데이터 정보 조회"""
        data_path = self.get_data_path(ticker, interval)

        if not data_path.exists():
            return None

        try:
            df = pd.read_parquet(data_path)
            return {
                'ticker': ticker,
                'interval': interval,
                'rows': len(df),
                'start_date': df.index[0],
                'end_date': df.index[-1],
                'file_size_mb': data_path.stat().st_size / (1024 * 1024),
                'columns': list(df.columns)
            }
        except Exception as e:
            return {'error': str(e)}

    def cleanup_old_data(self) -> Dict[str, int]:
        """오래된 데이터 파일 정리"""
        cutoff_date = datetime.now() - timedelta(days=self.max_years * 365)
        cleaned = {'files_deleted': 0, 'rows_removed': 0}

        for file_path in self.data_dir.glob("*.parquet"):
            try:
                df = pd.read_parquet(file_path)
                original_len = len(df)

                # 오래된 데이터 제거
                df = df[df.index >= cutoff_date]

                if len(df) < original_len:
                    if len(df) > 0:
                        df.to_parquet(file_path)
                        cleaned['rows_removed'] += original_len - len(df)
                    else:
                        # 모든 데이터가 삭제됨 - 파일 삭제
                        file_path.unlink()
                        cleaned['files_deleted'] += 1
                        cleaned['rows_removed'] += original_len

            except Exception as e:
                Logger.print_warning(f"정리 실패 ({file_path.name}): {str(e)}")

        return cleaned

    def print_data_summary(self) -> None:
        """저장된 데이터 요약 출력"""
        Logger.print_header("📊 저장된 데이터 요약")

        files = list(self.data_dir.glob("*.parquet"))
        if not files:
            print("  저장된 데이터 없음")
            return

        total_size = 0
        print(f"{'파일':>20} {'행수':>10} {'기간':>25} {'크기(MB)':>10}")
        print("-" * 70)

        for file_path in sorted(files):
            try:
                df = pd.read_parquet(file_path)
                size_mb = file_path.stat().st_size / (1024 * 1024)
                total_size += size_mb

                period = f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}"
                print(f"{file_path.name:>20} {len(df):>10,} {period:>25} {size_mb:>10.2f}")

            except Exception as e:
                print(f"{file_path.name:>20} 오류: {str(e)}")

        print("-" * 70)
        print(f"{'총계':>20} {len(files)}개 파일, {total_size:.2f} MB")
