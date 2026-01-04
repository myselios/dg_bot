"""
트레이딩 파이프라인 오케스트레이터

파이프라인 스테이지들을 조합하여 전체 거래 사이클을 실행합니다.
"""
from typing import List, Dict, Any
import traceback
from src.trading.pipeline.base_stage import (
    BasePipelineStage,
    PipelineContext,
    StageResult
)
from src.utils.logger import Logger


class TradingPipeline:
    """
    트레이딩 파이프라인

    여러 스테이지를 순차적으로 실행하여 거래 사이클을 완료합니다.
    각 스테이지는 독립적으로 실행되며, 이전 스테이지의 결과를 컨텍스트로 전달받습니다.
    """

    def __init__(self, stages: List[BasePipelineStage]):
        """
        Args:
            stages: 실행할 스테이지 리스트 (순서대로 실행)
        """
        self.stages = stages

    async def execute(self, context: PipelineContext) -> Dict[str, Any]:
        """
        파이프라인 실행 (비동기)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            Dict: 최종 거래 결과
        """
        Logger.print_header(f"🚀 트레이딩 파이프라인 시작 ({context.ticker})")

        for stage in self.stages:
            try:
                # 스테이지 실행 전 검증
                if not stage.pre_execute(context):
                    Logger.print_warning(f"⏭️ {stage.name} 스테이지 스킵 (pre_execute 실패)")
                    continue

                # 스테이지 실행 (비동기)
                Logger.print_header(f"▶ {stage.name} 스테이지 실행")
                result = await stage.execute(context)

                # 스테이지 실행 후 처리
                stage.post_execute(context, result)

                # 백테스팅 콜백 처리 (스테이지에서 설정한 경우)
                if context.pending_backtest_callback_data and context.on_backtest_complete:
                    try:
                        callback_data = context.pending_backtest_callback_data
                        context.pending_backtest_callback_data = None  # 처리 후 초기화
                        callback_result = context.on_backtest_complete(callback_data)
                        # 코루틴이면 await으로 완료 대기
                        import asyncio
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
                        Logger.print_success("✅ 백테스팅 콜백 전송 완료")
                    except Exception as cb_error:
                        Logger.print_warning(f"⚠️ 백테스팅 콜백 실패: {cb_error}")

                # 결과 처리
                if not result.success:
                    Logger.print_error(f"❌ {stage.name} 스테이지 실패: {result.message}")
                    return self._create_error_response(result, context)

                # 액션에 따른 처리
                if result.action == 'exit':
                    Logger.print_success(f"✅ {stage.name} 스테이지에서 파이프라인 종료")
                    # 종료 전 미처리된 콜백 처리
                    await self._process_pending_callback(context)
                    return self._create_success_response(result, context)

                elif result.action == 'skip':
                    Logger.print_warning(f"⏭️ {stage.name} 스테이지에서 거래 스킵")
                    # 스킵 전 미처리된 콜백 처리
                    await self._process_pending_callback(context)
                    return self._create_success_response(result, context)

                elif result.action == 'stop':
                    Logger.print_error(f"⛔ {stage.name} 스테이지에서 파이프라인 중단")
                    return self._create_error_response(result, context)

                elif result.action == 'continue':
                    Logger.print_success(f"✅ {stage.name} 스테이지 완료 - 다음 단계 진행")
                    continue

            except Exception as e:
                Logger.print_error(f"❌ {stage.name} 스테이지 오류: {str(e)}")
                traceback.print_exc()

                error_result = stage.handle_error(context, e)
                return self._create_error_response(error_result, context)

        # 모든 스테이지 완료
        Logger.print_success("🎉 트레이딩 파이프라인 완료")
        return self._create_final_response(context)

    async def _process_pending_callback(self, context: PipelineContext) -> None:
        """
        미처리된 백테스팅 콜백 처리

        Args:
            context: 파이프라인 컨텍스트
        """
        if context.pending_backtest_callback_data and context.on_backtest_complete:
            try:
                callback_data = context.pending_backtest_callback_data
                context.pending_backtest_callback_data = None  # 처리 후 초기화
                callback_result = context.on_backtest_complete(callback_data)
                # 코루틴이면 await으로 완료 대기
                import asyncio
                if asyncio.iscoroutine(callback_result):
                    await callback_result
                Logger.print_success("✅ 백테스팅 콜백 전송 완료 (파이프라인 종료 시)")
            except Exception as cb_error:
                Logger.print_warning(f"⚠️ 백테스팅 콜백 실패: {cb_error}")

    def _create_success_response(
        self,
        result: StageResult,
        context: PipelineContext
    ) -> Dict[str, Any]:
        """
        성공 응답 생성

        Args:
            result: 스테이지 결과
            context: 파이프라인 컨텍스트

        Returns:
            Dict: 성공 응답
        """
        if result.data:
            return {**result.data, 'pipeline_status': 'completed'}

        return {
            'status': 'success',
            'decision': 'hold',
            'reason': result.message,
            'pipeline_status': 'completed'
        }

    def _create_error_response(
        self,
        result: StageResult,
        context: PipelineContext
    ) -> Dict[str, Any]:
        """
        에러 응답 생성

        Args:
            result: 스테이지 결과
            context: 파이프라인 컨텍스트

        Returns:
            Dict: 에러 응답
        """
        return {
            'status': 'failed',
            'decision': 'hold',
            'reason': result.message,
            'error': result.metadata.get('error', 'Unknown error'),
            'pipeline_status': 'failed'
        }

    def _get_upbit_client(self, context: PipelineContext):
        """context에서 upbit_client 획득 (레거시 호환성)"""
        # 레거시 서비스 직접 사용 (하위 호환성)
        return context.upbit_client

    def _create_final_response(self, context: PipelineContext) -> Dict[str, Any]:
        """
        최종 응답 생성 (모든 스테이지 완료 시)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            Dict: 최종 응답
        """
        upbit_client = self._get_upbit_client(context)
        current_price = upbit_client.get_current_price(context.ticker)
        coin_balance = upbit_client.get_balance(context.ticker)

        response = {
            'status': 'success',
            'decision': context.ai_result.get('decision', 'hold') if context.ai_result else 'hold',
            'confidence': context.ai_result.get('confidence', 'medium') if context.ai_result else 'medium',
            'reason': context.ai_result.get('reason', '') if context.ai_result else '',
            'price': current_price,
            'amount': coin_balance,
            'total': current_price * coin_balance if current_price and coin_balance else 0,
            'pipeline_status': 'completed',
            # Phase 1: SignalAnalyzer 결과 추가
            'signal_analysis': context.signal_analysis if hasattr(context, 'signal_analysis') else None
        }

        # 선택된 코인 정보 포함 (멀티코인 스캐닝 결과)
        if hasattr(context, 'selected_coin') and context.selected_coin:
            response['selected_coin'] = {
                'ticker': context.selected_coin.ticker,
                'symbol': context.selected_coin.symbol,
                'score': context.selected_coin.final_score,
                'grade': getattr(context.selected_coin, 'final_grade', ''),
                'reason': getattr(context.selected_coin, 'selection_reason', '')
            }

        # 백테스팅 콜백 데이터에서 scan_summary, all_backtest_results 추출
        if hasattr(context, 'pending_backtest_callback_data') and context.pending_backtest_callback_data:
            callback_data = context.pending_backtest_callback_data
            if 'scan_summary' in callback_data:
                response['scan_summary'] = callback_data['scan_summary']
            if 'all_backtest_results' in callback_data:
                response['all_backtest_results'] = callback_data['all_backtest_results']

        return response


