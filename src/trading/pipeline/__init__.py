"""
트레이딩 파이프라인 모듈

파이프라인 아키텍처를 통한 트레이딩 사이클 실행

사용 예시:
    from src.trading.pipeline import create_spot_trading_pipeline, PipelineContext

    # 파이프라인 생성
    pipeline = create_spot_trading_pipeline()

    # 컨텍스트 생성
    context = PipelineContext(
        ticker="KRW-ETH",
        upbit_client=upbit_client,
        data_collector=data_collector,
        trading_service=trading_service,
        ai_service=ai_service
    )

    # 실행
    result = await pipeline.execute(context)
"""
from src.trading.pipeline.base_stage import (
    BasePipelineStage,
    PipelineContext,
    StageResult
)
from src.trading.pipeline.trading_pipeline import (
    TradingPipeline,
    create_spot_trading_pipeline,
    create_futures_trading_pipeline
)

__all__ = [
    'BasePipelineStage',
    'PipelineContext',
    'StageResult',
    'TradingPipeline',
    'create_spot_trading_pipeline',
    'create_futures_trading_pipeline',
]
