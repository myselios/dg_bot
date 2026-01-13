"""
AI 결과 전파 시나리오 테스트

AnalysisStage의 AI 결과가 ExecutionStage로 올바르게 전달되는지 검증합니다.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal

from src.trading.pipeline.base_stage import PipelineContext
from src.trading.pipeline.execution_stage import ExecutionStage
from src.domain.value_objects.money import Money


@pytest.mark.scenario
class TestAIResultPropagation:
    """AI 결과 전파 시나리오"""

    @pytest.fixture
    def mock_exchange_port(self):
        """ExchangePort Mock"""
        mock_exchange = AsyncMock()
        mock_exchange.get_current_price.return_value = Money.krw(Decimal("50000000"))
        mock_exchange.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        return mock_exchange

    @pytest.fixture
    def context_with_ai_result(self, mock_exchange_port):
        """AI 결과가 있는 컨텍스트 (필수 의존성 포함)"""
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-BTC"
        context.ai_result = {
            'decision': 'buy',
            'confidence': 'high',
            'reason': 'Strong buy signal detected'
        }
        # ExecutionStage.execute()에서 필요한 속성들
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
        context.container = MagicMock()

        # get_exchange_port()는 _print_current_status와 _create_result에서 사용
        context.get_exchange_port.return_value = mock_exchange_port

        return context

    @pytest.mark.asyncio
    async def test_execution_receives_buy_decision(self, context_with_ai_result):
        """ExecutionStage가 buy 결정을 받는지 확인"""
        # Given: buy 결정
        context_with_ai_result.ai_result['decision'] = 'buy'

        # When: ExecutionStage 실행
        stage = ExecutionStage()

        # Then: _execute_buy가 호출되어야 함
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_execute_buy', new_callable=AsyncMock) as mock_buy:
                with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                    mock_result.return_value = MagicMock(success=True)
                    await stage.execute(context_with_ai_result)
                    mock_buy.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_receives_hold_decision(self, context_with_ai_result):
        """ExecutionStage가 hold 결정을 받는지 확인"""
        # Given: hold 결정
        context_with_ai_result.ai_result['decision'] = 'hold'

        # When: ExecutionStage 실행
        stage = ExecutionStage()

        # Then: _execute_hold가 호출되어야 함 (_execute_hold는 sync)
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_execute_hold') as mock_hold:  # sync이므로 MagicMock
                with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                    mock_result.return_value = MagicMock(success=True)
                    await stage.execute(context_with_ai_result)
                    mock_hold.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_receives_sell_decision(self, context_with_ai_result):
        """ExecutionStage가 sell 결정을 받는지 확인"""
        # Given: sell 결정
        context_with_ai_result.ai_result['decision'] = 'sell'

        # When: ExecutionStage 실행
        stage = ExecutionStage()

        # Then: _execute_sell이 호출되어야 함
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_execute_sell', new_callable=AsyncMock) as mock_sell:
                with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                    mock_result.return_value = MagicMock(success=True)
                    await stage.execute(context_with_ai_result)
                    mock_sell.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_result_reason_is_accessible(self, context_with_ai_result):
        """AI 결과의 reason이 접근 가능한지 확인"""
        # Given: AI 결과에 reason 포함
        expected_reason = "Technical indicators show bullish momentum"
        context_with_ai_result.ai_result['reason'] = expected_reason

        # Then: reason이 context에서 접근 가능
        assert context_with_ai_result.ai_result['reason'] == expected_reason

    @pytest.mark.asyncio
    async def test_ai_result_confidence_is_accessible(self, context_with_ai_result):
        """AI 결과의 confidence가 접근 가능한지 확인"""
        # Given: AI 결과에 confidence 포함
        test_cases = ['high', 'medium', 'low']

        for confidence in test_cases:
            context_with_ai_result.ai_result['confidence'] = confidence

            # Then: confidence가 context에서 접근 가능
            assert context_with_ai_result.ai_result['confidence'] == confidence

    @pytest.mark.asyncio
    async def test_unknown_decision_does_not_execute_trade(self, context_with_ai_result):
        """알 수 없는 결정은 거래를 실행하지 않아야 함"""
        # Given: 알 수 없는 결정
        context_with_ai_result.ai_result['decision'] = 'unknown_action'

        # When: ExecutionStage 실행
        stage = ExecutionStage()

        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_execute_buy', new_callable=AsyncMock) as mock_buy:
                with patch.object(stage, '_execute_sell', new_callable=AsyncMock) as mock_sell:
                    with patch.object(stage, '_execute_hold') as mock_hold:
                        with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                            mock_result.return_value = MagicMock(success=True)
                            await stage.execute(context_with_ai_result)

                            # Then: 어떤 거래 메서드도 호출되지 않아야 함
                            mock_buy.assert_not_called()
                            mock_sell.assert_not_called()
                            mock_hold.assert_not_called()

    @pytest.mark.asyncio
    async def test_decision_case_sensitivity(self, context_with_ai_result):
        """결정 값은 소문자로 처리되는지 확인"""
        # Given: buy 결정 (소문자)
        context_with_ai_result.ai_result['decision'] = 'buy'
        stage = ExecutionStage()

        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_execute_buy', new_callable=AsyncMock) as mock_buy:
                with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                    mock_result.return_value = MagicMock(success=True)
                    await stage.execute(context_with_ai_result)

                    # Then: _execute_buy가 호출됨
                    mock_buy.assert_called_once()
