"""
파이프라인 기본 테스트

파이프라인 구조가 올바르게 작동하는지 기본적인 테스트
"""
import pytest
from unittest.mock import Mock, MagicMock
from src.trading.pipeline import PipelineContext, StageResult, BasePipelineStage


class DummyStage(BasePipelineStage):
    """테스트용 더미 스테이지"""

    def __init__(self, name: str, action: str = 'continue'):
        super().__init__(name)
        self.action = action
        self.executed = False

    def execute(self, context: PipelineContext) -> StageResult:
        self.executed = True
        return StageResult(
            success=True,
            action=self.action,
            message=f"{self.name} executed"
        )


@pytest.mark.unit
class TestPipelineContext:
    """PipelineContext 테스트"""

    def test_context_initialization(self):
        """컨텍스트 초기화 테스트"""
        context = PipelineContext(
            ticker="KRW-ETH",
            trading_type="spot"
        )

        assert context.ticker == "KRW-ETH"
        assert context.trading_type == "spot"
        assert context.metadata == {}

    def test_context_metadata(self):
        """컨텍스트 메타데이터 테스트"""
        context = PipelineContext(
            ticker="KRW-BTC",
            metadata={'test_key': 'test_value'}
        )

        assert context.metadata['test_key'] == 'test_value'


@pytest.mark.unit
class TestStageResult:
    """StageResult 테스트"""

    def test_result_initialization(self):
        """결과 초기화 테스트"""
        result = StageResult(
            success=True,
            action='continue',
            message="Test message"
        )

        assert result.success is True
        assert result.action == 'continue'
        assert result.message == "Test message"
        assert result.data == {}
        assert result.metadata == {}

    def test_result_with_data(self):
        """데이터 포함 결과 테스트"""
        result = StageResult(
            success=True,
            action='exit',
            data={'decision': 'buy'},
            metadata={'confidence': 0.8}
        )

        assert result.data['decision'] == 'buy'
        assert result.metadata['confidence'] == 0.8


@pytest.mark.unit
class TestBasePipelineStage:
    """BasePipelineStage 테스트"""

    def test_stage_name(self):
        """스테이지 이름 테스트"""
        stage = DummyStage("TestStage")
        assert stage.name == "TestStage"

    def test_stage_execution(self):
        """스테이지 실행 테스트"""
        stage = DummyStage("TestStage")
        context = PipelineContext(ticker="KRW-ETH")

        assert stage.executed is False

        result = stage.execute(context)

        assert stage.executed is True
        assert result.success is True
        assert result.action == 'continue'

    def test_stage_pre_execute_default(self):
        """스테이지 pre_execute 기본 동작 테스트"""
        stage = DummyStage("TestStage")
        context = PipelineContext(ticker="KRW-ETH")

        # 기본값은 True
        assert stage.pre_execute(context) is True

    def test_stage_post_execute_default(self):
        """스테이지 post_execute 기본 동작 테스트"""
        stage = DummyStage("TestStage")
        context = PipelineContext(ticker="KRW-ETH")
        result = StageResult(success=True, action='continue')

        # 기본 구현은 아무것도 하지 않음 (에러 없이 실행되는지 확인)
        stage.post_execute(context, result)

    def test_stage_handle_error(self):
        """스테이지 에러 핸들링 테스트"""
        stage = DummyStage("TestStage")
        context = PipelineContext(ticker="KRW-ETH")
        error = Exception("Test error")

        result = stage.handle_error(context, error)

        assert result.success is False
        assert result.action == 'stop'
        assert "Test error" in result.message
        assert result.metadata['error'] == "Test error"
        assert result.metadata['error_type'] == "Exception"


@pytest.mark.unit
class TestTradingPipelineBasic:
    """TradingPipeline 기본 테스트"""

    @pytest.mark.asyncio
    async def test_pipeline_single_stage(self):
        """단일 스테이지 파이프라인 테스트"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline

        stage = DummyStage("Stage1", action='exit')
        pipeline = TradingPipeline(stages=[stage])

        context = PipelineContext(
            ticker="KRW-ETH",
            upbit_client=Mock()
        )

        result = await pipeline.execute(context)

        assert stage.executed is True
        assert result['pipeline_status'] == 'completed'

    @pytest.mark.asyncio
    async def test_pipeline_multiple_stages(self):
        """다중 스테이지 파이프라인 테스트"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline

        stage1 = DummyStage("Stage1", action='continue')
        stage2 = DummyStage("Stage2", action='continue')
        stage3 = DummyStage("Stage3", action='exit')
        pipeline = TradingPipeline(stages=[stage1, stage2, stage3])

        context = PipelineContext(
            ticker="KRW-ETH",
            upbit_client=Mock()
        )

        result = await pipeline.execute(context)

        # 모든 스테이지가 실행되어야 함
        assert stage1.executed is True
        assert stage2.executed is True
        assert stage3.executed is True
        assert result['pipeline_status'] == 'completed'

    @pytest.mark.asyncio
    async def test_pipeline_early_exit(self):
        """파이프라인 조기 종료 테스트"""
        from src.trading.pipeline.trading_pipeline import TradingPipeline

        stage1 = DummyStage("Stage1", action='continue')
        stage2 = DummyStage("Stage2", action='exit')  # 여기서 종료
        stage3 = DummyStage("Stage3", action='continue')  # 실행되지 않아야 함
        pipeline = TradingPipeline(stages=[stage1, stage2, stage3])

        context = PipelineContext(
            ticker="KRW-ETH",
            upbit_client=Mock()
        )

        result = await pipeline.execute(context)

        # stage1, stage2만 실행, stage3는 실행 안 됨
        assert stage1.executed is True
        assert stage2.executed is True
        assert stage3.executed is False
        assert result['pipeline_status'] == 'completed'
