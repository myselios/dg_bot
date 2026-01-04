"""
트레이딩 파이프라인 모듈

파이프라인 아키텍처를 통한 트레이딩 사이클 실행

사용 예시:
    from src.trading.pipeline import create_hybrid_trading_pipeline, PipelineContext

    # 하이브리드 파이프라인 생성 (권장)
    # 스캔 활성화 (멀티코인)
    pipeline = create_hybrid_trading_pipeline(enable_scanning=True)

    # 스캔 비활성화 (고정 티커)
    pipeline = create_hybrid_trading_pipeline(enable_scanning=False)

    # 컨텍스트 생성
    context = PipelineContext(
        ticker="KRW-ETH",  # enable_scanning=False 시 사용
        upbit_client=upbit_client,
        data_collector=data_collector,
        trading_service=trading_service,
        ai_service=ai_service
    )

    # 실행
    result = await pipeline.execute(context)

Deprecated:
    - create_spot_trading_pipeline: create_hybrid_trading_pipeline(enable_scanning=False) 사용
    - create_adaptive_trading_pipeline: create_hybrid_trading_pipeline(enable_scanning=False) 사용
    - create_multi_coin_trading_pipeline: create_hybrid_trading_pipeline(enable_scanning=True) 사용
"""
from src.trading.pipeline.base_stage import (
    BasePipelineStage,
    PipelineContext,
    StageResult
)
from src.trading.pipeline.trading_pipeline import (
    TradingPipeline,
    create_hybrid_trading_pipeline,
    create_position_management_pipeline,
    create_spot_trading_pipeline,
    create_futures_trading_pipeline,
    create_adaptive_trading_pipeline
)
from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
# AdaptiveRiskCheckStage 제거됨 - deprecated, HybridRiskCheckStage 사용
from src.trading.pipeline.coin_scan_stage import (
    CoinScanStage,
    create_multi_coin_trading_pipeline
)

__all__ = [
    # Core classes
    'BasePipelineStage',
    'PipelineContext',
    'StageResult',
    'TradingPipeline',
    # Recommended factories
    'create_hybrid_trading_pipeline',
    'create_position_management_pipeline',
    # Deprecated factories (for backward compatibility)
    'create_spot_trading_pipeline',
    'create_futures_trading_pipeline',
    'create_adaptive_trading_pipeline',
    'create_multi_coin_trading_pipeline',
    # Stages
    'HybridRiskCheckStage',
    # 'AdaptiveRiskCheckStage' 제거됨 - deprecated, HybridRiskCheckStage 사용
    'CoinScanStage',
]