def create_hybrid_trading_pipeline(
    # 리스크 파라미터
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    daily_loss_limit_pct: float = -10.0,
    min_trade_interval_hours: int = 4,
    max_positions: int = 3,
    # 스캔 파라미터
    enable_scanning: bool = True,
    fallback_ticker: str = "KRW-ETH",
    liquidity_top_n: int = 10,
    min_volume_krw: float = 10_000_000_000,
    backtest_top_n: int = 5,
    final_select_n: int = 2,
    # 진입 모드 파라미터 (Phase 1: 신호 기반 진입)
    entry_mode: bool = True  # True: AI 스킵, SignalAnalyzer만 사용
) -> TradingPipeline:
    """
    통합 하이브리드 트레이딩 파이프라인 생성

    Mode 2(적응형)와 Mode 3(멀티코인)을 통합한 단일 파이프라인입니다.
    포지션 유무에 따라 ENTRY/MANAGEMENT 모드로 분기하고,
    ENTRY 모드에서는 선택적으로 코인 스캔을 수행합니다.

    흐름:
    1. HybridRiskCheckStage: 포지션 확인 + 모드 분기 + 코인 스캔 (옵션)
       - BLOCKED: 즉시 종료
       - MANAGEMENT: 포지션 관리 (규칙 + AI 하이브리드)
       - ENTRY + 스캔 활성화: 코인 스캔 후 동적 티커
       - ENTRY + 스캔 비활성화: 고정 티커 사용
    2. DataCollectionStage: 데이터 수집
    3. AnalysisStage: 진입 분석 (ENTRY 모드에서만)
    4. ExecutionStage: 거래 실행

    Args:
        stop_loss_pct: 손절 비율 (기본 -5%)
        take_profit_pct: 익절 비율 (기본 +10%)
        daily_loss_limit_pct: 일일 최대 손실 비율 (기본 -10%)
        min_trade_interval_hours: 최소 거래 간격 (기본 4시간)
        max_positions: 최대 동시 포지션 수 (기본 3개)
        enable_scanning: 코인 스캔 활성화 여부 (기본 True)
        fallback_ticker: 스캔 비활성화 또는 실패 시 사용할 티커 (기본 "KRW-ETH")
        liquidity_top_n: 유동성 스캔 상위 N개 (기본 10)
        min_volume_krw: 최소 거래대금 (기본 100억원)
        backtest_top_n: 백테스팅 통과 상위 N개 (기본 5)
        final_select_n: 최종 선택 N개 (기본 2)

    Returns:
        TradingPipeline: 통합 하이브리드 트레이딩 파이프라인
    """
    from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
    from src.trading.pipeline.data_collection_stage import DataCollectionStage
    from src.trading.pipeline.analysis_stage import AnalysisStage
    from src.trading.pipeline.execution_stage import ExecutionStage

    # 스캐너 설정
    scanner_config = {
        'liquidity_top_n': liquidity_top_n,
        'min_volume_krw': min_volume_krw,
        'backtest_top_n': backtest_top_n,
        'final_select_n': final_select_n
    }

    stages = [
        HybridRiskCheckStage(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            daily_loss_limit_pct=daily_loss_limit_pct,
            min_trade_interval_hours=min_trade_interval_hours,
            max_positions=max_positions,
            enable_scanning=enable_scanning,
            fallback_ticker=fallback_ticker,
            scanner_config=scanner_config
        ),
        DataCollectionStage(),
        AnalysisStage(entry_mode=entry_mode),  # Phase 1: entry_mode=True → AI 스킵
        ExecutionStage(),
    ]

    return TradingPipeline(stages=stages)


