"""
ExecutionStage UseCase 통합 테스트

TDD RED Phase: ExecutionStage가 ExecuteTradeUseCase를 사용하도록 마이그레이션

테스트 시나리오:
1. ExecutionStage가 Container에서 UseCase를 받을 수 있는지 확인
2. 매수 결정 시 UseCase.execute_buy() 호출 확인
3. 매도 결정 시 UseCase.execute_sell() 호출 확인
4. 보류 결정 시 아무 주문도 실행하지 않음 확인
5. 에러 핸들링 테스트
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.trading.pipeline.execution_stage import ExecutionStage
from src.trading.pipeline.base_stage import PipelineContext, StageResult
from src.container import Container
from src.application.use_cases.execute_trade import ExecuteTradeUseCase
from src.application.dto.trading import OrderResponse
from src.domain.entities.trade import OrderSide
from src.domain.value_objects.money import Money, Currency


class TestExecutionStageWithUseCase:
    """ExecutionStage + UseCase 통합 테스트"""

    @pytest.fixture
    def mock_container(self):
        """Container with mock UseCase"""
        mock_use_case = MagicMock(spec=ExecuteTradeUseCase)
        mock_use_case.execute_buy = AsyncMock()
        mock_use_case.execute_sell = AsyncMock()

        container = MagicMock(spec=Container)
        container.get_execute_trade_use_case.return_value = mock_use_case

        return container, mock_use_case

    @pytest.fixture
    def mock_context(self, mock_container):
        """PipelineContext with Container"""
        container, _ = mock_container

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container,
            upbit_client=MagicMock(),
            trading_service=MagicMock(),
        )

        # Mock 반환값 설정
        context.upbit_client.get_current_price.return_value = 50000000
        context.upbit_client.get_balance.return_value = 1000000

        return context

    @pytest.mark.asyncio
    async def test_execution_stage_uses_container_use_case_for_buy(
        self, mock_context, mock_container
    ):
        """매수 시 Container의 UseCase를 사용하는지 확인"""
        _, mock_use_case = mock_container

        # Given: AI 결정이 buy
        mock_context.ai_result = {
            "decision": "buy",
            "confidence": "high",
            "reason": "테스트 매수"
        }

        # UseCase 응답 설정
        mock_use_case.execute_buy.return_value = OrderResponse(
            success=True,
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_id="test-order-123",
            executed_price=Money(Decimal("50000000"), Currency.KRW),
            executed_volume=Decimal("0.002"),
            fee=Money(Decimal("500"), Currency.KRW),
        )

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        result = await stage.execute(mock_context)

        # Then: UseCase.execute_buy()가 호출되어야 함
        mock_use_case.execute_buy.assert_called_once()
        call_args = mock_use_case.execute_buy.call_args
        assert call_args.args[0] == "KRW-BTC"  # ticker
        # amount는 Money 타입이어야 함

    @pytest.mark.asyncio
    async def test_execution_stage_uses_container_use_case_for_sell(
        self, mock_context, mock_container
    ):
        """매도 시 Container의 UseCase를 사용하는지 확인"""
        _, mock_use_case = mock_container

        # Given: AI 결정이 sell
        mock_context.ai_result = {
            "decision": "sell",
            "confidence": "high",
            "reason": "테스트 매도"
        }
        mock_context.position_info = {
            "avg_buy_price": 48000000,
            "volume": Decimal("0.002")
        }

        # UseCase 응답 설정 (전량 매도 메서드)
        mock_use_case.execute_sell_all = AsyncMock(return_value=OrderResponse(
            success=True,
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            order_id="test-order-456",
            executed_price=Money(Decimal("51000000"), Currency.KRW),
            executed_volume=Decimal("0.002"),
            fee=Money(Decimal("510"), Currency.KRW),
        ))

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        result = await stage.execute(mock_context)

        # Then: UseCase.execute_sell_all()가 호출되어야 함
        mock_use_case.execute_sell_all.assert_called_once_with("KRW-BTC")

    @pytest.mark.asyncio
    async def test_execution_stage_hold_does_not_call_use_case(
        self, mock_context, mock_container
    ):
        """보류 시 UseCase가 호출되지 않아야 함"""
        _, mock_use_case = mock_container

        # Given: AI 결정이 hold
        mock_context.ai_result = {
            "decision": "hold",
            "confidence": "medium",
            "reason": "관망 필요"
        }

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        result = await stage.execute(mock_context)

        # Then: UseCase가 호출되지 않아야 함
        mock_use_case.execute_buy.assert_not_called()
        mock_use_case.execute_sell.assert_not_called()

    @pytest.mark.asyncio
    async def test_execution_stage_returns_order_response_data(
        self, mock_context, mock_container
    ):
        """OrderResponse 데이터가 StageResult에 포함되어야 함"""
        _, mock_use_case = mock_container

        # Given: 성공적인 매수
        mock_context.ai_result = {"decision": "buy", "confidence": "high", "reason": ""}

        mock_use_case.execute_buy.return_value = OrderResponse(
            success=True,
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_id="test-order-789",
            executed_price=Money(Decimal("50000000"), Currency.KRW),
            executed_volume=Decimal("0.002"),
            fee=Money(Decimal("500"), Currency.KRW),
        )

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        result = await stage.execute(mock_context)

        # Then: 결과에 OrderResponse 정보가 포함되어야 함
        assert result.success is True
        assert result.data.get('trade_id') == "test-order-789"
        assert result.data.get('trade_success') is True


class TestExecutionStageBackwardCompatibility:
    """레거시 호환성 테스트"""

    @pytest.fixture
    def legacy_context(self):
        """Container 없는 레거시 PipelineContext"""
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=None,  # Container 없음
            upbit_client=MagicMock(),
            trading_service=MagicMock(),
        )

        context.upbit_client.get_current_price.return_value = 50000000
        context.upbit_client.get_balance.return_value = 1000000

        return context

    @pytest.mark.asyncio
    async def test_execution_stage_falls_back_to_trading_service(
        self, legacy_context
    ):
        """Container 없으면 레거시 trading_service 사용"""
        # Given: AI 결정이 buy, Container 없음
        legacy_context.ai_result = {
            "decision": "buy",
            "confidence": "high",
            "reason": "테스트"
        }
        legacy_context.trading_service.execute_buy.return_value = {
            "success": True,
            "trade_id": "legacy-order",
            "fee": 500
        }

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        result = await stage.execute(legacy_context)

        # Then: 레거시 trading_service가 호출되어야 함
        legacy_context.trading_service.execute_buy.assert_called_once_with("KRW-BTC")


class TestExecutionStageErrorHandling:
    """에러 핸들링 테스트"""

    @pytest.fixture
    def error_container(self):
        """에러를 발생시키는 UseCase"""
        mock_use_case = MagicMock(spec=ExecuteTradeUseCase)
        mock_use_case.execute_buy = AsyncMock(
            return_value=OrderResponse(
                success=False,
                ticker="KRW-BTC",
                side=OrderSide.BUY,
                error_message="잔고 부족"
            )
        )

        container = MagicMock(spec=Container)
        container.get_execute_trade_use_case.return_value = mock_use_case

        return container

    @pytest.mark.asyncio
    async def test_execution_stage_handles_use_case_failure(self, error_container):
        """UseCase 실패 시 적절히 처리"""
        # Given: 실패하는 UseCase
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=error_container,
            upbit_client=MagicMock(),
        )
        context.upbit_client.get_current_price.return_value = 50000000
        context.upbit_client.get_balance.return_value = 1000000
        context.ai_result = {"decision": "buy", "confidence": "high", "reason": ""}

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        result = await stage.execute(context)

        # Then: 실패 정보가 결과에 포함되어야 함
        assert result.success is True  # 스테이지 자체는 성공
        assert result.data.get('trade_success') is False
        assert '잔고 부족' in result.data.get('trade_error', '')

    @pytest.mark.asyncio
    async def test_execution_stage_handles_use_case_exception(self):
        """UseCase 예외 발생 시 적절히 처리"""
        # Given: 예외를 발생시키는 UseCase
        mock_use_case = MagicMock(spec=ExecuteTradeUseCase)
        mock_use_case.execute_buy = AsyncMock(side_effect=Exception("네트워크 오류"))

        container = MagicMock(spec=Container)
        container.get_execute_trade_use_case.return_value = mock_use_case

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container,
            upbit_client=MagicMock(),
        )
        context.upbit_client.get_current_price.return_value = 50000000
        context.upbit_client.get_balance.return_value = 1000000
        context.ai_result = {"decision": "buy", "confidence": "high", "reason": ""}

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        result = await stage.execute(context)

        # Then: handle_error가 호출되어 실패 결과 반환
        assert result.success is False
        assert 'error' in result.metadata


class TestExecutionStageMoneyConversion:
    """Money 객체 변환 테스트"""

    @pytest.mark.asyncio
    async def test_buy_amount_is_converted_to_money(self):
        """매수 금액이 Money 객체로 변환되어 UseCase에 전달됨"""
        # Given: Container with mock UseCase
        mock_use_case = MagicMock(spec=ExecuteTradeUseCase)
        mock_use_case.execute_buy = AsyncMock(
            return_value=OrderResponse(
                success=True,
                ticker="KRW-BTC",
                side=OrderSide.BUY,
                order_id="test",
                executed_price=Money(Decimal("50000000"), Currency.KRW),
                executed_volume=Decimal("0.002"),
                fee=Money(Decimal("500"), Currency.KRW),
            )
        )

        container = MagicMock(spec=Container)
        container.get_execute_trade_use_case.return_value = mock_use_case

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container,
            upbit_client=MagicMock(),
        )
        context.upbit_client.get_current_price.return_value = 50000000
        context.upbit_client.get_balance.return_value = 1000000
        context.ai_result = {"decision": "buy", "confidence": "high", "reason": ""}

        # When: ExecutionStage 실행
        stage = ExecutionStage()
        await stage.execute(context)

        # Then: amount가 Money 타입으로 전달되어야 함
        call_args = mock_use_case.execute_buy.call_args
        amount_arg = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get('amount')
        assert isinstance(amount_arg, Money)
        assert amount_arg.currency == Currency.KRW
