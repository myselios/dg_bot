"""
ExecutionStage와 UseCase 통합 테스트

ExecutionStage가 Container의 UseCase를 올바르게 사용하는지 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from src.trading.pipeline.execution_stage import ExecutionStage
from src.trading.pipeline.base_stage import PipelineContext
from src.domain.value_objects.money import Money, Currency


@pytest.mark.integration
class TestExecutionStageUseCase:
    """ExecutionStage UseCase 통합"""

    @pytest.fixture
    def mock_exchange_port(self):
        """Mock ExchangePort"""
        mock = AsyncMock()
        mock.get_current_price = AsyncMock(
            return_value=Money.krw(Decimal("50000000"))
        )
        mock.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("1000000"))
        ))
        return mock

    @pytest.fixture
    def mock_container(self, mock_exchange_port):
        """Mock Container"""
        container = MagicMock()

        # CalculateEntryAmountUseCase Mock
        mock_calc_use_case = AsyncMock()
        mock_calc_use_case.execute = AsyncMock(
            return_value=Money.krw(Decimal("100000"))
        )
        container.get_calculate_entry_amount_use_case = MagicMock(
            return_value=mock_calc_use_case
        )

        # ExecuteTradeUseCase Mock
        mock_trade_use_case = AsyncMock()
        mock_trade_use_case.execute_buy = AsyncMock(return_value=MagicMock(
            success=True,
            order_id="test-order-123",
            executed_price=Money.krw(Decimal("50000000")),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(Decimal("50")),
            error_message=None,
        ))
        container.get_execute_trade_use_case = MagicMock(
            return_value=mock_trade_use_case
        )

        # ExchangePort Mock
        container.get_exchange_port = MagicMock(
            return_value=mock_exchange_port
        )

        return container

    @pytest.fixture
    def context_with_container(self, mock_container, mock_exchange_port):
        """Container가 있는 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-BTC"
        context.ai_result = {'decision': 'buy'}
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

        # get_exchange_port()는 _print_current_status에서 사용
        context.get_exchange_port = MagicMock(
            return_value=mock_exchange_port
        )

        return context

    @pytest.mark.asyncio
    async def test_uses_calculate_entry_amount_use_case(self, context_with_container):
        """CalculateEntryAmountUseCase 사용 확인"""
        # Given: buy 결정
        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = MagicMock(success=True)
                await stage.execute(context_with_container)

        # Then: CalculateEntryAmountUseCase가 호출됨
        context_with_container.container.get_calculate_entry_amount_use_case.assert_called_once()
        mock_calc = context_with_container.container.get_calculate_entry_amount_use_case()
        mock_calc.execute.assert_called_once_with("KRW-BTC")

    @pytest.mark.asyncio
    async def test_uses_execute_trade_use_case(self, context_with_container):
        """ExecuteTradeUseCase 사용 확인"""
        # Given: buy 결정, 진입 금액 > 0
        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = MagicMock(success=True)
                await stage.execute(context_with_container)

        # Then: ExecuteTradeUseCase가 호출됨
        context_with_container.container.get_execute_trade_use_case.assert_called_once()
        mock_trade = context_with_container.container.get_execute_trade_use_case()
        mock_trade.execute_buy.assert_called_once()

    @pytest.mark.asyncio
    async def test_entry_amount_passed_to_trade(self, context_with_container):
        """진입 금액이 ExecuteTradeUseCase에 전달되는지 확인"""
        # Given: 특정 진입 금액
        expected_amount = Money.krw(Decimal("100000"))
        mock_calc = context_with_container.container.get_calculate_entry_amount_use_case()
        mock_calc.execute.return_value = expected_amount

        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = MagicMock(success=True)
                await stage.execute(context_with_container)

        # Then: 올바른 금액이 전달됨
        mock_trade = context_with_container.container.get_execute_trade_use_case()
        mock_trade.execute_buy.assert_called_once_with("KRW-BTC", expected_amount)

    @pytest.mark.asyncio
    async def test_zero_entry_amount_skips_trade(self, context_with_container):
        """진입 금액 0일 때 거래 스킵 확인"""
        # Given: 진입 금액 0
        mock_calc = context_with_container.container.get_calculate_entry_amount_use_case()
        mock_calc.execute.return_value = Money.krw(Decimal("0"))

        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = MagicMock(success=True)
                await stage.execute(context_with_container)

        # Then: ExecuteTradeUseCase.execute_buy 호출 안 됨
        mock_trade = context_with_container.container.get_execute_trade_use_case()
        mock_trade.execute_buy.assert_not_called()

    @pytest.mark.asyncio
    async def test_trade_result_stored_in_context(self, context_with_container):
        """거래 결과가 context에 저장되는지 확인"""
        # Given
        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = MagicMock(success=True)
                await stage.execute(context_with_container)

        # Then: trade_result가 설정됨
        assert context_with_container.trade_result is not None
        assert context_with_container.trade_result.get('success') is True
        assert 'trade_id' in context_with_container.trade_result


