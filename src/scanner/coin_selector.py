"""
코인 선택기 (Coin Selector)

유동성 스캔 → 백테스팅 → AI 분석까지의 전체 흐름을 조율합니다.

주요 기능:
- 유동성 상위 코인 스캔
- 섹터별 분산 선택 (포트폴리오 다양성 확보)
- 병렬 백테스팅 필터링
- AI 진입 분석 (상위 N개만)
- 최종 진입 코인 선택
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from src.scanner.liquidity_scanner import LiquidityScanner, CoinInfo
from src.scanner.data_sync import HistoricalDataSync
from src.scanner.multi_backtest import MultiCoinBacktest, BacktestScore, MultiBacktestConfig
from src.scanner.sector_mapping import (
    SectorDiversifier,
    get_coin_sector,
    get_sector_korean_name,
    CoinSector
)
from src.ai.entry_analyzer import EntryAnalyzer, EntrySignal
from src.utils.logger import Logger


@dataclass
class CoinCandidate:
    """코인 후보 (전체 분석 결과 통합)"""
    ticker: str
    symbol: str
    coin_info: Optional[CoinInfo]         # 유동성 정보
    backtest_score: Optional[BacktestScore]  # 백테스팅 결과
    entry_signal: Optional[EntrySignal]    # AI 진입 분석 결과
    final_score: float                     # 최종 점수
    final_grade: str                       # 최종 등급
    selected: bool                         # 최종 선택 여부
    selection_reason: str                  # 선택/미선택 사유
    analysis_time: datetime = field(default_factory=datetime.now)

    @property
    def is_ready_for_entry(self) -> bool:
        """진입 준비 완료 여부"""
        return (
            self.selected and
            self.entry_signal is not None and
            self.entry_signal.decision == 'buy'
        )


@dataclass
class ScanResult:
    """스캔 결과 (전체 프로세스)"""
    scan_time: datetime
    liquidity_scanned: int                # 유동성 스캔 코인 수
    backtest_passed: int                  # 백테스팅 통과 코인 수
    ai_analyzed: int                      # AI 분석 코인 수
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
    3. 병렬 백테스팅 (상위 5개 선별)
    4. AI 진입 분석 (상위 5개)
    5. 최종 선택 (상위 2개)

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
        entry_analyzer: Optional[EntryAnalyzer] = None,
        sector_diversifier: Optional[SectorDiversifier] = None,
        # 스캔 파라미터
        liquidity_top_n: int = 10,
        min_volume_krw: float = 10_000_000_000,  # 100억원
        backtest_top_n: int = 5,
        ai_top_n: int = 5,
        final_select_n: int = 2,
        # 섹터 분산 파라미터
        enable_sector_diversification: bool = True,
        one_per_sector: bool = True,
        exclude_unknown_sector: bool = False
    ):
        """
        Args:
            liquidity_scanner: 유동성 스캐너
            data_sync: 데이터 동기화 관리자
            multi_backtest: 멀티 백테스터
            entry_analyzer: AI 진입 분석기
            sector_diversifier: 섹터 분산 선택기
            liquidity_top_n: 유동성 스캔 상위 N개
            min_volume_krw: 최소 거래대금
            backtest_top_n: 백테스팅 통과 상위 N개
            ai_top_n: AI 분석 대상 N개
            final_select_n: 최종 선택 N개
            enable_sector_diversification: 섹터 분산 활성화 여부
            one_per_sector: True면 섹터당 1개만 선택
            exclude_unknown_sector: True면 미분류 섹터 코인 제외
        """
        self.liquidity_scanner = liquidity_scanner or LiquidityScanner(min_volume_krw=min_volume_krw)
        self.data_sync = data_sync or HistoricalDataSync()
        self.multi_backtest = multi_backtest or MultiCoinBacktest(data_sync=self.data_sync)
        self.entry_analyzer = entry_analyzer
        self.sector_diversifier = sector_diversifier or SectorDiversifier()

        self.liquidity_top_n = liquidity_top_n
        self.min_volume_krw = min_volume_krw
        self.backtest_top_n = backtest_top_n
        self.ai_top_n = ai_top_n
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
                ai_analyzed=0,
                candidates=[],
                selected_coins=[],
                all_backtest_results=backtest_results  # 모든 결과 포함
            )

        self.multi_backtest.print_results(passed_backtests)

        # ========================================
        # 4단계: AI 진입 분석 (옵션)
        # ========================================
        ai_analyzed = 0
        candidates: List[CoinCandidate] = []

        if self.entry_analyzer:
            Logger.print_info("\n🤖 4단계: AI 진입 분석")
            ai_candidates = passed_backtests[:self.ai_top_n]
            Logger.print_info(f"  분석 대상: {len(ai_candidates)}개 코인")

            for bt_result in ai_candidates:
                try:
                    # 시장 데이터 준비 (간소화)
                    analysis_data = self._prepare_analysis_data(bt_result)

                    # AI 분석
                    entry_signal = self.entry_analyzer.analyze_entry(
                        ticker=bt_result.ticker,
                        analysis_data=analysis_data,
                        backtest_result=bt_result.metrics
                    )
                    ai_analyzed += 1

                    # 후보 생성
                    candidate = self._create_candidate(
                        bt_result=bt_result,
                        entry_signal=entry_signal
                    )
                    candidates.append(candidate)

                except Exception as e:
                    Logger.print_warning(f"  [{bt_result.symbol}] AI 분석 실패: {str(e)}")
                    candidates.append(self._create_candidate(bt_result=bt_result, entry_signal=None))

        else:
            # AI 분석기 없으면 백테스팅 결과만으로 후보 생성
            Logger.print_info("\n⏭️ 4단계: AI 분석 스킵 (entry_analyzer 없음)")
            for bt_result in passed_backtests[:self.ai_top_n]:
                candidates.append(self._create_candidate(bt_result=bt_result, entry_signal=None))

        # ========================================
        # 5단계: 최종 선택
        # ========================================
        Logger.print_info("\n🏆 5단계: 최종 선택")
        selected_coins = self._select_final_coins(candidates)

        # 결과 생성
        result = self._create_result(
            start_time=start_time,
            liquidity_scanned=len(filtered_coins),
            backtest_passed=len(passed_backtests),
            ai_analyzed=ai_analyzed,
            candidates=candidates,
            selected_coins=selected_coins,
            all_backtest_results=backtest_results  # 모든 결과 포함
        )

        # 최종 결과 출력
        self._print_final_result(result)

        return result

    def _prepare_analysis_data(self, bt_result: BacktestScore) -> Dict[str, Any]:
        """AI 분석을 위한 데이터 준비"""
        # 기본 데이터 구조
        data = {
            'ticker': bt_result.ticker,
            'backtest_metrics': bt_result.metrics,
            'backtest_grade': bt_result.grade,
            'backtest_score': bt_result.score
        }

        # 유동성 정보 추가
        if bt_result.coin_info:
            data['liquidity'] = {
                'volume_24h': bt_result.coin_info.acc_trade_price_24h,
                'volatility_24h': bt_result.coin_info.volatility_24h,
                'volatility_7d': bt_result.coin_info.volatility_7d,
                'change_rate': bt_result.coin_info.signed_change_rate
            }

        return data

    def _create_candidate(
        self,
        bt_result: BacktestScore,
        entry_signal: Optional[EntrySignal]
    ) -> CoinCandidate:
        """코인 후보 생성"""
        # 최종 점수 계산
        final_score = self._calculate_final_score(bt_result, entry_signal)

        # 최종 등급 결정
        final_grade = self._determine_final_grade(bt_result, entry_signal, final_score)

        # 선택 여부 결정
        selected = self._should_select(bt_result, entry_signal, final_score)

        # 사유 생성
        selection_reason = self._generate_selection_reason(bt_result, entry_signal, selected)

        return CoinCandidate(
            ticker=bt_result.ticker,
            symbol=bt_result.symbol,
            coin_info=bt_result.coin_info,
            backtest_score=bt_result,
            entry_signal=entry_signal,
            final_score=final_score,
            final_grade=final_grade,
            selected=selected,
            selection_reason=selection_reason
        )

    def _calculate_final_score(
        self,
        bt_result: BacktestScore,
        entry_signal: Optional[EntrySignal]
    ) -> float:
        """최종 점수 계산"""
        # 기본 점수: 백테스팅 점수 (60%)
        base_score = bt_result.score * 0.6

        # AI 점수 (40%)
        if entry_signal:
            ai_score = entry_signal.score * 0.4
        else:
            # AI 분석 없으면 백테스팅 등급으로 추정
            if bt_result.grade == "STRONG PASS":
                ai_score = 70 * 0.4
            elif bt_result.grade == "WEAK PASS":
                ai_score = 50 * 0.4
            else:
                ai_score = 30 * 0.4

        return round(base_score + ai_score, 1)

    def _determine_final_grade(
        self,
        bt_result: BacktestScore,
        entry_signal: Optional[EntrySignal],
        final_score: float
    ) -> str:
        """최종 등급 결정"""
        if not bt_result.passed:
            return "FAIL"

        if entry_signal:
            if entry_signal.decision != 'buy':
                return "HOLD"
            if entry_signal.confidence == 'high' and final_score >= 70:
                return "STRONG BUY"
            elif entry_signal.confidence in ['high', 'medium'] and final_score >= 50:
                return "BUY"
            else:
                return "WEAK BUY"
        else:
            # AI 없으면 백테스팅 등급 기반
            if bt_result.grade == "STRONG PASS":
                return "BUY"
            else:
                return "WEAK BUY"

    def _should_select(
        self,
        bt_result: BacktestScore,
        entry_signal: Optional[EntrySignal],
        final_score: float
    ) -> bool:
        """선택 여부 결정"""
        # 백테스팅 미통과면 선택 안함
        if not bt_result.passed:
            return False

        # AI 분석이 있고 buy가 아니면 선택 안함
        if entry_signal and entry_signal.decision != 'buy':
            return False

        # 최종 점수가 50점 이상이면 선택
        return final_score >= 50

    def _generate_selection_reason(
        self,
        bt_result: BacktestScore,
        entry_signal: Optional[EntrySignal],
        selected: bool
    ) -> str:
        """선택/미선택 사유 생성"""
        if not selected:
            if not bt_result.passed:
                return f"백테스팅 미통과: {bt_result.reason}"
            if entry_signal and entry_signal.decision != 'buy':
                return f"AI 거부: {entry_signal.reason}"
            return "점수 미달"

        # 선택된 경우
        reasons = []
        reasons.append(f"백테스팅 {bt_result.grade}")
        if entry_signal:
            reasons.append(f"AI {entry_signal.confidence} 신뢰도")
        return " + ".join(reasons)

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
            ai_analyzed=0,
            candidates=[],
            selected_coins=[],
            total_duration_seconds=(datetime.now() - start_time).total_seconds()
        )

    def _create_result(
        self,
        start_time: datetime,
        liquidity_scanned: int,
        backtest_passed: int,
        ai_analyzed: int,
        candidates: List[CoinCandidate],
        selected_coins: List[CoinCandidate],
        all_backtest_results: Optional[List] = None
    ) -> ScanResult:
        """결과 생성"""
        return ScanResult(
            scan_time=start_time,
            liquidity_scanned=liquidity_scanned,
            backtest_passed=backtest_passed,
            ai_analyzed=ai_analyzed,
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
        print(f"  2. 백테스팅 통과: {result.backtest_passed}개")
        print(f"  3. AI 분석: {result.ai_analyzed}개")
        print(f"  4. 최종 선택: {len(result.selected_coins)}개")
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
