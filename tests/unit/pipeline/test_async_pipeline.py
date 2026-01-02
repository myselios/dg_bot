"""
비동기 파이프라인 테스트

Phase 1: 파이프라인 비동기화를 위한 테스트 코드
- BasePipelineStage.execute()가 async로 동작하는지 확인
- TradingPipeline.execute()가 async로 동작하는지 확인
- 모든 스테이지가 async execute를 지원하는지 확인
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Any

# 테스트 대상 모듈
from src.trading.pipeline.base_stage import (
    BasePipelineStage,
    PipelineContext,
    StageResult
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_upbit_client():
    """Mock UpbitClient"""
    client = Mock()
    client.get_balance = Mock(return_value=1000000.0)
    client.get_current_price = Mock(return_value=50000000.0)
    client.get_balances = Mock(return_value=[])
    return client


@pytest.fixture
def mock_data_collector():
    """Mock DataCollector"""
    collector = Mock()
    collector.get_chart_data = Mock(return_value={
        'day': [],
        'minute60': []
    })
    collector.get_chart_data_with_btc = Mock(return_value={
        'eth': {'day': [], 'minute60': []},
        'btc': {'day': [], 'minute60': []}
    })
    collector.get_orderbook = Mock(return_value={})
    collector.get_orderbook_summary = Mock(return_value={})
    collector.get_fear_greed_index = Mock(return_value={'value': 50, 'classification': 'Neutral'})
    return collector


@pytest.fixture
def mock_trading_service():
    """Mock TradingService"""
    service = Mock()
    service.execute_buy = Mock(return_value={'success': True, 'trade_id': 'test-123'})
    service.execute_sell = Mock(return_value={'success': True, 'trade_id': 'test-456'})
    service.execute_hold = Mock()
    return service


@pytest.fixture
def mock_ai_service():
    """Mock AIService"""
    service = Mock()
    service.analyze = Mock(return_value={
        'decision': 'hold',
        'confidence': 'medium',
        'reason': 'Test reason'
    })
    service.prepare_analysis_data = Mock(return_value={})
    return service


@pytest.fixture
def pipeline_context(mock_upbit_client, mock_data_collector, mock_trading_service, mock_ai_service):
    """PipelineContext fixture"""
    return PipelineContext(
        ticker="KRW-BTC",
        trading_type="spot",
        upbit_client=mock_upbit_client,
        data_collector=mock_data_collector,
        trading_service=mock_trading_service,
        ai_service=mock_ai_service
    )


# ============================================================================
# Test: BasePipelineStage Async
# ============================================================================

class TestBasePipelineStageAsync:
    """BasePipelineStage 비동기 테스트"""

    @pytest.mark.asyncio
    async def test_execute_is_async(self, pipeline_context):
        """execute() 메서드가 async인지 확인"""
        from src.trading.pipeline.base_stage import BasePipelineStage
        import inspect

        # BasePipelineStage.execute가 코루틴 함수인지 확인
        assert inspect.iscoroutinefunction(BasePipelineStage.execute), \
            "BasePipelineStage.execute()는 async 메서드여야 합니다"

    @pytest.mark.asyncio
    async def test_concrete_stage_execute_is_async(self, pipeline_context):
        """구체적인 스테이지의 execute()가 async인지 확인"""
        from src.trading.pipeline.execution_stage import ExecutionStage
        from src.trading.pipeline.data_collection_stage import DataCollectionStage
        from src.trading.pipeline.analysis_stage import AnalysisStage
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
        import inspect

        stages = [
            ExecutionStage(),
            DataCollectionStage(),
            AnalysisStage(),
            HybridRiskCheckStage(),
        ]

        for stage in stages:
            assert inspect.iscoroutinefunction(stage.execute), \
                f"{stage.name}Stage.execute()는 async 메서드여야 합니다"


# ============================================================================
# Test: TradingPipeline Async
# ============================================================================

class TestTradingPipelineAsync:
    """TradingPipeline 비동기 테스트"""

    @pytest.mark.asyncio
    async def test_pipeline_execute_is_async(self):
        """TradingPipeline.execute()가 async인지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        import inspect

        pipeline = TradingPipeline(stages=[])
        assert inspect.iscoroutinefunction(pipeline.execute), \
            "TradingPipeline.execute()는 async 메서드여야 합니다"

    @pytest.mark.asyncio
    async def test_pipeline_executes_stages_sequentially(self, pipeline_context):
        """파이프라인이 스테이지를 순차적으로 실행하는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        execution_order = []

        class MockStage(BasePipelineStage):
            def __init__(self, name: str, order: list):
                super().__init__(name)
                self.order = order

            async def execute(self, context: PipelineContext) -> StageResult:
                self.order.append(self.name)
                return StageResult(success=True, action='continue')

        stages = [
            MockStage("Stage1", execution_order),
            MockStage("Stage2", execution_order),
            MockStage("Stage3", execution_order),
        ]

        pipeline = TradingPipeline(stages=stages)
        result = await pipeline.execute(pipeline_context)

        assert execution_order == ["Stage1", "Stage2", "Stage3"], \
            "스테이지는 순차적으로 실행되어야 합니다"

    @pytest.mark.asyncio
    async def test_pipeline_stops_on_exit_action(self, pipeline_context):
        """exit 액션에서 파이프라인이 중단되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        execution_order = []

        class MockStage(BasePipelineStage):
            def __init__(self, name: str, action: str, order: list):
                super().__init__(name)
                self.action = action
                self.order = order

            async def execute(self, context: PipelineContext) -> StageResult:
                self.order.append(self.name)
                return StageResult(success=True, action=self.action)

        stages = [
            MockStage("Stage1", "continue", execution_order),
            MockStage("Stage2", "exit", execution_order),
            MockStage("Stage3", "continue", execution_order),  # 실행 안됨
        ]

        pipeline = TradingPipeline(stages=stages)
        result = await pipeline.execute(pipeline_context)

        assert execution_order == ["Stage1", "Stage2"], \
            "exit 액션 후 파이프라인이 중단되어야 합니다"
        assert result['pipeline_status'] == 'completed'