@pytest.mark.integration
class TestExecutionStageSellFlow:
    """ExecutionStage 매도 흐름 테스트"""

    @pytest.fixture
    def mock_container_for_sell(self):
        """매도용 Mock Container"""
        container = MagicMock()

        # ExecuteTradeUseCase Mock
        mock_trade_use_case = AsyncMock()
        mock_trade_use_case.execute_sell_all = AsyncMock(return_value=MagicMock(
            success=True,
            order_id="sell-order-456",
            executed_price=Money.krw(Decimal("51000000")),
            executed_volume=Decimal("0.01"),
            fee=Money.krw(Decimal("250")),
            error_message=None,
        ))
        container.get_execute_trade_use_case = MagicMock(
            return_value=mock_trade_use_case
        )

        # ExchangePort Mock
        mock_exchange = AsyncMock()
        mock_exchange.get_current_price = AsyncMock(
            return_value=Money.krw(Decimal("51000000"))
        )
        mock_exchange.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("0"))
        ))
        container.get_exchange_port = MagicMock(return_value=mock_exchange)

        return container

    @pytest.mark.asyncio
    async def test_sell_uses_execute_sell_all(self, mock_container_for_sell):
        """sell 결정 시 execute_sell_all 호출 확인"""
        # Given: sell 결정
        mock_exchange = mock_container_for_sell.get_exchange_port()

        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-BTC"
        context.ai_result = {'decision': 'sell'}
        context.container = mock_container_for_sell
        context.risk_manager = None
        context.position_info = {'avg_buy_price': 50000000}
        context.get_exchange_port = MagicMock(return_value=mock_exchange)

        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = MagicMock(success=True)
                await stage.execute(context)

        # Then: execute_sell_all 호출됨
        mock_trade = mock_container_for_sell.get_execute_trade_use_case()
        mock_trade.execute_sell_all.assert_called_once_with("KRW-BTC")


@pytest.mark.integration
class TestExecutionStageLegacyFallback:
    """레거시 경로 fallback 테스트"""

    @pytest.fixture
    def context_without_container(self):
        """Container가 없는 컨텍스트 (레거시 경로)"""
        mock_exchange = AsyncMock()
        mock_exchange.get_current_price = AsyncMock(
            return_value=Money.krw(Decimal("50000000"))
        )
        mock_exchange.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("1000000"))
        ))

        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-BTC"
        context.ai_result = {'decision': 'buy'}
        context.container = None  # Container 없음
        context.trading_service = MagicMock()  # 레거시 서비스
        context.risk_manager = None
        context.get_exchange_port = MagicMock(return_value=mock_exchange)

        return context

    @pytest.mark.asyncio
    async def test_falls_back_to_legacy_service(self, context_without_container):
        """Container 없을 때 레거시 서비스 사용 확인"""
        # Given: Container 없음
        stage = ExecutionStage()

        # When: 실행
        with patch.object(stage, '_print_current_status', new_callable=AsyncMock):
            with patch.object(stage, '_create_result', new_callable=AsyncMock) as mock_result:
                mock_result.return_value = MagicMock(success=True)
                await stage.execute(context_without_container)

        # Then: 레거시 서비스의 execute_buy 호출
        context_without_container.trading_service.execute_buy.assert_called_once()

    def test_has_use_case_returns_false_without_container(self):
        """Container 없으면 _has_use_case()가 False 반환"""
        # Given: Container 없는 context
        context = MagicMock()
        context.container = None

        stage = ExecutionStage()

        # When/Then
        assert stage._has_use_case(context) is False

    def test_has_use_case_returns_true_with_container(self):
        """Container 있으면 _has_use_case()가 True 반환"""
        # Given: Container 있는 context
        context = MagicMock()
        context.container = MagicMock()

        stage = ExecutionStage()

        # When/Then
        assert stage._has_use_case(context) is True
