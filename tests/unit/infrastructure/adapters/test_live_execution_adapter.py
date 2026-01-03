"""
LiveExecutionAdapter 테스트 (TDD - Red Phase)

실시간 거래용 ExecutionPort 구현 테스트.

테스트 시나리오:
1. 시장가 매수 주문 실행
2. 시장가 매도 주문 실행
3. 슬리피지 반영
4. 실행 실패 처리
5. 스탑로스 트리거 확인 (실시간 가격 기반)
6. 익절 트리거 확인
7. 슬리피지 반영 체결가 계산
8. 체결 결과에 모든 필드 포함
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.domain.entities import OrderSide
from src.domain.value_objects import Money, Currency
from src.application.ports.outbound.execution_port import (
    ExecutionPort,
    ExecutionResult,
    CandleData,
)
from src.application.dto.trading import OrderResponse


class TestLiveExecutionAdapterMarketOrder:
    """시장가 주문 실행 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        """ExchangePort mock"""
        from src.application.ports.outbound.exchange_port import ExchangePort

        mock = MagicMock(spec=ExchangePort)
        # Mock async methods
        mock.get_current_price = AsyncMock(return_value=Money(Decimal("50000000"), Currency.KRW))
        mock.get_balance = AsyncMock()
        mock.execute_market_buy = AsyncMock()
        mock.execute_market_sell = AsyncMock()
        return mock

    @pytest.fixture
    def sample_candle(self):
        """테스트용 캔들 데이터"""
        return CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("50000000"), Currency.KRW),
            high=Money(Decimal("51000000"), Currency.KRW),
            low=Money(Decimal("49000000"), Currency.KRW),
            close=Money(Decimal("50500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

    @pytest.fixture
    def adapter(self, mock_exchange_port):
        """LiveExecutionAdapter 인스턴스"""
        from src.infrastructure.adapters.execution.live_execution_adapter import LiveExecutionAdapter
        return LiveExecutionAdapter(exchange_port=mock_exchange_port)

    def test_execute_market_buy_order(self, adapter, sample_candle):
        """
        시장가 매수 주문 실행

        Given: 유효한 주문 파라미터
        When: execute_market_order(BUY) 호출
        Then: 성공적인 ExecutionResult 반환
        """
        # When
        result = adapter.execute_market_order(
            side=OrderSide.BUY,
            size=Decimal("0.001"),
            expected_price=Money(Decimal("50000000"), Currency.KRW),
            candle=sample_candle,
            slippage_pct=Decimal("0.0001"),
        )

        # Then
        assert result.success is True
        assert result.executed_price is not None
        assert result.executed_size == Decimal("0.001")
        assert result.slippage is not None

    def test_execute_market_sell_order(self, adapter, sample_candle):
        """
        시장가 매도 주문 실행

        Given: 유효한 주문 파라미터
        When: execute_market_order(SELL) 호출
        Then: 성공적인 ExecutionResult 반환
        """
        # When
        result = adapter.execute_market_order(
            side=OrderSide.SELL,
            size=Decimal("0.001"),
            expected_price=Money(Decimal("50000000"), Currency.KRW),
            candle=sample_candle,
            slippage_pct=Decimal("0.0001"),
        )

        # Then
        assert result.success is True
        assert result.executed_price is not None
        assert result.executed_size == Decimal("0.001")

    def test_execution_with_slippage(self, adapter, sample_candle):
        """
        슬리피지 반영 확인

        Given: 슬리피지 비율 0.1%
        When: 매수 주문 실행
        Then: 체결가에 슬리피지 반영 (시가보다 높은 가격)
        """
        # When
        result = adapter.execute_market_order(
            side=OrderSide.BUY,
            size=Decimal("0.001"),
            expected_price=sample_candle.open,
            candle=sample_candle,
            slippage_pct=Decimal("0.001"),  # 0.1%
        )

        # Then
        assert result.success is True
        # 매수 시 슬리피지로 인해 더 높은 가격으로 체결
        assert result.executed_price > sample_candle.open

    def test_sell_slippage_lower_price(self, adapter, sample_candle):
        """
        매도 시 슬리피지는 더 낮은 가격으로 반영

        Given: 슬리피지 비율 0.1%
        When: 매도 주문 실행
        Then: 체결가에 슬리피지 반영 (시가보다 낮은 가격)
        """
        # When
        result = adapter.execute_market_order(
            side=OrderSide.SELL,
            size=Decimal("0.001"),
            expected_price=sample_candle.open,
            candle=sample_candle,
            slippage_pct=Decimal("0.001"),  # 0.1%
        )

        # Then
        assert result.success is True
        # 매도 시 슬리피지로 인해 더 낮은 가격으로 체결
        assert result.executed_price < sample_candle.open


class TestLiveExecutionAdapterStopLossTakeProfit:
    """스탑로스/익절 트리거 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        """ExchangePort mock"""
        from src.application.ports.outbound.exchange_port import ExchangePort

        mock = MagicMock(spec=ExchangePort)
        mock.get_current_price = AsyncMock()
        return mock

    @pytest.fixture
    def adapter(self, mock_exchange_port):
        """LiveExecutionAdapter 인스턴스"""
        from src.infrastructure.adapters.execution.live_execution_adapter import LiveExecutionAdapter
        return LiveExecutionAdapter(exchange_port=mock_exchange_port)

    def test_check_stop_loss_triggered_when_low_below_stop(self, adapter):
        """
        캔들 저점이 스탑가 이하일 때 스탑로스 트리거

        Given: 스탑가 49,500,000 KRW
        When: 캔들 저점이 49,000,000 KRW (스탑가 이하)
        Then: True 반환
        """
        # Given
        stop_price = Money(Decimal("49500000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("50000000"), Currency.KRW),
            high=Money(Decimal("51000000"), Currency.KRW),
            low=Money(Decimal("49000000"), Currency.KRW),  # 스탑가 이하
            close=Money(Decimal("50500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        triggered = adapter.check_stop_loss_triggered(stop_price, candle)

        # Then
        assert triggered is True

    def test_check_stop_loss_not_triggered_when_low_above_stop(self, adapter):
        """
        캔들 저점이 스탑가 초과일 때 스탑로스 트리거 안됨

        Given: 스탑가 48,000,000 KRW
        When: 캔들 저점이 49,000,000 KRW (스탑가 초과)
        Then: False 반환
        """
        # Given
        stop_price = Money(Decimal("48000000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("50000000"), Currency.KRW),
            high=Money(Decimal("51000000"), Currency.KRW),
            low=Money(Decimal("49000000"), Currency.KRW),  # 스탑가 초과
            close=Money(Decimal("50500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        triggered = adapter.check_stop_loss_triggered(stop_price, candle)

        # Then
        assert triggered is False

    def test_check_take_profit_triggered_when_high_above_tp(self, adapter):
        """
        캔들 고점이 익절가 이상일 때 익절 트리거

        Given: 익절가 50,500,000 KRW
        When: 캔들 고점이 51,000,000 KRW (익절가 이상)
        Then: True 반환
        """
        # Given
        take_profit_price = Money(Decimal("50500000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("50000000"), Currency.KRW),
            high=Money(Decimal("51000000"), Currency.KRW),  # 익절가 이상
            low=Money(Decimal("49000000"), Currency.KRW),
            close=Money(Decimal("50500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        triggered = adapter.check_take_profit_triggered(take_profit_price, candle)

        # Then
        assert triggered is True

    def test_check_take_profit_not_triggered_when_high_below_tp(self, adapter):
        """
        캔들 고점이 익절가 미만일 때 익절 트리거 안됨

        Given: 익절가 52,000,000 KRW
        When: 캔들 고점이 51,000,000 KRW (익절가 미만)
        Then: False 반환
        """
        # Given
        take_profit_price = Money(Decimal("52000000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("50000000"), Currency.KRW),
            high=Money(Decimal("51000000"), Currency.KRW),  # 익절가 미만
            low=Money(Decimal("49000000"), Currency.KRW),
            close=Money(Decimal("50500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        triggered = adapter.check_take_profit_triggered(take_profit_price, candle)

        # Then
        assert triggered is False


class TestLiveExecutionAdapterExecutionPrice:
    """체결 가격 계산 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        """ExchangePort mock"""
        from src.application.ports.outbound.exchange_port import ExchangePort
        return MagicMock(spec=ExchangePort)

    @pytest.fixture
    def adapter(self, mock_exchange_port):
        """LiveExecutionAdapter 인스턴스"""
        from src.infrastructure.adapters.execution.live_execution_adapter import LiveExecutionAdapter
        return LiveExecutionAdapter(exchange_port=mock_exchange_port)

    def test_get_stop_loss_execution_price_normal(self, adapter):
        """
        정상 상황에서 스탑로스 체결가는 스탑가

        Given: 시가가 스탑가보다 높음
        When: 스탑로스 체결가 계산
        Then: 스탑가 반환
        """
        # Given
        stop_price = Money(Decimal("49000000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("50000000"), Currency.KRW),  # 시가 > 스탑가
            high=Money(Decimal("51000000"), Currency.KRW),
            low=Money(Decimal("48500000"), Currency.KRW),
            close=Money(Decimal("49500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        execution_price = adapter.get_stop_loss_execution_price(stop_price, candle)

        # Then
        assert execution_price == stop_price

    def test_get_stop_loss_execution_price_gap_down(self, adapter):
        """
        갭 하락 시 스탑로스 체결가는 시가 (더 나쁜 가격)

        Given: 시가가 스탑가보다 낮음 (갭 하락)
        When: 스탑로스 체결가 계산
        Then: 시가 반환 (스탑가보다 나쁜 가격)
        """
        # Given
        stop_price = Money(Decimal("49000000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("48000000"), Currency.KRW),  # 시가 < 스탑가 (갭 하락)
            high=Money(Decimal("49000000"), Currency.KRW),
            low=Money(Decimal("47500000"), Currency.KRW),
            close=Money(Decimal("48500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        execution_price = adapter.get_stop_loss_execution_price(stop_price, candle)

        # Then
        assert execution_price == candle.open  # 갭 하락으로 시가 체결

    def test_get_take_profit_execution_price_normal(self, adapter):
        """
        정상 상황에서 익절 체결가는 익절가

        Given: 시가가 익절가보다 낮음
        When: 익절 체결가 계산
        Then: 익절가 반환
        """
        # Given
        take_profit_price = Money(Decimal("52000000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("50000000"), Currency.KRW),  # 시가 < 익절가
            high=Money(Decimal("53000000"), Currency.KRW),
            low=Money(Decimal("49500000"), Currency.KRW),
            close=Money(Decimal("52500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        execution_price = adapter.get_take_profit_execution_price(take_profit_price, candle)

        # Then
        assert execution_price == take_profit_price

    def test_get_take_profit_execution_price_gap_up(self, adapter):
        """
        갭 상승 시 익절 체결가는 시가 (더 좋은 가격)

        Given: 시가가 익절가보다 높음 (갭 상승)
        When: 익절 체결가 계산
        Then: 시가 반환 (익절가보다 좋은 가격)
        """
        # Given
        take_profit_price = Money(Decimal("51000000"), Currency.KRW)
        candle = CandleData(
            timestamp=datetime.utcnow(),
            open=Money(Decimal("52000000"), Currency.KRW),  # 시가 > 익절가 (갭 상승)
            high=Money(Decimal("53000000"), Currency.KRW),
            low=Money(Decimal("51500000"), Currency.KRW),
            close=Money(Decimal("52500000"), Currency.KRW),
            volume=Decimal("100.5"),
        )

        # When
        execution_price = adapter.get_take_profit_execution_price(take_profit_price, candle)

        # Then
        assert execution_price == candle.open  # 갭 상승으로 시가 체결


class TestLiveExecutionAdapterRealTimePrice:
    """실시간 가격 기반 기능 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        """ExchangePort mock"""
        from src.application.ports.outbound.exchange_port import ExchangePort

        mock = MagicMock(spec=ExchangePort)
        mock.get_current_price = AsyncMock(return_value=Money(Decimal("50000000"), Currency.KRW))
        return mock

    @pytest.fixture
    def adapter(self, mock_exchange_port):
        """LiveExecutionAdapter 인스턴스"""
        from src.infrastructure.adapters.execution.live_execution_adapter import LiveExecutionAdapter
        return LiveExecutionAdapter(exchange_port=mock_exchange_port)

    @pytest.mark.asyncio
    async def test_check_stop_loss_triggered_realtime(self, adapter, mock_exchange_port):
        """
        실시간 가격 기반 스탑로스 트리거 확인

        Given: 현재가 49,000,000 KRW, 스탑가 49,500,000 KRW
        When: check_stop_loss_triggered_realtime() 호출
        Then: True 반환 (현재가 <= 스탑가)
        """
        # Given
        mock_exchange_port.get_current_price = AsyncMock(
            return_value=Money(Decimal("49000000"), Currency.KRW)
        )
        ticker = "KRW-BTC"
        stop_price = Money(Decimal("49500000"), Currency.KRW)

        # When
        triggered = await adapter.check_stop_loss_triggered_realtime(ticker, stop_price)

        # Then
        assert triggered is True
        mock_exchange_port.get_current_price.assert_called_once_with(ticker)

    @pytest.mark.asyncio
    async def test_check_stop_loss_not_triggered_realtime(self, adapter, mock_exchange_port):
        """
        현재가가 스탑가보다 높을 때 트리거 안됨

        Given: 현재가 50,000,000 KRW, 스탑가 49,000,000 KRW
        When: check_stop_loss_triggered_realtime() 호출
        Then: False 반환
        """
        # Given
        mock_exchange_port.get_current_price = AsyncMock(
            return_value=Money(Decimal("50000000"), Currency.KRW)
        )
        ticker = "KRW-BTC"
        stop_price = Money(Decimal("49000000"), Currency.KRW)

        # When
        triggered = await adapter.check_stop_loss_triggered_realtime(ticker, stop_price)

        # Then
        assert triggered is False

    @pytest.mark.asyncio
    async def test_check_take_profit_triggered_realtime(self, adapter, mock_exchange_port):
        """
        실시간 가격 기반 익절 트리거 확인

        Given: 현재가 52,000,000 KRW, 익절가 51,000,000 KRW
        When: check_take_profit_triggered_realtime() 호출
        Then: True 반환 (현재가 >= 익절가)
        """
        # Given
        mock_exchange_port.get_current_price = AsyncMock(
            return_value=Money(Decimal("52000000"), Currency.KRW)
        )
        ticker = "KRW-BTC"
        take_profit_price = Money(Decimal("51000000"), Currency.KRW)

        # When
        triggered = await adapter.check_take_profit_triggered_realtime(ticker, take_profit_price)

        # Then
        assert triggered is True

    @pytest.mark.asyncio
    async def test_execute_market_buy_realtime(self, adapter, mock_exchange_port):
        """
        실시간 시장가 매수 실행

        Given: ExchangePort가 주문 성공 응답 반환
        When: execute_market_buy_realtime() 호출
        Then: OrderResponse 반환
        """
        # Given
        from src.application.dto.trading import OrderResponse

        mock_response = OrderResponse(
            success=True,
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_id="order123",
            executed_price=Money(Decimal("50000000"), Currency.KRW),
            executed_volume=Decimal("0.001"),
            fee=Money(Decimal("50"), Currency.KRW),
        )
        mock_exchange_port.execute_market_buy = AsyncMock(return_value=mock_response)

        ticker = "KRW-BTC"
        amount = Money(Decimal("50000"), Currency.KRW)

        # When
        result = await adapter.execute_market_buy_realtime(ticker, amount)

        # Then
        assert result.success is True
        assert result.order_id == "order123"
        mock_exchange_port.execute_market_buy.assert_called_once_with(ticker, amount)

    @pytest.mark.asyncio
    async def test_execute_market_sell_realtime(self, adapter, mock_exchange_port):
        """
        실시간 시장가 매도 실행

        Given: ExchangePort가 주문 성공 응답 반환
        When: execute_market_sell_realtime() 호출
        Then: OrderResponse 반환
        """
        # Given
        from src.application.dto.trading import OrderResponse

        mock_response = OrderResponse(
            success=True,
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            order_id="order456",
            executed_price=Money(Decimal("50000000"), Currency.KRW),
            executed_volume=Decimal("0.001"),
            fee=Money(Decimal("50"), Currency.KRW),
        )
        mock_exchange_port.execute_market_sell = AsyncMock(return_value=mock_response)

        ticker = "KRW-BTC"
        volume = Decimal("0.001")

        # When
        result = await adapter.execute_market_sell_realtime(ticker, volume)

        # Then
        assert result.success is True
        assert result.order_id == "order456"
        mock_exchange_port.execute_market_sell.assert_called_once_with(ticker, volume)


class TestLiveExecutionAdapterInheritance:
    """ExecutionPort 상속 확인 테스트"""

    def test_adapter_implements_execution_port(self):
        """
        LiveExecutionAdapter가 ExecutionPort를 상속하는지 확인
        """
        from src.infrastructure.adapters.execution.live_execution_adapter import LiveExecutionAdapter
        from src.application.ports.outbound.execution_port import ExecutionPort
        from src.application.ports.outbound.exchange_port import ExchangePort

        mock_exchange = MagicMock(spec=ExchangePort)
        adapter = LiveExecutionAdapter(exchange_port=mock_exchange)

        assert isinstance(adapter, ExecutionPort)
