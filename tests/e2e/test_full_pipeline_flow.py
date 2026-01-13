"""
전체 파이프라인 E2E 테스트

진입부터 실행까지 전체 흐름을 검증합니다.

검증 범위:
- 파이프라인 스테이지 구성 검증
- Context 데이터 전달 경로 검증
- UseCase 호출 순서 검증

제외:
- 실제 거래소 API 호출
- 실제 주문 실행
- 실제 데이터 수집
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from src.container import Container
from src.trading.pipeline.trading_pipeline import (
    create_hybrid_trading_pipeline,
    TradingPipeline,
)
from src.trading.pipeline.base_stage import PipelineContext, StageResult
from src.domain.value_objects.money import Money


@pytest.mark.e2e
class TestFullPipelineFlow:
    """전체 파이프라인 흐름"""

    @pytest.fixture
    def mock_exchange_port(self):
        """Mock ExchangePort"""
        mock = AsyncMock()
        mock.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("1000000"))
        ))
        mock.get_all_positions = AsyncMock(return_value=[])
        mock.get_current_price = AsyncMock(
            return_value=Money.krw(Decimal("50000000"))
        )
        return mock

    @pytest.fixture
    def mock_container(self, mock_exchange_port):
        """Mock Container"""
        container = MagicMock(spec=Container)

        # Exchange Port Mock
        container.get_exchange_port = MagicMock(
            return_value=mock_exchange_port
        )

        # Calculate Entry Amount UseCase Mock
        mock_calc = AsyncMock()
        mock_calc.execute = AsyncMock(
            return_value=Money.krw(Decimal("133333"))
        )
        container.get_calculate_entry_amount_use_case = MagicMock(
            return_value=mock_calc
        )

        # Execute Trade UseCase Mock
        mock_trade = AsyncMock()
        mock_trade.execute_buy = AsyncMock(return_value=MagicMock(
            success=True,
            order_id="test-123",
            executed_price=Money.krw(Decimal("50000000")),
            executed_volume=Decimal("0.00266666"),
            fee=Money.krw(Decimal("50")),
            error_message=None,
        ))
        container.get_execute_trade_use_case = MagicMock(
            return_value=mock_trade
        )

        return container

    def test_pipeline_creates_correct_stages(self):
        """파이프라인이 올바른 스테이지로 구성되는지 확인"""
        # When: 파이프라인 생성
        pipeline = create_hybrid_trading_pipeline(
            enable_scanning=False,
            entry_mode=True
        )

        # Then: 파이프라인이 생성됨
        assert pipeline is not None
        assert isinstance(pipeline, TradingPipeline)
        assert len(pipeline.stages) > 0

    def test_pipeline_stages_order(self):
        """파이프라인 스테이지 순서 확인"""
        # When: 파이프라인 생성
        pipeline = create_hybrid_trading_pipeline(
            enable_scanning=False,
            entry_mode=True
        )

        # Then: 예상되는 스테이지 순서
        stage_names = [stage.name for stage in pipeline.stages]

        # 필수 스테이지가 포함되어야 함
        assert "HybridRiskCheck" in stage_names
        assert "DataCollection" in stage_names
        assert "Analysis" in stage_names
        assert "Execution" in stage_names

        # 순서 확인 (HybridRiskCheck가 DataCollection보다 먼저)
        hybrid_idx = stage_names.index("HybridRiskCheck")
        data_idx = stage_names.index("DataCollection")
        analysis_idx = stage_names.index("Analysis")
        execution_idx = stage_names.index("Execution")

        assert hybrid_idx < data_idx < analysis_idx < execution_idx, \
            f"스테이지 순서가 올바르지 않음: {stage_names}"

    def test_entry_mode_configuration(self):
        """entry_mode 설정이 반영되는지 확인"""
        # When: entry_mode=True로 생성
        pipeline_true = create_hybrid_trading_pipeline(
            enable_scanning=False,
            entry_mode=True
        )

        # Then: AnalysisStage에 entry_mode가 설정됨
        analysis_stage = next(
            (s for s in pipeline_true.stages if s.name == "Analysis"),
            None
        )
        assert analysis_stage is not None
        assert analysis_stage.entry_mode is True

        # When: entry_mode=False로 생성
        pipeline_false = create_hybrid_trading_pipeline(
            enable_scanning=False,
            entry_mode=False
        )

        analysis_stage = next(
            (s for s in pipeline_false.stages if s.name == "Analysis"),
            None
        )
        assert analysis_stage is not None
        assert analysis_stage.entry_mode is False

    def test_enable_scanning_configuration(self):
        """enable_scanning 설정이 반영되는지 확인"""
        # When: enable_scanning=True로 생성
        pipeline = create_hybrid_trading_pipeline(
            enable_scanning=True,
            entry_mode=True
        )

        # Then: HybridRiskCheckStage에 enable_scanning 설정
        hybrid_stage = next(
            (s for s in pipeline.stages if s.name == "HybridRiskCheck"),
            None
        )
        assert hybrid_stage is not None
        assert hybrid_stage.enable_scanning is True


@pytest.mark.e2e
class TestContextDataFlow:
    """Context 데이터 흐름 테스트"""

    def test_context_initialization(self):
        """Context 초기화 테스트"""
        # When: Context 생성
        context = PipelineContext(ticker="KRW-BTC")

        # Then: 기본 속성이 설정됨
        assert context.ticker == "KRW-BTC"
        assert context.ai_result is None
        assert context.trade_result is None

    def test_context_accepts_container(self):
        """Context가 Container를 받는지 확인"""
        # Given: Mock Container
        mock_container = MagicMock()

        # When: Context에 Container 설정
        context = PipelineContext(ticker="KRW-BTC")
        context.container = mock_container

        # Then: Container 접근 가능
        assert context.container is mock_container

    def test_context_signal_analysis_flow(self):
        """signal_analysis 데이터 흐름 확인"""
        # Given: Context with signal_analysis
        context = PipelineContext(ticker="KRW-BTC")
        context.signal_analysis = {
            'decision': 'strong_buy',
            'confidence': 'high',
            'total_score': 80.0
        }

        # Then: signal_analysis 접근 가능
        assert context.signal_analysis is not None
        assert context.signal_analysis['decision'] == 'strong_buy'

    def test_context_ai_result_flow(self):
        """ai_result 데이터 흐름 확인"""
        # Given: Context with ai_result
        context = PipelineContext(ticker="KRW-BTC")
        context.ai_result = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Test reason'
        }

        # Then: ai_result 접근 가능
        assert context.ai_result is not None
        assert context.ai_result['decision'] == 'buy'


@pytest.mark.e2e
class TestUseCaseIntegration:
    """UseCase 통합 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        """Mock ExchangePort"""
        mock = AsyncMock()
        mock.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("1000000"))
        ))
        mock.get_all_positions = AsyncMock(return_value=[])
        mock.get_current_price = AsyncMock(
            return_value=Money.krw(Decimal("50000000"))
        )
        return mock

    def test_container_provides_all_use_cases(self, mock_exchange_port):
        """Container가 모든 필요한 UseCase를 제공하는지 확인"""
        # Given: Mock이 주입된 Container
        container = Container(exchange_port=mock_exchange_port)

        # Then: 모든 UseCase가 제공됨
        assert container.get_execute_trade_use_case() is not None
        assert container.get_calculate_entry_amount_use_case() is not None
        assert container.get_exchange_port() is not None
        assert container.get_validation_port() is not None

    @pytest.mark.asyncio
    async def test_entry_amount_calculation_integration(self, mock_exchange_port):
        """진입 금액 계산 통합 테스트"""
        # Given: Container with mocks
        container = Container(exchange_port=mock_exchange_port)

        # When: UseCase 실행
        use_case = container.get_calculate_entry_amount_use_case()
        result = await use_case.execute("KRW-BTC")

        # Then: 올바른 진입 금액 계산
        # 1,000,000 * 0.4 / 3 = 133,333
        assert result.amount == Decimal("133333")


