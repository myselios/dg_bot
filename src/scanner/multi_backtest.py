"""
멀티코인 병렬 백테스팅 (Multi-Coin Parallel Backtest)

여러 코인에 대해 병렬로 백테스팅을 실행하여
진입 후보를 필터링합니다.

주요 기능:
- 병렬 백테스팅 실행 (비동기)
- Research Pass 기준 필터링 (느슨한 기준으로 후보 확보)
- 점수 기반 순위화

⚠️ 2026-01-04 변경: MultiBacktestConfig 제거, ResearchPassConfig 사용
- 설정 중복 제거 및 단일 소스 원칙 적용
- Research Pass 기준으로 후보 선별 (30-50% 통과율 목표)
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from src.backtesting.runner import BacktestRunner
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
from src.backtesting.backtester import BacktestResult
from src.backtesting.quick_filter import ResearchPassConfig  # ⚠️ 통합된 Config 사용
from src.scanner.data_sync import HistoricalDataSync
from src.scanner.liquidity_scanner import CoinInfo
from src.utils.logger import Logger


@dataclass
class BacktestScore:
    """백테스팅 점수 및 결과"""
    ticker: str
    symbol: str
    passed: bool                          # 필터 통과 여부
    score: float                          # 종합 점수 (0-100)
    grade: str                            # 등급 (STRONG PASS, WEAK PASS, FAIL)
    metrics: Dict[str, Any]               # 성능 지표
    filter_results: Dict[str, bool]       # 개별 필터 결과
    reason: str                           # 통과/실패 사유
    backtest_result: Optional[BacktestResult] = None
    coin_info: Optional[CoinInfo] = None  # 유동성 정보
    backtest_time: datetime = field(default_factory=datetime.now)
    pass_type: str = "research"           # 통과한 Pass 타입 (research/trading)


@dataclass
class MultiBacktestConfig:
    """
    멀티코인 백테스팅 설정 (DEPRECATED - ResearchPassConfig 사용 권장)

    ⚠️ 하위 호환성을 위해 유지되지만, 내부적으로 ResearchPassConfig 값 사용
    새 코드에서는 ResearchPassConfig를 직접 사용하세요.
    """
    # 백테스팅 파라미터 (ResearchPassConfig와 동기화)
    initial_capital: float = 10_000_000
    commission: float = 0.0005
    slippage: float = 0.0001
    days: int = 730
    interval: str = "day"

    # Research Pass 기준 사용 (느슨한 기준)
    min_return: float = 8.0               # Research 기준
    min_win_rate: float = 30.0            # Research 기준
    min_profit_factor: float = 1.3        # Research 기준
    min_sharpe_ratio: float = 0.4         # Research 기준
    min_sortino_ratio: float = 0.5        # Research 기준
    min_calmar_ratio: float = 0.25        # Research 기준
    max_drawdown: float = 30.0            # Research 기준
    max_consecutive_losses: int = 8       # Research 기준
    max_volatility: float = 100.0         # Research 기준
    min_trades: int = 10                  # Research 기준 (ResearchPassConfig와 동기화)
    min_avg_win_loss_ratio: float = 1.0   # Research 기준 (연동 필터로 대체)
    max_avg_holding_hours: float = 336.0  # Research 기준

    # 점수 가중치
    weight_return: float = 0.20
    weight_win_rate: float = 0.10
    weight_profit_factor: float = 0.20
    weight_sharpe: float = 0.25
    weight_drawdown: float = 0.15
    weight_sortino: float = 0.10

    @classmethod
    def from_research_config(cls) -> 'MultiBacktestConfig':
        """ResearchPassConfig에서 생성 (권장)"""
        rc = ResearchPassConfig()
        return cls(
            initial_capital=rc.initial_capital,
            commission=rc.commission,
            slippage=rc.slippage,
            days=rc.days,
            min_return=rc.min_return,
            min_win_rate=rc.min_win_rate,
            min_profit_factor=rc.min_profit_factor,
            min_sharpe_ratio=rc.min_sharpe_ratio,
            min_sortino_ratio=rc.min_sortino_ratio,
            min_calmar_ratio=rc.min_calmar_ratio,
            max_drawdown=rc.max_drawdown,
            max_consecutive_losses=rc.max_consecutive_losses,
            max_volatility=rc.max_volatility,
            min_trades=rc.min_trades,
            min_avg_win_loss_ratio=rc.min_avg_win_loss_ratio,
            max_avg_holding_hours=rc.max_avg_holding_hours,
        )


class MultiCoinBacktest:
    """
    멀티코인 병렬 백테스팅

    여러 코인에 대해 병렬로 백테스팅을 실행합니다.

    사용 예시:
        backtest = MultiCoinBacktest()
        results = await backtest.run_parallel_backtest(
            coin_list=["KRW-BTC", "KRW-ETH", ...],
            top_n=5
        )
        for result in results:
            print(f"{result.symbol}: {result.score:.1f}점 ({result.grade})")
    """

    def __init__(
        self,
        config: Optional[MultiBacktestConfig] = None,
        data_sync: Optional[HistoricalDataSync] = None,
        max_workers: int = 4
    ):
        """
        Args:
            config: 백테스팅 설정
            data_sync: 데이터 동기화 관리자
            max_workers: 병렬 처리 워커 수
        """
        self.config = config or MultiBacktestConfig()
        self.data_sync = data_sync or HistoricalDataSync()
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def run_parallel_backtest(
        self,
        coin_list: List[str],
        coin_infos: Optional[Dict[str, CoinInfo]] = None,
        top_n: int = 5,
        filter_criteria: Optional[Dict] = None
    ) -> List[BacktestScore]:
        """
        병렬 백테스팅 실행

        Args:
            coin_list: 코인 티커 목록
            coin_infos: 코인 정보 딕셔너리 (유동성 데이터 포함)
            top_n: 반환할 상위 코인 수
            filter_criteria: 커스텀 필터 기준 (None이면 config 사용)

        Returns:
            BacktestScore 리스트 (점수 순 정렬)
        """
        Logger.print_header(f"🔬 멀티코인 백테스팅 ({len(coin_list)}개 코인)")

        # 필터 기준 설정
        criteria = self._get_filter_criteria(filter_criteria)

        # 병렬 백테스팅 실행
        tasks = []
        for ticker in coin_list:
            coin_info = coin_infos.get(ticker) if coin_infos else None
            task = self._run_single_backtest(ticker, coin_info, criteria)
            tasks.append(task)

        # 모든 태스크 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 처리
        valid_results = []
        for ticker, result in zip(coin_list, results):
            if isinstance(result, Exception):
                Logger.print_warning(f"  [{ticker}] 백테스팅 실패: {str(result)}")
                valid_results.append(BacktestScore(
                    ticker=ticker,
                    symbol=ticker.replace("KRW-", ""),
                    passed=False,
                    score=0.0,
                    grade="FAIL",
                    metrics={},
                    filter_results={},
                    reason=f"백테스팅 실패: {str(result)}"
                ))
            else:
                valid_results.append(result)

        # 점수 순 정렬 및 상위 N개 추출
        valid_results.sort(key=lambda x: x.score, reverse=True)
        top_results = valid_results[:top_n]

        # 결과 요약
        passed_count = sum(1 for r in valid_results if r.passed)
        Logger.print_info(f"\n📊 백테스팅 완료: 통과 {passed_count}/{len(valid_results)}")

        return top_results

    async def _run_single_backtest(
        self,
        ticker: str,
        coin_info: Optional[CoinInfo],
        criteria: Dict
    ) -> BacktestScore:
        """단일 코인 백테스팅 실행"""
        symbol = ticker.replace("KRW-", "")
        Logger.print_info(f"  [{symbol}] 백테스팅 중...")

        try:
            # 데이터 로드
            df = self.data_sync.load_data(ticker, self.config.interval)

            if df is None or len(df) < 30:
                return BacktestScore(
                    ticker=ticker,
                    symbol=symbol,
                    passed=False,
                    score=0.0,
                    grade="FAIL",
                    metrics={},
                    filter_results={},
                    reason="데이터 부족 (최소 30일 필요)",
                    coin_info=coin_info
                )

            # 최근 N일 데이터만 사용
            df = df.tail(self.config.days).copy()

            # 백테스팅 실행 (ThreadPoolExecutor로 동기 함수 실행)
            loop = asyncio.get_event_loop()
            backtest_result = await loop.run_in_executor(
                self._executor,
                self._execute_backtest,
                ticker,
                df
            )

            # 메트릭 추출
            metrics = backtest_result.metrics

            # 필터링
            filter_results = self._check_filters(metrics, criteria)
            passed = all(filter_results.values())

            # 점수 계산
            score = self._calculate_score(metrics)

            # 등급 결정
            grade = self._determine_grade(score, passed)

            # 사유 생성
            reason = self._generate_reason(metrics, filter_results, passed)

            result = BacktestScore(
                ticker=ticker,
                symbol=symbol,
                passed=passed,
                score=score,
                grade=grade,
                metrics=metrics,
                filter_results=filter_results,
                reason=reason,
                backtest_result=backtest_result,
                coin_info=coin_info
            )

            # 간단한 결과 로그
            status = "✅" if passed else "❌"
            Logger.print_info(f"  [{symbol}] {status} 점수: {score:.1f} ({grade})")

            return result

        except Exception as e:
            Logger.print_warning(f"  [{symbol}] 오류: {str(e)}")
            return BacktestScore(
                ticker=ticker,
                symbol=symbol,
                passed=False,
                score=0.0,
                grade="FAIL",
                metrics={},
                filter_results={},
                reason=f"오류: {str(e)}",
                coin_info=coin_info
            )

    def _execute_backtest(self, ticker: str, df: pd.DataFrame) -> BacktestResult:
        """백테스팅 실행 (동기 함수)"""
        strategy = RuleBasedBreakoutStrategy(
            ticker=ticker,
            risk_per_trade=0.02,
            max_position_size=0.3
        )

        return BacktestRunner.run_backtest(
            strategy=strategy,
            data=df,
            ticker=ticker,
            initial_capital=self.config.initial_capital,
            commission=self.config.commission,
            slippage=self.config.slippage
        )

    def _get_filter_criteria(self, custom_criteria: Optional[Dict]) -> Dict:
        """필터 기준 반환 (퀀트 기준 12가지 조건)"""
        if custom_criteria:
            return custom_criteria

        return {
            # 1. 수익성 지표
            'min_return': self.config.min_return,
            'min_win_rate': self.config.min_win_rate,
            'min_profit_factor': self.config.min_profit_factor,
            # 2. 위험조정 수익률
            'min_sharpe_ratio': self.config.min_sharpe_ratio,
            'min_sortino_ratio': self.config.min_sortino_ratio,
            'min_calmar_ratio': self.config.min_calmar_ratio,
            # 3. 리스크 관리
            'max_drawdown': self.config.max_drawdown,
            'max_consecutive_losses': self.config.max_consecutive_losses,
            'max_volatility': self.config.max_volatility,
            # 4. 통계적 유의성
            'min_trades': self.config.min_trades,
            # 5. 거래 품질
            'min_avg_win_loss_ratio': self.config.min_avg_win_loss_ratio,
            'max_avg_holding_hours': self.config.max_avg_holding_hours,
        }

    def _check_filters(self, metrics: Dict, criteria: Dict) -> Dict[str, bool]:
        """필터 조건 체크 (퀀트/헤지펀드 기준 12가지)"""
        # 지표 추출
        total_return = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        sortino_ratio = metrics.get('sortino_ratio', 0)
        calmar_ratio = metrics.get('calmar_ratio', 0)
        max_dd = abs(metrics.get('max_drawdown', 0))
        volatility = metrics.get('volatility', 0)
        max_consecutive_losses = metrics.get('max_consecutive_losses', 0)
        total_trades = metrics.get('total_trades', 0)
        avg_win = metrics.get('avg_win', 0)
        avg_loss = abs(metrics.get('avg_loss', 1))  # 0 방지
        avg_holding_hours = metrics.get('avg_holding_period_hours', 0)

        # 평균 수익/손실 비율 계산
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        return {
            # 1. 수익성 지표 (Profitability)
            'return': total_return >= criteria.get('min_return', 0),
            'win_rate': win_rate >= criteria.get('min_win_rate', 0),
            'profit_factor': profit_factor >= criteria.get('min_profit_factor', 0),

            # 2. 위험조정 수익률 (Risk-Adjusted Returns)
            'sharpe_ratio': sharpe_ratio >= criteria.get('min_sharpe_ratio', 0),
            'sortino_ratio': sortino_ratio >= criteria.get('min_sortino_ratio', 0),
            'calmar_ratio': calmar_ratio >= criteria.get('min_calmar_ratio', 0),

            # 3. 리스크 관리 (Risk Management)
            'max_drawdown': max_dd <= criteria.get('max_drawdown', 100),
            'max_consecutive_losses': max_consecutive_losses <= criteria.get('max_consecutive_losses', 100),
            'volatility': volatility <= criteria.get('max_volatility', 100),

            # 4. 통계적 유의성 (Statistical Significance)
            'min_trades': total_trades >= criteria.get('min_trades', 0),

            # 5. 거래 품질 (Trade Quality)
            'avg_win_loss_ratio': avg_win_loss_ratio >= criteria.get('min_avg_win_loss_ratio', 0),
            'avg_holding_hours': avg_holding_hours <= criteria.get('max_avg_holding_hours', 1000),
        }

    def _calculate_score(self, metrics: Dict) -> float:
        """종합 점수 계산 (0-100) - 퀀트 기준"""
        # 각 지표 정규화 (0-100 범위로)
        total_return = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        sortino_ratio = metrics.get('sortino_ratio', 0)
        max_dd = abs(metrics.get('max_drawdown', 0))

        # 수익률: 0-30% → 0-100 (2년 기준)
        return_score = min(100, max(0, total_return * 3.33))

        # 승률: 30-60% → 0-100
        win_rate_score = min(100, max(0, (win_rate - 30) * 3.33))

        # 손익비: 1.0-3.0 → 0-100
        pf_score = min(100, max(0, (profit_factor - 1.0) * 50))

        # 샤프 비율: 0-2.0 → 0-100 (가장 중요)
        sharpe_score = min(100, max(0, sharpe_ratio * 50))

        # 소르티노 비율: 0-2.5 → 0-100
        sortino_score = min(100, max(0, sortino_ratio * 40))

        # 낙폭: 0-20% → 100-0 (낮을수록 좋음)
        dd_score = max(0, 100 - (max_dd * 5))

        # 가중 평균 (샤프 비율 중시)
        score = (
            return_score * self.config.weight_return +
            win_rate_score * self.config.weight_win_rate +
            pf_score * self.config.weight_profit_factor +
            sharpe_score * self.config.weight_sharpe +
            dd_score * self.config.weight_drawdown +
            sortino_score * self.config.weight_sortino
        )

        return round(score, 1)

    def _determine_grade(self, score: float, passed: bool) -> str:
        """등급 결정"""
        if not passed:
            return "FAIL"
        elif score >= 70:
            return "STRONG PASS"
        else:
            return "WEAK PASS"

    def _generate_reason(
        self,
        metrics: Dict,
        filter_results: Dict[str, bool],
        passed: bool
    ) -> str:
        """통과/실패 사유 생성"""
        if passed:
            total_return = metrics.get('total_return', 0)
            profit_factor = metrics.get('profit_factor', 0)
            return f"수익률 {total_return:.1f}%, 손익비 {profit_factor:.2f}"

        # 실패 사유
        failed = []
        if not filter_results.get('return', True):
            failed.append(f"수익률 {metrics.get('total_return', 0):.1f}%")
        if not filter_results.get('win_rate', True):
            failed.append(f"승률 {metrics.get('win_rate', 0):.1f}%")
        if not filter_results.get('profit_factor', True):
            failed.append(f"손익비 {metrics.get('profit_factor', 0):.2f}")
        if not filter_results.get('sharpe_ratio', True):
            failed.append(f"샤프 {metrics.get('sharpe_ratio', 0):.2f}")
        if not filter_results.get('max_drawdown', True):
            failed.append(f"MDD {abs(metrics.get('max_drawdown', 0)):.1f}%")
        if not filter_results.get('min_trades', True):
            failed.append(f"거래 {metrics.get('total_trades', 0)}회")

        return f"미달: {', '.join(failed)}"

    def print_results(self, results: List[BacktestScore]) -> None:
        """백테스팅 결과 출력"""
        Logger.print_header("🏆 백테스팅 순위")

        print(f"{'순위':>4} {'심볼':>8} {'점수':>8} {'등급':>12} {'수익률':>10} {'승률':>8} {'손익비':>8} {'MDD':>8}")
        print("-" * 85)

        for i, result in enumerate(results, 1):
            grade_icon = "🟢" if result.grade == "STRONG PASS" else ("🟡" if result.grade == "WEAK PASS" else "🔴")
            total_return = result.metrics.get('total_return', 0)
            win_rate = result.metrics.get('win_rate', 0)
            profit_factor = result.metrics.get('profit_factor', 0)
            max_dd = abs(result.metrics.get('max_drawdown', 0))

            print(f"{i:>4} {result.symbol:>8} {result.score:>8.1f} {grade_icon} {result.grade:>10} "
                  f"{total_return:>9.1f}% {win_rate:>7.1f}% {profit_factor:>8.2f} {max_dd:>7.1f}%")

    def close(self):
        """리소스 정리"""
        self._executor.shutdown(wait=False)