# ============================================================================
# Test: DataCollectionStage Async
# ============================================================================

class TestDataCollectionStageAsync:
    """DataCollectionStage 비동기 테스트"""

    @pytest.mark.asyncio
    async def test_execute_returns_stage_result(self, pipeline_context):
        """execute()가 StageResult를 반환하는지 확인"""
        from src.trading.pipeline.data_collection_stage import DataCollectionStage

        stage = DataCollectionStage()

        # chart_data_with_btc 모킹 강화
        pipeline_context.data_collector.get_chart_data_with_btc.return_value = {
            'eth': {'day': [{'close': 1000}], 'minute60': []},
            'btc': {'day': [{'close': 50000}], 'minute60': []}
        }

        result = await stage.execute(pipeline_context)

        assert isinstance(result, StageResult), \
            "execute()는 StageResult를 반환해야 합니다"
        assert result.action in ['continue', 'stop', 'skip', 'exit']


# ============================================================================
# Test: ExecutionStage Async
# ============================================================================

class TestExecutionStageAsync:
    """ExecutionStage 비동기 테스트"""

    @pytest.mark.asyncio
    async def test_execute_buy_is_awaitable(self, pipeline_context):
        """매수 실행이 awaitable인지 확인"""
        from src.trading.pipeline.execution_stage import ExecutionStage

        # AI 결과 설정
        pipeline_context.ai_result = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Test buy'
        }

        stage = ExecutionStage()
        result = await stage.execute(pipeline_context)

        assert isinstance(result, StageResult)
        assert pipeline_context.trading_service.execute_buy.called

    @pytest.mark.asyncio
    async def test_execute_sell_is_awaitable(self, pipeline_context):
        """매도 실행이 awaitable인지 확인"""
        from src.trading.pipeline.execution_stage import ExecutionStage

        # AI 결과 설정
        pipeline_context.ai_result = {
            'decision': 'sell',
            'confidence': 'high',
            'reason': 'Test sell'
        }
        pipeline_context.position_info = {'avg_buy_price': 45000000}

        stage = ExecutionStage()
        result = await stage.execute(pipeline_context)

        assert isinstance(result, StageResult)
        assert pipeline_context.trading_service.execute_sell.called

    @pytest.mark.asyncio
    async def test_execute_hold_is_awaitable(self, pipeline_context):
        """보류 실행이 awaitable인지 확인"""
        from src.trading.pipeline.execution_stage import ExecutionStage

        # AI 결과 설정
        pipeline_context.ai_result = {
            'decision': 'hold',
            'confidence': 'medium',
            'reason': 'Test hold'
        }

        stage = ExecutionStage()
        result = await stage.execute(pipeline_context)

        assert isinstance(result, StageResult)
        assert pipeline_context.trading_service.execute_hold.called


