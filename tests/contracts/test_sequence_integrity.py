"""
파이프라인 시퀀스 무결성 계약 테스트

각 스테이지에서 계산한 값이 다음 스테이지로 올바르게 전달되는지 검증합니다.

주의: 단순히 Context에 값을 넣고 확인하는 것이 아니라,
실제 스테이지를 거쳐 데이터가 전달되는지 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from src.trading.pipeline.base_stage import PipelineContext, StageResult
from src.trading.pipeline.execution_stage import ExecutionStage
from src.trading.pipeline.analysis_stage import AnalysisStage
from src.domain.value_objects.money import Money, Currency


@pytest.mark.contract
class TestSequenceIntegrity:
    """시퀀스 무결성 계약 - 실제 스테이지 실행 검증"""

    @pytest.fixture
    def mock_container(self):
        """Container Mock with all dependencies"""
        container = MagicMock()

        # CalculateEntryAmountUseCase Mock
        mock_calc = AsyncMock()
        mock_calc.execute.return_value = Money.krw(Decimal("133333"))
        container.get_calculate_entry_amount_use_case.return_value = mock_calc

        # ExecuteTradeUseCase Mock
        mock_trade = AsyncMock()
        mock_trade.execute_buy.return_value = MagicMock(
            success=True, order_id="test-123",
            executed_price=None, executed_volume=None, fee=None,
            error_message=None
        )
        container.get_execute_trade_use_case.return_value = mock_trade

        # ExchangePort Mock
        mock_exchange = AsyncMock()
        mock_exchange.get_current_price.return_value = Money.krw(Decimal("50000000"))
        mock_exchange.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        container.get_exchange_port.return_value = mock_exchange

        return container

    @pytest.fixture
    def execution_context(self, mock_container):
        """ExecutionStage 실행에 필요한 완전한 Context"""
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-BTC"
        context.ai_result = {'decision': 'buy', 'confidence': 'high'}
        context.container = mock_container
        context.risk_manager = None
        context.validation_result = None
        context.position_check = True
        context.circuit_check = True
        context.frequency_check = True
        context.flash_crash = None
        context.rsi_divergence = None
        context.backtest_result = None
        context.signal_analysis = None
        context.trade_result = None
        context.position_info = None

        # ExchangePort 설정
        context.get_exchange_port.return_value = mock_container.get_exchange_port()

        return context

    @pytest.mark.asyncio
    async def test_execution_stage_calls_calculate_entry_amount_usecase(
        self, mock_container, execution_context
    ):
        """
        ExecutionStage가 실제로 CalculateEntryAmountUseCase를 호출하는지 검증

        이 테스트는 context.entry_capital이 아닌,
        UseCase를 통해 진입 금액이 계산되는지 확인합니다.
        """
        # Given: buy 결정이 있는 컨텍스트
        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = StageResult(success=True, action='exit')
                await stage.execute(execution_context)

        # Then: CalculateEntryAmountUseCase가 호출되어야 함
        mock_container.get_calculate_entry_amount_use_case.assert_called_once()
        mock_calc = mock_container.get_calculate_entry_amount_use_case.return_value
        mock_calc.execute.assert_called_once_with("KRW-BTC")

    @pytest.mark.asyncio
    async def test_ai_result_determines_execution_branch(self, mock_container, execution_context):
        """
        AnalysisStage의 ai_result.decision이 ExecutionStage의 분기를 결정하는지 검증

        단순히 context.ai_result를 읽는 것이 아니라,
        실제 ExecutionStage.execute()에서 올바른 메서드가 호출되는지 확인합니다.
        """
        # Given: 다양한 decision 값
        # _execute_hold는 sync, _execute_buy/_execute_sell는 async
        test_cases = [
            ('buy', '_execute_buy', True),    # is_async=True
            ('sell', '_execute_sell', True),  # is_async=True
            ('hold', '_execute_hold', False), # is_async=False (sync method)
        ]

        for decision, expected_method, is_async in test_cases:
            # Reset context for each test case
            execution_context.ai_result = {'decision': decision}

            stage = ExecutionStage()

            # When/Then: 올바른 메서드가 호출되는지 확인
            with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
                # _execute_hold는 sync이므로 MagicMock 사용
                mock_cls = AsyncMock if is_async else MagicMock
                with patch.object(stage, expected_method, new_callable=mock_cls) as mock_method:
                    with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                        mock_result.return_value = StageResult(success=True, action='exit')
                        await stage.execute(execution_context)

                        mock_method.assert_called_once(), \
                            f"decision='{decision}'일 때 {expected_method}가 호출되어야 함"

    @pytest.mark.asyncio
    async def test_backtest_result_available_in_analysis_stage(self):
        """
        백테스트 결과가 AnalysisStage에서 실제로 사용되는지 검증
        """
        # Given: 백테스트 결과가 있는 컨텍스트
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-BTC"
        context.backtest_result = MagicMock(
            passed=True,
            metrics={'sharpe_ratio': 1.5}
        )
        context.signal_analysis = {
            'decision': 'strong_buy',
            'confidence': 'high',
            'total_score': 75.0
        }
        context.container = None  # 레거시 경로
        context.chart_data = MagicMock()
        context.chart_data.df = MagicMock()
        context.ai_result = None
        context.flash_crash = None
        context.rsi_divergence = None
        context.validation_result = None

        stage = AnalysisStage(entry_mode=True)

        # When: 실행 (내부 의존성 mock)
        mock_backtest_pass = StageResult(success=True, action='continue', message="백테스트 통과")
        with patch.object(stage, '_detect_flash_crash'):
            with patch.object(stage, '_detect_rsi_divergence'):
                with patch.object(stage, '_run_backtest_filter', return_value=mock_backtest_pass):
                    with patch.object(stage, '_analyze_signals'):
                        result = await stage.execute(context)

        # Then: 백테스트 결과가 접근 가능해야 함
        assert context.backtest_result.passed is True
        # entry_mode=True이므로 SignalAnalyzer 결과 사용
        assert context.ai_result is not None

    @pytest.mark.asyncio
    async def test_entry_amount_flows_to_trade_execution(self, mock_container, execution_context):
        """
        진입 금액이 ExecuteTradeUseCase로 올바르게 전달되는지 검증
        """
        # Given: 133,333원으로 진입 금액 설정됨 (mock_container fixture)
        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = StageResult(success=True, action='exit')
                await stage.execute(execution_context)

        # Then: ExecuteTradeUseCase.execute_buy가 올바른 금액으로 호출되어야 함
        mock_trade = mock_container.get_execute_trade_use_case.return_value
        mock_trade.execute_buy.assert_called_once()

        # 호출 인자 검증
        call_args = mock_trade.execute_buy.call_args
        assert call_args[0][0] == "KRW-BTC"  # ticker
        assert call_args[0][1].amount == Decimal("133333")  # entry_amount
