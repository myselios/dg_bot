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


# ============================================================================
# Test: TradingPipeline Callback Processing (NEW)
# ============================================================================

class TestTradingPipelineCallbackProcessing:
    """TradingPipeline 콜백 처리 테스트"""

    @pytest.mark.asyncio
    async def test_callback_executed_when_pending_data_exists(self, pipeline_context):
        """pending_backtest_callback_data가 있을 때 콜백이 실행되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        callback_called = []
        callback_data_received = []

        # 비동기 콜백 함수
        async def on_backtest_complete(data):
            callback_called.append(True)
            callback_data_received.append(data)

        # 콜백 데이터를 설정하는 스테이지
        class CallbackSettingStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                context.pending_backtest_callback_data = {
                    'ticker': 'KRW-ETH',
                    'backtest_result': {'passed': True, 'metrics': {}},
                    'scan_summary': {'liquidity_scanned': 20, 'backtest_passed': 5}
                }
                return StageResult(success=True, action='continue')

        pipeline_context.on_backtest_complete = on_backtest_complete

        stages = [CallbackSettingStage("CallbackSetter")]
        pipeline = TradingPipeline(stages=stages)

        await pipeline.execute(pipeline_context)

        assert len(callback_called) == 1, "콜백이 한 번 호출되어야 합니다"
        assert callback_data_received[0]['ticker'] == 'KRW-ETH'
        assert callback_data_received[0]['scan_summary']['liquidity_scanned'] == 20

    @pytest.mark.asyncio
    async def test_callback_not_executed_when_no_pending_data(self, pipeline_context):
        """pending_backtest_callback_data가 없을 때 콜백이 실행되지 않는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        callback_called = []

        async def on_backtest_complete(data):
            callback_called.append(True)

        class NoCallbackStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                # pending_backtest_callback_data를 설정하지 않음
                return StageResult(success=True, action='continue')

        pipeline_context.on_backtest_complete = on_backtest_complete

        stages = [NoCallbackStage("NoCallback")]
        pipeline = TradingPipeline(stages=stages)

        await pipeline.execute(pipeline_context)

        assert len(callback_called) == 0, "콜백이 호출되지 않아야 합니다"

    @pytest.mark.asyncio
    async def test_callback_on_exit_action(self, pipeline_context):
        """exit 액션에서도 콜백이 실행되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        callback_called = []

        async def on_backtest_complete(data):
            callback_called.append(True)

        class ExitWithCallbackStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                context.pending_backtest_callback_data = {
                    'ticker': 'KRW-BTC',
                    'backtest_result': {'passed': False}
                }
                return StageResult(success=True, action='exit')

        pipeline_context.on_backtest_complete = on_backtest_complete

        stages = [ExitWithCallbackStage("ExitWithCallback")]
        pipeline = TradingPipeline(stages=stages)

        result = await pipeline.execute(pipeline_context)

        assert len(callback_called) >= 1, "exit 전에 콜백이 실행되어야 합니다"
        assert result['pipeline_status'] == 'completed'

    @pytest.mark.asyncio
    async def test_callback_on_skip_action(self, pipeline_context):
        """skip 액션에서도 콜백이 실행되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        callback_called = []

        async def on_backtest_complete(data):
            callback_called.append(True)

        class SkipWithCallbackStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                context.pending_backtest_callback_data = {
                    'ticker': 'KRW-XRP',
                    'backtest_result': {'passed': False}
                }
                return StageResult(success=True, action='skip')

        pipeline_context.on_backtest_complete = on_backtest_complete

        stages = [SkipWithCallbackStage("SkipWithCallback")]
        pipeline = TradingPipeline(stages=stages)

        await pipeline.execute(pipeline_context)

        assert len(callback_called) >= 1, "skip 전에 콜백이 실행되어야 합니다"

    @pytest.mark.asyncio
    async def test_callback_cleared_after_execution(self, pipeline_context):
        """콜백 실행 후 pending_data가 초기화되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        execution_counts = {'stage1': 0, 'stage2': 0}
        callback_counts = []

        async def on_backtest_complete(data):
            callback_counts.append(data.get('stage', 'unknown'))

        class Stage1(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                execution_counts['stage1'] += 1
                context.pending_backtest_callback_data = {
                    'stage': 'stage1',
                    'ticker': 'KRW-ETH'
                }
                return StageResult(success=True, action='continue')

        class Stage2(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                execution_counts['stage2'] += 1
                # Stage1의 콜백이 처리된 후이므로 pending_data는 None이어야 함
                assert context.pending_backtest_callback_data is None, \
                    "Stage1 콜백 처리 후 pending_data는 None이어야 합니다"
                return StageResult(success=True, action='continue')

        pipeline_context.on_backtest_complete = on_backtest_complete

        stages = [Stage1("Stage1"), Stage2("Stage2")]
        pipeline = TradingPipeline(stages=stages)

        await pipeline.execute(pipeline_context)

        assert execution_counts['stage1'] == 1
        assert execution_counts['stage2'] == 1
        assert len(callback_counts) == 1
        assert callback_counts[0] == 'stage1'

    @pytest.mark.asyncio
    async def test_sync_callback_also_works(self, pipeline_context):
        """동기 콜백도 동작하는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        callback_called = []

        # 동기 콜백 함수 (async가 아님)
        def on_backtest_complete_sync(data):
            callback_called.append(data['ticker'])

        class SyncCallbackStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                context.pending_backtest_callback_data = {
                    'ticker': 'KRW-SOL',
                    'backtest_result': {'passed': True}
                }
                return StageResult(success=True, action='continue')

        pipeline_context.on_backtest_complete = on_backtest_complete_sync

        stages = [SyncCallbackStage("SyncCallback")]
        pipeline = TradingPipeline(stages=stages)

        await pipeline.execute(pipeline_context)

        assert 'KRW-SOL' in callback_called, "동기 콜백도 동작해야 합니다"

    @pytest.mark.asyncio
    async def test_callback_error_does_not_stop_pipeline(self, pipeline_context):
        """콜백 에러가 파이프라인을 중단시키지 않는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        stage_executed = []

        async def failing_callback(data):
            raise ValueError("콜백에서 에러 발생!")

        class StageBeforeError(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                context.pending_backtest_callback_data = {'ticker': 'KRW-ETH'}
                return StageResult(success=True, action='continue')

        class StageAfterError(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                stage_executed.append(self.name)
                return StageResult(success=True, action='continue')

        pipeline_context.on_backtest_complete = failing_callback

        stages = [StageBeforeError("BeforeError"), StageAfterError("AfterError")]
        pipeline = TradingPipeline(stages=stages)

        # 파이프라인이 에러 없이 완료되어야 함
        result = await pipeline.execute(pipeline_context)

        assert 'AfterError' in stage_executed, "콜백 에러 후에도 다음 스테이지가 실행되어야 합니다"
        assert result['pipeline_status'] == 'completed'


# ============================================================================
# Test: TradingPipeline Error Handling (NEW)
# ============================================================================

class TestTradingPipelineErrorHandling:
    """TradingPipeline 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_stage_exception_creates_error_response(self, pipeline_context):
        """스테이지 예외 발생 시 에러 응답 생성 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        class FailingStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                raise RuntimeError("스테이지에서 예외 발생!")

        stages = [FailingStage("Failing")]
        pipeline = TradingPipeline(stages=stages)

        result = await pipeline.execute(pipeline_context)

        assert result['pipeline_status'] == 'failed'
        assert result['status'] == 'failed'
        assert result['decision'] == 'hold'
        assert 'error' in result

    @pytest.mark.asyncio
    async def test_stage_failure_returns_error_response(self, pipeline_context):
        """스테이지 실패(success=False) 시 에러 응답 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        class FailingResultStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                return StageResult(
                    success=False,
                    action='stop',
                    message='데이터 수집 실패',
                    metadata={'error': 'API timeout'}
                )

        stages = [FailingResultStage("FailingResult")]
        pipeline = TradingPipeline(stages=stages)

        result = await pipeline.execute(pipeline_context)

        assert result['pipeline_status'] == 'failed'
        assert result['error'] == 'API timeout'
        assert result['reason'] == '데이터 수집 실패'

    @pytest.mark.asyncio
    async def test_stop_action_returns_error_response(self, pipeline_context):
        """stop 액션 시 에러 응답 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        class StopStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                return StageResult(
                    success=True,  # success=True이지만 action='stop'
                    action='stop',
                    message='리스크 한도 초과',
                    metadata={'error': '일일 손실 한도 초과'}
                )

        stages = [StopStage("Stop")]
        pipeline = TradingPipeline(stages=stages)

        result = await pipeline.execute(pipeline_context)

        assert result['pipeline_status'] == 'failed'

    @pytest.mark.asyncio
    async def test_exception_after_callback_still_handles_callback(self, pipeline_context):
        """예외 발생 전에 콜백이 처리되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        callback_data_received = []

        async def on_backtest_complete(data):
            callback_data_received.append(data)

        class CallbackThenFailStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                context.pending_backtest_callback_data = {'ticker': 'KRW-ETH'}
                return StageResult(success=True, action='continue')

        class ExceptionStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                raise RuntimeError("두 번째 스테이지 예외!")

        pipeline_context.on_backtest_complete = on_backtest_complete

        stages = [CallbackThenFailStage("CallbackFirst"), ExceptionStage("Exception")]
        pipeline = TradingPipeline(stages=stages)

        result = await pipeline.execute(pipeline_context)

        # 콜백은 실행되어야 함
        assert len(callback_data_received) == 1
        assert callback_data_received[0]['ticker'] == 'KRW-ETH'
        # 파이프라인은 실패해야 함
        assert result['pipeline_status'] == 'failed'


