"""
코인 스캔 스테이지 (Coin Scan Stage)

멀티코인 스캐닝을 파이프라인에 통합합니다.

ENTRY 모드에서 실행되며:
1. 유동성 상위 코인 스캔
2. 병렬 백테스팅
3. 최적 코인 선택
4. 컨텍스트에 선택된 코인 저장

Note:
    이 스테이지는 HybridRiskCheckStage에 통합되어 deprecated 예정입니다.
    새 코드에서는 HybridRiskCheckStage를 사용하세요.
"""
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, List

from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.scanner.coin_selector import CoinSelector, ScanResult
from src.scanner.liquidity_scanner import LiquidityScanner
from src.scanner.data_sync import HistoricalDataSync
from src.scanner.multi_backtest import MultiCoinBacktest, MultiBacktestConfig
from src.utils.logger import Logger


def run_async_safely(coro):
    """
    비동기 코루틴을 안전하게 동기적으로 실행

    이벤트 루프 상태에 따라 적절한 방법을 선택합니다:
    - 루프가 없으면: asyncio.run() 사용
    - 루프가 실행 중이면: ThreadPoolExecutor로 별도 스레드에서 실행

    Args:
        coro: 실행할 코루틴

    Returns:
        코루틴 실행 결과
    """
    try:
        # 실행 중인 루프가 있는지 확인
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 루프가 없으면 새로 생성하여 실행
        return asyncio.run(coro)

    # 루프가 실행 중이면 별도 스레드에서 실행
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result(timeout=180)  # 3분 타임아웃


class CoinScanStage(BasePipelineStage):
    """
    코인 스캔 스테이지

    ENTRY 모드에서 최적의 진입 코인을 선택합니다.

    흐름:
    1. 포트폴리오에서 이미 보유 중인 코인 확인
    2. 유동성 상위 코인 스캔
    3. 병렬 백테스팅으로 필터링
    4. 최적 코인 선택 (상위 N개)
    5. 컨텍스트에 선택된 코인 저장
    """

    def __init__(
        self,
        liquidity_top_n: int = 20,
        min_volume_krw: float = 10_000_000_000,
        backtest_top_n: int = 5,
        final_select_n: int = 2,
        data_dir: str = "./data/historical",
        backtest_config: Optional[MultiBacktestConfig] = None
    ):
        """
        Args:
            liquidity_top_n: 유동성 스캔 상위 N개
            min_volume_krw: 최소 거래대금 (KRW)
            backtest_top_n: 백테스팅 통과 상위 N개
            final_select_n: 최종 선택 N개
            data_dir: 과거 데이터 저장 디렉토리
            backtest_config: 백테스팅 설정
        """
        super().__init__(name="CoinScan")
        self.liquidity_top_n = liquidity_top_n
        self.min_volume_krw = min_volume_krw
        self.backtest_top_n = backtest_top_n
        self.final_select_n = final_select_n
        self.data_dir = data_dir
        self.backtest_config = backtest_config

        # 컴포넌트 초기화 (지연 로딩)
        self._coin_selector: Optional[CoinSelector] = None

    def pre_execute(self, context: PipelineContext) -> bool:
        """
        스테이지 실행 전 검증

        ENTRY 모드에서만 실행됩니다.
        """
        # ENTRY 모드인지 확인
        trading_mode = getattr(context, 'trading_mode', None)
        if trading_mode != 'entry':
            Logger.print_info(f"⏭️ 코인 스캔 스킵 (모드: {trading_mode})")
            return False

        return True

    def execute(self, context: PipelineContext) -> StageResult:
        """
        코인 스캔 실행

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 실행 결과
        """
        try:
            Logger.print_header("🔍 멀티코인 스캐닝")

            # 1. 이미 보유 중인 코인 목록
            exclude_tickers = self._get_held_tickers(context)
            Logger.print_info(f"보유 중인 코인: {exclude_tickers}")

            # 2. 코인 선택기 초기화
            selector = self._get_coin_selector()

            # 3. 코인 선택 실행 (개선된 동기 래퍼)
            scan_result = run_async_safely(
                selector.select_coins(exclude_tickers=exclude_tickers)
            )

            # 4. 결과 처리
            if not scan_result.selected_coins:
                Logger.print_warning("선택된 코인 없음")
                return StageResult(
                    success=True,
                    action='skip',
                    data={
                        'status': 'success',
                        'decision': 'hold',
                        'reason': '스캔 결과 진입 적합 코인 없음',
                        'scan_result': {
                            'liquidity_scanned': scan_result.liquidity_scanned,
                            'backtest_passed': scan_result.backtest_passed,
                            'selected': 0
                        }
                    },
                    message="진입 적합 코인 없음"
                )

            # 5. 컨텍스트에 선택된 코인 저장
            selected_coin = scan_result.selected_coins[0]  # 최상위 코인
            context.scanned_coins = scan_result.selected_coins
            context.selected_coin = selected_coin
            context.ticker = selected_coin.ticker  # 티커 업데이트

            Logger.print_success(f"✅ 선택된 코인: {selected_coin.symbol} ({selected_coin.final_score:.1f}점)")

            return StageResult(
                success=True,
                action='continue',
                data={
                    'selected_coin': {
                        'ticker': selected_coin.ticker,
                        'symbol': selected_coin.symbol,
                        'score': selected_coin.final_score,
                        'grade': selected_coin.final_grade,
                        'reason': selected_coin.selection_reason
                    },
                    'scan_summary': {
                        'liquidity_scanned': scan_result.liquidity_scanned,
                        'backtest_passed': scan_result.backtest_passed,
                        'ai_analyzed': scan_result.ai_analyzed,
                        'selected': len(scan_result.selected_coins),
                        'duration_seconds': scan_result.total_duration_seconds
                    }
                },
                message=f"코인 선택 완료: {selected_coin.symbol}"
            )

        except Exception as e:
            return self.handle_error(context, e)

    def _get_held_tickers(self, context: PipelineContext) -> List[str]:
        """보유 중인 코인 티커 목록 조회"""
        exclude = []

        # 포트폴리오 매니저에서 보유 코인 조회
        if hasattr(context, 'portfolio_status') and context.portfolio_status:
            for pos in context.portfolio_status.positions:
                exclude.append(pos.ticker)

        # 현재 분석 중인 코인도 제외
        if context.ticker:
            exclude.append(context.ticker)

        return list(set(exclude))

    def _get_coin_selector(self) -> CoinSelector:
        """코인 선택기 반환 (지연 초기화)"""
        if self._coin_selector is None:
            liquidity_scanner = LiquidityScanner(
                min_volume_krw=self.min_volume_krw
            )
            data_sync = HistoricalDataSync(
                data_dir=self.data_dir
            )
            multi_backtest = MultiCoinBacktest(
                config=self.backtest_config,
                data_sync=data_sync
            )

            self._coin_selector = CoinSelector(
                liquidity_scanner=liquidity_scanner,
                data_sync=data_sync,
                multi_backtest=multi_backtest,
                entry_analyzer=None,  # AI 분석은 다음 스테이지에서
                liquidity_top_n=self.liquidity_top_n,
                min_volume_krw=self.min_volume_krw,
                backtest_top_n=self.backtest_top_n,
                ai_top_n=0,  # 이 스테이지에서는 AI 분석 안함
                final_select_n=self.final_select_n
            )

        return self._coin_selector