def create_spot_trading_pipeline(
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    daily_loss_limit_pct: float = -10.0,
    min_trade_interval_hours: int = 4
) -> TradingPipeline:
    """
    현물 거래 파이프라인 생성

    .. deprecated::
        이 함수는 deprecated 되었습니다.
        대신 create_hybrid_trading_pipeline(enable_scanning=False)를 사용하세요.

    Args:
        stop_loss_pct: 손절 비율
        take_profit_pct: 익절 비율
        daily_loss_limit_pct: 일일 최대 손실 비율
        min_trade_interval_hours: 최소 거래 간격

    Returns:
        TradingPipeline: 현물 거래 파이프라인
    """
    import warnings
    warnings.warn(
        "create_spot_trading_pipeline is deprecated. "
        "Use create_hybrid_trading_pipeline(enable_scanning=False) instead.",
        DeprecationWarning,
        stacklevel=2
    )

    return create_hybrid_trading_pipeline(
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        daily_loss_limit_pct=daily_loss_limit_pct,
        min_trade_interval_hours=min_trade_interval_hours,
        max_positions=1,
        enable_scanning=False,
        fallback_ticker="KRW-ETH"
    )


def create_position_management_pipeline(
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    max_positions: int = 3
) -> TradingPipeline:
    """
    포지션 관리 전용 파이프라인 생성 (15분 주기용)

    진입 로직 없이 기존 포지션의 손절/익절만 관리합니다.
    포지션이 없으면 즉시 종료합니다.

    Args:
        stop_loss_pct: 손절 비율 (기본 -5%)
        take_profit_pct: 익절 비율 (기본 +10%)
        max_positions: 최대 동시 포지션 수 (기본 3개)

    Returns:
        TradingPipeline: 포지션 관리 전용 파이프라인
    """
    from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

    # 포지션 관리 전용 스테이지만 사용 (진입 로직 없음)
    stages = [
        HybridRiskCheckStage(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            daily_loss_limit_pct=-10.0,
            min_trade_interval_hours=0,  # 관리는 간격 제한 없음
            max_positions=max_positions,
            enable_scanning=False,  # 스캔 비활성화 (관리만)
            fallback_ticker="KRW-BTC"  # 사용되지 않음
        ),
    ]

    return TradingPipeline(stages=stages)


