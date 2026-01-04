"""
코인 선택기 (Coin Selector)

유동성 스캔 → Research Pass → Trading Pass 전체 흐름을 조율합니다.

주요 기능:
- 유동성 상위 코인 스캔
- 섹터별 분산 선택 (포트폴리오 다양성 확보)
- 병렬 백테스팅 필터링 (Research Pass - 느슨한 기준)
- Trading Pass 최종 검증 (엄격한 기준 + Expectancy)
- 최종 진입 코인 선택

⚠️ 2026-01-04 변경: EntryAnalyzer 제거 (Clean Architecture 마이그레이션)
- AI 진입 분석 단계 제거됨
- 백테스팅 통과 코인을 직접 Trading Pass로 검증
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

# AI 분석 관련 타입은 제거됨 (Clean Architecture 마이그레이션)

from src.scanner.liquidity_scanner import LiquidityScanner, CoinInfo
from src.scanner.data_sync import HistoricalDataSync
from src.scanner.multi_backtest import MultiCoinBacktest, BacktestScore, MultiBacktestConfig
from src.scanner.sector_mapping import (
    SectorDiversifier,
    get_coin_sector,
    get_sector_korean_name,
    CoinSector
)
# EntryAnalyzer 제거됨 - Clean Architecture 마이그레이션
# from src.ai.entry_analyzer import EntryAnalyzer, EntrySignal
from src.backtesting.quick_filter import QuickBacktestFilter, TradingPassConfig  # 2단 게이트
from src.config.settings import ScannerConfig
from src.utils.logger import Logger


@dataclass
class CoinCandidate:
    """코인 후보 (백테스팅 결과 기반)"""
    ticker: str
    symbol: str
    coin_info: Optional[CoinInfo]         # 유동성 정보
    backtest_score: Optional[BacktestScore]  # 백테스팅 결과
    final_score: float                     # 최종 점수 (백테스팅 점수)
    final_grade: str                       # 최종 등급
    selected: bool                         # 최종 선택 여부
    selection_reason: str                  # 선택/미선택 사유
    analysis_time: datetime = field(default_factory=datetime.now)
    # 백테스팅 평가 결과
    backtest_passed: bool = False          # 백테스팅 통과 여부
    backtest_reason: str = ""              # 백테스팅 결과 사유
    expectancy_R: float = 0.0              # 기대값 (R 단위)

    @property
    def is_ready_for_entry(self) -> bool:
        """
        진입 준비 완료 여부 (백테스팅 통과 필수)

        백테스팅 통과 + 선택된 코인만 진입 가능
        """
        return self.selected and self.backtest_passed


@dataclass
class ScanResult:
    """스캔 결과 (전체 프로세스)"""
    scan_time: datetime
    liquidity_scanned: int                # 유동성 스캔 코인 수
    backtest_passed: int                  # 백테스팅 통과 코인 수
    candidates: List[CoinCandidate]       # 최종 후보
    selected_coins: List[CoinCandidate]   # 선택된 코인
    total_duration_seconds: float         # 전체 소요 시간
    all_backtest_results: Optional[List] = None  # 모든 백테스팅 결과 (통과 여부 무관)


class CoinSelector:
    """
    코인 선택기

    전체 스캐닝 파이프라인을 조율합니다:
    1. 유동성 스캔 (상위 10개, ScannerConfig.LIQUIDITY_TOP_N 참조)
    2. 데이터 동기화
    3. 병렬 백테스팅 (12개 필터 + Expectancy 검증)
    4. 최종 선택 (상위 2개)

    사용 예시:
        selector = CoinSelector()
        result = await selector.select_coins()
        for coin in result.selected_coins:
            print(f"{coin.symbol}: {coin.final_score:.1f}점")
    """

    def __init__(
        self,
        liquidity_scanner: Optional[LiquidityScanner] = None,
        data_sync: Optional[HistoricalDataSync] = None,
        multi_backtest: Optional[MultiCoinBacktest] = None,
        sector_diversifier: Optional[SectorDiversifier] = None,
        # 스캔 파라미터
        liquidity_top_n: int = 10,
        min_volume_krw: float = 10_000_000_000,  # 100억원
        backtest_top_n: int = 5,
        final_select_n: int = 2,
        # 섹터 분산 파라미터
        enable_sector_diversification: bool = True,
        one_per_sector: bool = True,
        exclude_unknown_sector: bool = ScannerConfig.EXCLUDE_UNKNOWN_SECTOR
    ):
        """
        Args:
            liquidity_scanner: 유동성 스캐너
            data_sync: 데이터 동기화 관리자
            multi_backtest: 멀티 백테스터
            sector_diversifier: 섹터 분산 선택기
            liquidity_top_n: 유동성 스캔 상위 N개
            min_volume_krw: 최소 거래대금
            backtest_top_n: 백테스팅 통과 상위 N개
            final_select_n: 최종 선택 N개
            enable_sector_diversification: 섹터 분산 활성화 여부
            one_per_sector: True면 섹터당 1개만 선택
            exclude_unknown_sector: True면 미분류 섹터 코인 제외
        """
        self.liquidity_scanner = liquidity_scanner or LiquidityScanner(min_volume_krw=min_volume_krw)
        self.data_sync = data_sync or HistoricalDataSync()
        self.multi_backtest = multi_backtest or MultiCoinBacktest(data_sync=self.data_sync)
        self.sector_diversifier = sector_diversifier or SectorDiversifier()

        self.liquidity_top_n = liquidity_top_n
        self.min_volume_krw = min_volume_krw
        self.backtest_top_n = backtest_top_n
        self.final_select_n = final_select_n

        # 섹터 분산 설정
        self.enable_sector_diversification = enable_sector_diversification
        self.one_per_sector = one_per_sector
        self.exclude_unknown_sector = exclude_unknown_sector

    async def select_coins(
        self,
        exclude_tickers: Optional[List[str]] = None,
        force_data_sync: bool = False
    ) -> ScanResult:
        """
        코인 선택 프로세스 실행

        Args:
            exclude_tickers: 제외할 코인 목록 (이미 보유 중인 코인)
            force_data_sync: True면 강제 데이터 재동기화

        Returns:
            ScanResult: 스캔 결과
        """
        start_time = datetime.now()
        Logger.print_header("🎯 코인 선택 프로세스 시작")

        exclude_tickers = exclude_tickers or []

        # ========================================
        # 1단계: 유동성 스캔
        # ========================================
        Logger.print_info("\n📊 1단계: 유동성 스캔")
        top_coins = await self.liquidity_scanner.scan_top_coins(
            min_volume_krw=self.min_volume_krw,
            top_n=self.liquidity_top_n,
            include_volatility=True
        )

        # 이미 보유 중인 코인 제외
        filtered_coins = [c for c in top_coins if c.ticker not in exclude_tickers]
        Logger.print_info(f"  유동성 상위: {len(top_coins)}개 → 보유 제외: {len(filtered_coins)}개")

        if not filtered_coins:
            return self._empty_result(start_time)

        # ========================================
        # 1-1단계: 섹터별 분산 선택 (옵션)
        # ========================================
        if self.enable_sector_diversification:
            Logger.print_info("\n🏷️ 1-1단계: 섹터별 분산 선택")
            diversified_coins = self.sector_diversifier.select_diversified(
                coins=filtered_coins,
                max_coins=self.liquidity_top_n,
                one_per_sector=self.one_per_sector,
                exclude_unknown=self.exclude_unknown_sector
            )
            Logger.print_info(f"  섹터 분산 전: {len(filtered_coins)}개 → 분산 후: {len(diversified_coins)}개")

            # 섹터 분포 출력
            self._print_sector_summary(diversified_coins)

            filtered_coins = diversified_coins

        if not filtered_coins:
            return self._empty_result(start_time)

        # 유동성 결과 출력
        self.liquidity_scanner.print_scan_result(filtered_coins[:10])

        # ========================================
        # 2단계: 데이터 동기화
        # ========================================
        Logger.print_info("\n📥 2단계: 데이터 동기화")
        tickers = [c.ticker for c in filtered_coins]
        await self.data_sync.sync_multiple_coins(
            tickers=tickers,
            years=1,  # 1년치 데이터
            interval="day",
            max_concurrent=3
        )

        # ========================================
        # 3단계: 병렬 백테스팅
        # ========================================
        Logger.print_info("\n🔬 3단계: 병렬 백테스팅")
        coin_infos = {c.ticker: c for c in filtered_coins}
        backtest_results = await self.multi_backtest.run_parallel_backtest(
            coin_list=tickers,
            coin_infos=coin_infos,
            top_n=self.backtest_top_n
        )

        # 통과 코인만 필터링
        passed_backtests = [r for r in backtest_results if r.passed]
        Logger.print_info(f"  백테스팅 통과: {len(passed_backtests)}/{len(backtest_results)}")

        if not passed_backtests:
            Logger.print_warning("  백테스팅 통과 코인 없음")
            return self._create_result(
                start_time=start_time,
                liquidity_scanned=len(filtered_coins),
                backtest_passed=0,
                candidates=[],
                selected_coins=[],
                all_backtest_results=backtest_results  # 모든 결과 포함
            )

        self.multi_backtest.print_results(passed_backtests)

        # ========================================
        # 4단계: 후보 생성 및 백테스팅 검증
        # ========================================
        Logger.print_info("\n📋 4단계: 후보 생성 및 백테스팅 검증")
        candidates: List[CoinCandidate] = []

        for bt_result in passed_backtests:
            candidates.append(self._create_candidate(bt_result=bt_result))
        Logger.print_info(f"  생성된 후보: {len(candidates)}개")

        # 백테스팅 최종 검증 (Expectancy 포함)
        Logger.print_info("\n🔐 백테스팅 최종 검증 (12개 필터 + Expectancy)")
        candidates = self._apply_backtest(candidates)

        # 백테스팅 통과 코인 수
        backtest_final_passed = sum(1 for c in candidates if c.backtest_passed)
        Logger.print_info(f"  백테스팅 통과: {backtest_final_passed}/{len(candidates)}")

        # ========================================
        # 5단계: 최종 선택
        # ========================================
        Logger.print_info("\n🏆 5단계: 최종 선택")
        selected_coins = self._select_final_coins(candidates)

        # backtest_results에 백테스팅 검증 정보 병합
        candidate_map = {c.symbol: c for c in candidates}
        enriched_backtest_results = []
        for bt_result in backtest_results:
            result_dict = {
                'symbol': bt_result.symbol,
                'score': bt_result.score,
                'grade': bt_result.grade,
                'passed': bt_result.passed,
                'metrics': bt_result.metrics,
                'filter_results': bt_result.filter_results,
            }
            # 백테스팅 검증 정보 추가
            if bt_result.symbol in candidate_map:
                candidate = candidate_map[bt_result.symbol]
                result_dict['expectancy'] = candidate.expectancy_R
                result_dict['backtest_passed'] = candidate.backtest_passed
                result_dict['backtest_reason'] = candidate.backtest_reason
            enriched_backtest_results.append(result_dict)

        # 결과 생성
        result = self._create_result(
            start_time=start_time,
            liquidity_scanned=len(filtered_coins),
            backtest_passed=len(passed_backtests),
            candidates=candidates,
            selected_coins=selected_coins,
            all_backtest_results=enriched_backtest_results
        )

        # 최종 결과 출력
        self._print_final_result(result)

        return result

    def _create_candidate(
        self,
        bt_result: BacktestScore
    ) -> CoinCandidate:
        """코인 후보 생성 (백테스팅 결과 기반)"""
        # 최종 점수: 백테스팅 점수 그대로 사용
        final_score = bt_result.score

        # 최종 등급: 백테스팅 등급 사용
        final_grade = bt_result.grade

        # 선택 여부: 백테스팅 통과 여부
        selected = bt_result.passed

        # 사유: 백테스팅 결과 기반
        if selected:
            selection_reason = f"백테스팅 통과 ({bt_result.grade})"
        else:
            selection_reason = "백테스팅 미통과"

        return CoinCandidate(
            ticker=bt_result.ticker,
            symbol=bt_result.symbol,
            coin_info=bt_result.coin_info,
            backtest_score=bt_result,
            final_score=final_score,
            final_grade=final_grade,
            selected=selected,
            selection_reason=selection_reason
        )

    def _calculate_final_score(
        self,
        bt_result: BacktestScore
    ) -> float:
        """최종 점수 계산 (백테스팅 점수만 사용)"""
        return bt_result.score

    def _determine_final_grade(
        self,
        bt_result: BacktestScore,
        final_score: float
    ) -> str:
        """최종 등급 결정 (백테스팅 기반)"""
        if not bt_result.passed:
            return "FAIL"

        # 백테스팅 등급 기반
        if bt_result.grade == "STRONG PASS":
            return "BUY"
        else:
            return "WEAK BUY"

    def _should_select(
        self,
        bt_result: BacktestScore,
        final_score: float
    ) -> bool:
        """선택 여부 결정 (백테스팅 기반)"""
        # 백테스팅 미통과면 선택 안함
        if not bt_result.passed:
            return False

        # 최종 점수가 40점 이상이면 선택 (WEAK PASS 포함)
        return final_score >= 40

    def _generate_selection_reason(
        self,
        bt_result: BacktestScore,
        selected: bool
    ) -> str:
        """선택/미선택 사유 생성 (백테스팅 기반)"""
        if not selected:
            if not bt_result.passed:
                return f"백테스팅 미통과: {bt_result.reason}"
            return "점수 미달"

        # 선택된 경우
        return f"백테스팅 {bt_result.grade}"

    def _select_final_coins(self, candidates: List[CoinCandidate]) -> List[CoinCandidate]:
        """최종 코인 선택"""
        # selected=True인 것만 필터링
        selectable = [c for c in candidates if c.selected]

        # 점수 순 정렬
        selectable.sort(key=lambda x: x.final_score, reverse=True)

        # 상위 N개 선택
        selected = selectable[:self.final_select_n]

        Logger.print_info(f"  최종 선택: {len(selected)}개 코인")
        for coin in selected:
            Logger.print_info(f"    - {coin.symbol}: {coin.final_score:.1f}점 ({coin.final_grade})")

        return selected

    def _empty_result(self, start_time: datetime) -> ScanResult:
        """빈 결과 생성"""
        return ScanResult(
            scan_time=start_time,
            liquidity_scanned=0,
            backtest_passed=0,
            candidates=[],
            selected_coins=[],
            total_duration_seconds=(datetime.now() - start_time).total_seconds()
        )

    def _create_result(
        self,
        start_time: datetime,
        liquidity_scanned: int,
        backtest_passed: int,
        candidates: List[CoinCandidate],
        selected_coins: List[CoinCandidate],
        all_backtest_results: Optional[List] = None
    ) -> ScanResult:
        """결과 생성"""
        return ScanResult(
            scan_time=start_time,
            liquidity_scanned=liquidity_scanned,
            backtest_passed=backtest_passed,
            candidates=candidates,
            selected_coins=selected_coins,
            total_duration_seconds=(datetime.now() - start_time).total_seconds(),
            all_backtest_results=all_backtest_results
        )

    def _print_final_result(self, result: ScanResult) -> None:
        """최종 결과 출력"""
        Logger.print_header("📋 코인 선택 최종 결과")

        print(f"스캔 시간: {result.scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"소요 시간: {result.total_duration_seconds:.1f}초")
        print()
        print("파이프라인 요약:")
        print(f"  1. 유동성 스캔: {result.liquidity_scanned}개")
        print(f"  2. 백테스팅 검증: {result.backtest_passed}개")
        print(f"  3. 최종 선택: {len(result.selected_coins)}개")
        print()

        if result.selected_coins:
            print("선택된 코인:")
            print(f"{'순위':>4} {'심볼':>8} {'점수':>8} {'등급':>12} {'사유':>30}")
            print("-" * 70)

            for i, coin in enumerate(result.selected_coins, 1):
                print(f"{i:>4} {coin.symbol:>8} {coin.final_score:>8.1f} {coin.final_grade:>12} {coin.selection_reason[:30]:>30}")
        else:
            print("선택된 코인이 없습니다.")

    def _print_sector_summary(self, coins: List[CoinInfo]) -> None:
        """섹터 분포 요약 출력"""
        distribution = self.sector_diversifier.get_sector_distribution(coins)

        print("\n  [섹터 분포]")
        for sector, count in distribution.items():
            sector_coins = [c.symbol for c in coins if get_coin_sector(c.symbol) == sector]
            coins_str = ", ".join(sector_coins[:3])
            if len(sector_coins) > 3:
                coins_str += f" (+{len(sector_coins) - 3})"
            print(f"    {get_sector_korean_name(sector):12}: {count}개 ({coins_str})")

    def _apply_backtest(self, candidates: List[CoinCandidate]) -> List[CoinCandidate]:
        """
        백테스팅 최종 검증 적용

        12개 필터 + Expectancy 필터로 실거래 적합성을 최종 검증합니다.
        - BacktestConfig 임계값 사용
        - Expectancy Filter 필수 (기대값 양수)

        Args:
            candidates: 후보 코인 리스트

        Returns:
            백테스팅 검증 결과가 업데이트된 후보 리스트
        """
        backtest_filter = QuickBacktestFilter(BacktestConfig())

        for candidate in candidates:
            # 백테스트 결과가 없으면 스킵
            if not candidate.backtest_score or not candidate.backtest_score.metrics:
                candidate.backtest_passed = False
                candidate.backtest_reason = "백테스트 결과 없음"
                continue

            # 백테스팅 검증
            metrics = candidate.backtest_score.metrics
            pass_result = backtest_filter.evaluate_backtest(metrics)

            # Expectancy 정보 추출
            exp_result = backtest_filter.check_expectancy_with_metrics(metrics)

            # 결과 업데이트
            candidate.backtest_passed = pass_result.passed
            candidate.backtest_reason = pass_result.reason
            candidate.expectancy_R = exp_result.get('net_expectancy', 0.0)

            # 로그 출력
            status = "✅" if pass_result.passed else "❌"
            Logger.print_info(
                f"  [{candidate.symbol}] {status} 백테스팅 검증 "
                f"(기대값: {candidate.expectancy_R:.3f}R)"
            )

            # 백테스팅 실패 시 selected=False로 변경
            if not pass_result.passed:
                candidate.selected = False
                candidate.selection_reason = f"백테스팅 미통과: {pass_result.reason}"

        return candidates
