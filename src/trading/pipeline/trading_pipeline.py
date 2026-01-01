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
        파이프라인 실행

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

                # 스테이지 실행
                Logger.print_header(f"▶ {stage.name} 스테이지 실행")
                result = stage.execute(context)

                # 스테이지 실행 후 처리
                stage.post_execute(context, result)

                # 결과 처리
                if not result.success:
                    Logger.print_error(f"❌ {stage.name} 스테이지 실패: {result.message}")
                    return self._create_error_response(result, context)

                # 액션에 따른 처리
                if result.action == 'exit':
                    Logger.print_success(f"✅ {stage.name} 스테이지에서 파이프라인 종료")
                    return self._create_success_response(result, context)

                elif result.action == 'skip':
                    Logger.print_warning(f"⏭️ {stage.name} 스테이지에서 거래 스킵")
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

    def _create_final_response(self, context: PipelineContext) -> Dict[str, Any]:
        """
        최종 응답 생성 (모든 스테이지 완료 시)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            Dict: 최종 응답
        """
        current_price = context.upbit_client.get_current_price(context.ticker)
        coin_balance = context.upbit_client.get_balance(context.ticker)

        return {
            'status': 'success',
            'decision': context.ai_result.get('decision', 'hold') if context.ai_result else 'hold',
            'confidence': context.ai_result.get('confidence', 'medium') if context.ai_result else 'medium',
            'reason': context.ai_result.get('reason', '') if context.ai_result else '',
            'price': current_price,
            'amount': coin_balance,
            'total': current_price * coin_balance if current_price and coin_balance else 0,
            'pipeline_status': 'completed'
        }


def create_spot_trading_pipeline(
    stop_loss_pct: float = -5.0,
    take_profit_pct: float = 10.0,
    daily_loss_limit_pct: float = -10.0,
    min_trade_interval_hours: int = 4
) -> TradingPipeline:
    """
    현물 거래 파이프라인 생성

    Args:
        stop_loss_pct: 손절 비율
        take_profit_pct: 익절 비율
        daily_loss_limit_pct: 일일 최대 손실 비율
        min_trade_interval_hours: 최소 거래 간격

    Returns:
        TradingPipeline: 현물 거래 파이프라인
    """
    from src.trading.pipeline.risk_check_stage import RiskCheckStage
    from src.trading.pipeline.data_collection_stage import DataCollectionStage
    from src.trading.pipeline.analysis_stage import AnalysisStage
    from src.trading.pipeline.execution_stage import ExecutionStage

    stages = [
        RiskCheckStage(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            daily_loss_limit_pct=daily_loss_limit_pct,
            min_trade_interval_hours=min_trade_interval_hours
        ),
        DataCollectionStage(),
        AnalysisStage(),
        ExecutionStage(),
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