# ============================================================================
# Test: AnalysisStage Async
# ============================================================================

class TestAnalysisStageAsync:
    """AnalysisStage 비동기 테스트"""

    @pytest.mark.asyncio
    async def test_ai_analysis_is_awaitable(self, pipeline_context):
        """AI 분석이 awaitable인지 확인"""
        from src.trading.pipeline.analysis_stage import AnalysisStage
        import inspect

        stage = AnalysisStage()

        # execute가 async 함수인지 확인
        assert inspect.iscoroutinefunction(stage.execute), \
            "AnalysisStage.execute()는 async 메서드여야 합니다"


# ============================================================================
# Test: HybridRiskCheckStage Async
# ============================================================================

class TestHybridRiskCheckStageAsync:
    """HybridRiskCheckStage 비동기 테스트"""

    @pytest.mark.asyncio
    async def test_hybrid_stage_is_async(self, pipeline_context):
        """HybridRiskCheckStage.execute()가 async인지 확인"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
        import inspect

        stage = HybridRiskCheckStage()

        assert inspect.iscoroutinefunction(stage.execute), \
            "HybridRiskCheckStage.execute()는 async 메서드여야 합니다"


# ============================================================================
# Test: Pipeline Factory Functions
# ============================================================================

class TestPipelineFactoryAsync:
    """파이프라인 팩토리 함수 테스트"""

    @pytest.mark.asyncio
    async def test_create_hybrid_pipeline_returns_async_pipeline(self):
        """create_hybrid_trading_pipeline이 async 파이프라인을 반환하는지 확인"""
        from src.trading.pipeline import create_hybrid_trading_pipeline
        import inspect

        pipeline = create_hybrid_trading_pipeline()

        assert inspect.iscoroutinefunction(pipeline.execute), \
            "생성된 파이프라인의 execute()는 async여야 합니다"


# ============================================================================
# Test: Backward Compatibility
# ============================================================================

class TestBackwardCompatibility:
    """하위 호환성 테스트"""

    @pytest.mark.asyncio
    async def test_stage_result_unchanged(self):
        """StageResult 구조가 변경되지 않았는지 확인"""
        result = StageResult(
            success=True,
            action='continue',
            data={'key': 'value'},
            message='Test message',
            metadata={'meta': 'data'}
        )

        assert result.success == True
        assert result.action == 'continue'
        assert result.data == {'key': 'value'}
        assert result.message == 'Test message'
        assert result.metadata == {'meta': 'data'}

    @pytest.mark.asyncio
    async def test_pipeline_context_unchanged(self, mock_upbit_client):
        """PipelineContext 구조가 변경되지 않았는지 확인"""
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            upbit_client=mock_upbit_client
        )

        assert context.ticker == "KRW-BTC"
        assert context.trading_type == "spot"
        assert context.upbit_client is not None
        assert context.chart_data is None
        assert context.ai_result is None