def create_multi_coin_trading_pipeline(
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    daily_loss_limit_pct: float = -10.0,
    min_trade_interval_hours: int = 4,
    max_positions: int = 3,
    liquidity_top_n: int = 20,
    min_volume_krw: float = 10_000_000_000,
    backtest_top_n: int = 5,
    final_select_n: int = 2
) -> 'TradingPipeline':
    """
    멀티코인 트레이딩 파이프라인 생성

    .. deprecated::
        이 함수는 deprecated 되었습니다.
        대신 create_hybrid_trading_pipeline(enable_scanning=True)를 사용하세요.

    Args:
        stop_loss_pct: 손절 비율
        take_profit_pct: 익절 비율
        daily_loss_limit_pct: 일일 최대 손실 비율
        min_trade_interval_hours: 최소 거래 간격
        max_positions: 최대 동시 포지션 수
        liquidity_top_n: 유동성 스캔 상위 N개
        min_volume_krw: 최소 거래대금
        backtest_top_n: 백테스팅 통과 상위 N개
        final_select_n: 최종 선택 N개

    Returns:
        TradingPipeline: 멀티코인 트레이딩 파이프라인
    """
    import warnings
    from src.trading.pipeline.trading_pipeline import create_hybrid_trading_pipeline

    warnings.warn(
        "create_multi_coin_trading_pipeline is deprecated. "
        "Use create_hybrid_trading_pipeline(enable_scanning=True) instead.",
        DeprecationWarning,
        stacklevel=2
    )

    return create_hybrid_trading_pipeline(
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        daily_loss_limit_pct=daily_loss_limit_pct,
        min_trade_interval_hours=min_trade_interval_hours,
        max_positions=max_positions,
        enable_scanning=True,
        fallback_ticker="KRW-ETH",
        liquidity_top_n=liquidity_top_n,
        min_volume_krw=min_volume_krw,
        backtest_top_n=backtest_top_n,
        final_select_n=final_select_n
    )