@pytest.mark.e2e
class TestConfigurationPropagation:
    """설정 전파 E2E 테스트"""

    def test_stop_loss_propagates_to_pipeline(self):
        """손절 설정이 파이프라인에 전파되는지 확인"""
        # Given: 커스텀 손절 설정
        custom_stop_loss = -3.0

        # When: 파이프라인 생성 with 커스텀 손절
        pipeline = create_hybrid_trading_pipeline(
            enable_scanning=False,
            entry_mode=True,
            stop_loss_pct=custom_stop_loss,
        )

        # Then: HybridRiskCheckStage에 설정 적용됨
        hybrid_stage = next(
            (s for s in pipeline.stages if s.name == "HybridRiskCheck"),
            None
        )
        assert hybrid_stage is not None
        assert hybrid_stage.stop_loss_pct == custom_stop_loss

    def test_take_profit_propagates_to_pipeline(self):
        """익절 설정이 파이프라인에 전파되는지 확인"""
        # Given: 커스텀 익절 설정
        custom_take_profit = 15.0

        # When: 파이프라인 생성 with 커스텀 익절
        pipeline = create_hybrid_trading_pipeline(
            enable_scanning=False,
            entry_mode=True,
            take_profit_pct=custom_take_profit,
        )

        # Then: HybridRiskCheckStage에 설정 적용됨
        hybrid_stage = next(
            (s for s in pipeline.stages if s.name == "HybridRiskCheck"),
            None
        )
        assert hybrid_stage is not None
        assert hybrid_stage.take_profit_pct == custom_take_profit

    def test_default_values_match_across_components(self):
        """기본값이 컴포넌트 간 일치하는지 확인"""
        # Given: 기본값으로 생성된 파이프라인
        pipeline = create_hybrid_trading_pipeline(
            enable_scanning=False,
            entry_mode=True,
        )

        # When: 스테이지 설정값 확인
        hybrid_stage = next(
            (s for s in pipeline.stages if s.name == "HybridRiskCheck"),
            None
        )

        # Then: 기본값이 일치해야 함
        assert hybrid_stage.stop_loss_pct == -5.0
        assert hybrid_stage.take_profit_pct == 10.0