# ============================================================================
# Test: TradingPipeline State Management (NEW)
# ============================================================================

class TestTradingPipelineStateManagement:
    """TradingPipeline 상태 관리 테스트"""

    @pytest.mark.asyncio
    async def test_context_data_persists_across_stages(self, pipeline_context):
        """컨텍스트 데이터가 스테이지 간 유지되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        class SetDataStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                context.chart_data = {'day': [{'close': 50000}]}
                context.technical_indicators = {'rsi': 45}
                return StageResult(success=True, action='continue')

        class CheckDataStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                assert context.chart_data is not None
                assert context.chart_data['day'][0]['close'] == 50000
                assert context.technical_indicators['rsi'] == 45
                return StageResult(success=True, action='continue')

        stages = [SetDataStage("SetData"), CheckDataStage("CheckData")]
        pipeline = TradingPipeline(stages=stages)

        result = await pipeline.execute(pipeline_context)

        assert result['pipeline_status'] == 'completed'

    @pytest.mark.asyncio
    async def test_pre_execute_can_skip_stage(self, pipeline_context):
        """pre_execute가 False를 반환하면 스테이지가 스킵되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        skipped_stage_executed = []

        class SkippableStage(BasePipelineStage):
            def pre_execute(self, context: PipelineContext) -> bool:
                return False  # 스킵

            async def execute(self, context: PipelineContext) -> StageResult:
                skipped_stage_executed.append(True)
                return StageResult(success=True, action='continue')

        class NormalStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                return StageResult(success=True, action='continue')

        stages = [SkippableStage("Skippable"), NormalStage("Normal")]
        pipeline = TradingPipeline(stages=stages)

        result = await pipeline.execute(pipeline_context)

        assert len(skipped_stage_executed) == 0, "pre_execute=False인 스테이지는 실행되지 않아야 합니다"
        assert result['pipeline_status'] == 'completed'

    @pytest.mark.asyncio
    async def test_post_execute_called_after_stage(self, pipeline_context):
        """post_execute가 스테이지 실행 후 호출되는지 확인"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline
        from src.trading.pipeline.base_stage import BasePipelineStage

        post_execute_results = []

        class PostExecuteStage(BasePipelineStage):
            async def execute(self, context: PipelineContext) -> StageResult:
                return StageResult(success=True, action='continue', data={'test': 'data'})

            def post_execute(self, context: PipelineContext, result: StageResult) -> None:
                post_execute_results.append({
                    'stage': self.name,
                    'result_action': result.action,
                    'result_data': result.data
                })

        stages = [PostExecuteStage("PostExecute")]
        pipeline = TradingPipeline(stages=stages)

        await pipeline.execute(pipeline_context)

        assert len(post_execute_results) == 1
        assert post_execute_results[0]['stage'] == 'PostExecute'
        assert post_execute_results[0]['result_action'] == 'continue'
        assert post_execute_results[0]['result_data'] == {'test': 'data'}