def create_futures_trading_pipeline(
    # TODO: 선물 거래 전용 파라미터 추가
    leverage: int = 1,
    **kwargs
) -> TradingPipeline:
    """
    선물 거래 파이프라인 생성 (미래 구현)

    Args:
        leverage: 레버리지
        **kwargs: 기타 리스크 관리 파라미터

    Returns:
        TradingPipeline: 선물 거래 파이프라인
    """
    # TODO: 선물 거래용 스테이지 구현 후 교체
    # - FuturesRiskCheckStage (레버리지 고려)
    # - FuturesDataCollectionStage (펀딩비, 미결제약정 등)
    # - FuturesExecutionStage (롱/숏 포지션 관리)

    raise NotImplementedError("선물 거래 파이프라인은 아직 구현되지 않았습니다.")


def create_adaptive_trading_pipeline(
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    daily_loss_limit_pct: float = -10.0,
    min_trade_interval_hours: int = 4,
    max_positions: int = 3
) -> TradingPipeline:
    """
    적응형 트레이딩 파이프라인 생성

    .. deprecated::
        이 함수는 deprecated 되었습니다.
        대신 create_hybrid_trading_pipeline(enable_scanning=False)를 사용하세요.

    Args:
        stop_loss_pct: 손절 비율
        take_profit_pct: 익절 비율
        daily_loss_limit_pct: 일일 최대 손실 비율
        min_trade_interval_hours: 최소 거래 간격
        max_positions: 최대 동시 포지션 수

    Returns:
        TradingPipeline: 적응형 트레이딩 파이프라인
    """
    import warnings
    warnings.warn(
        "create_adaptive_trading_pipeline is deprecated. "
        "Use create_hybrid_trading_pipeline(enable_scanning=False) instead.",
        DeprecationWarning,
        stacklevel=2
    )

    return create_hybrid_trading_pipeline(
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        daily_loss_limit_pct=daily_loss_limit_pct,
        min_trade_interval_hours=min_trade_interval_hours,
        max_positions=max_positions,
        enable_scanning=False,
        fallback_ticker="KRW-ETH"
    )
