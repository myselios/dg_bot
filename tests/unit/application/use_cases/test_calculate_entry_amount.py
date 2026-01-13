"""
CalculateEntryAmountUseCase 테스트

TDD 방식으로 작성된 테스트입니다.
진입 금액 계산 UseCase의 동작을 검증합니다.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.application.use_cases.calculate_entry_amount import CalculateEntryAmountUseCase
from src.application.dto.trading import PositionInfo
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.position_sizing import PositionSizingPolicy


def create_position_info(
    ticker: str,
    volume: Decimal,
    avg_buy_price: Decimal,
    current_price: Decimal = None,
) -> PositionInfo:
    """
    테스트용 PositionInfo 헬퍼 함수

    모든 필수 필드를 자동으로 계산합니다.
    """
    if current_price is None:
        current_price = avg_buy_price

    symbol = ticker.replace("KRW-", "")
    total_cost = avg_buy_price * volume
    current_value = current_price * volume
    profit_loss = current_value - total_cost
    profit_rate = (profit_loss / total_cost * 100) if total_cost > 0 else Decimal("0")

    return PositionInfo(
        ticker=ticker,
        symbol=symbol,
        volume=volume,
        avg_buy_price=Money.krw(avg_buy_price),
        current_price=Money.krw(current_price),
        profit_loss=Money.krw(profit_loss),
        profit_rate=profit_rate,
        total_cost=Money.krw(total_cost),
        current_value=Money.krw(current_value),
    )


class TestCalculateEntryAmountUseCase:
    """CalculateEntryAmountUseCase 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        """Mock ExchangePort 생성"""
        mock = AsyncMock()
        mock.get_balance = AsyncMock()
        mock.get_all_positions = AsyncMock()
        mock.get_current_price = AsyncMock()
        return mock

    @pytest.fixture
    def use_case(self, mock_exchange_port):
        """기본 정책으로 UseCase 생성"""
        return CalculateEntryAmountUseCase(
            exchange=mock_exchange_port,
            policy=PositionSizingPolicy.default(),
        )

    # --- 기본 동작 테스트 ---

    @pytest.mark.asyncio
    async def test_execute_no_positions(self, use_case, mock_exchange_port):
        """
        포지션 없을 때 진입 금액 계산

        조건:
        - KRW 잔고: 1,000,000원
        - 포지션: 없음 (0개)

        예상 계산:
        - 총 자본: 1,000,000
        - 예비금: 100,000 (10%)
        - 가용: 900,000
        - 최대 배분: 400,000 (40%)
        - 슬롯 3개 → 400,000 / 3 = 133,333
        """
        # Given
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = []

        # When
        result = await use_case.execute("KRW-BTC")

        # Then
        assert result.currency == Currency.KRW
        assert result.amount == Decimal("133333")

    @pytest.mark.asyncio
    async def test_execute_with_existing_positions(self, use_case, mock_exchange_port):
        """
        기존 포지션 있을 때 진입 금액 계산

        조건:
        - KRW 잔고: 600,000원
        - 기존 포지션: ETH 400,000원 (1개)
        - 총 자본: 1,000,000원

        예상 계산:
        - 예비금: 100,000 (10%)
        - 가용: 600,000 - 100,000 = 500,000
        - 최대 배분: 400,000 (40%)
        - 슬롯 2개 → 400,000 / 2 = 200,000
        """
        # Given
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("600000"))
        )
        mock_exchange_port.get_all_positions.return_value = [
            create_position_info(
                ticker="KRW-ETH",
                volume=Decimal("0.1"),
                avg_buy_price=Decimal("4000000"),
                current_price=Decimal("4000000"),
            )
        ]

        # When
        result = await use_case.execute("KRW-BTC")

        # Then
        assert result.amount == Decimal("200000")

    @pytest.mark.asyncio
    async def test_execute_max_positions_reached(self, use_case, mock_exchange_port):
        """최대 포지션 도달 시 0 반환"""
        # Given
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("500000"))
        )
        # 3개 포지션 (기본 max_positions = 3)
        mock_exchange_port.get_all_positions.return_value = [
            create_position_info("KRW-BTC", Decimal("0.01"), Decimal("50000000")),
            create_position_info("KRW-ETH", Decimal("0.1"), Decimal("3000000")),
            create_position_info("KRW-XRP", Decimal("1000"), Decimal("500")),
        ]

        # When
        result = await use_case.execute("KRW-DOGE")

        # Then
        assert result.is_zero()

    @pytest.mark.asyncio
    async def test_execute_already_has_ticker_position(self, use_case, mock_exchange_port):
        """이미 해당 코인 보유 시 0 반환 (추가 매수 불가)"""
        # Given
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = [
            create_position_info(
                ticker="KRW-BTC",  # 이미 BTC 보유
                volume=Decimal("0.01"),
                avg_buy_price=Decimal("50000000"),
            )
        ]

        # When
        result = await use_case.execute("KRW-BTC")  # 동일 코인 진입 시도

        # Then
        assert result.is_zero()

    @pytest.mark.asyncio
    async def test_execute_insufficient_krw(self, use_case, mock_exchange_port):
        """KRW 잔고 부족 시 0 반환"""
        # Given: 예비금보다 적은 잔고
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("50000"))  # 50,000원
        )
        mock_exchange_port.get_all_positions.return_value = [
            create_position_info(
                ticker="KRW-ETH",
                volume=Decimal("0.1"),
                avg_buy_price=Decimal("9000000"),
            )
        ]
        # 총 자본: 950,000, 예비금: 95,000 > 현금 50,000

        # When
        result = await use_case.execute("KRW-BTC")

        # Then
        assert result.is_zero()

    # --- 상세 정보 테스트 ---

    @pytest.mark.asyncio
    async def test_execute_with_details(self, use_case, mock_exchange_port):
        """상세 정보 반환 테스트"""
        # Given
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = []

        # When
        result = await use_case.execute_with_details("KRW-BTC")

        # Then
        assert "entry_amount" in result
        assert "current_krw" in result
        assert "total_capital" in result
        assert "position_count" in result
        assert "remaining_slots" in result
        assert "can_enter" in result
        assert "policy" in result

        assert result["current_krw"] == Decimal("1000000")
        assert result["position_count"] == 0
        assert result["remaining_slots"] == 3
        assert result["can_enter"] is True

    # --- 정책 변경 테스트 ---

    @pytest.mark.asyncio
    async def test_with_conservative_policy(self, mock_exchange_port):
        """보수적 정책 적용 테스트"""
        # Given
        use_case = CalculateEntryAmountUseCase(
            exchange=mock_exchange_port,
            policy=PositionSizingPolicy.conservative(),
        )
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = []

        # When
        result = await use_case.execute("KRW-BTC")

        # Then
        # 보수적: 20% 배분, 20% 예비금, 2 포지션
        # 예비금: 200,000, 가용: 800,000, 최대배분: 200,000
        # 200,000 / 2 = 100,000
        assert result.amount == Decimal("100000")

    @pytest.mark.asyncio
    async def test_with_aggressive_policy(self, mock_exchange_port):
        """공격적 정책 적용 테스트"""
        # Given
        use_case = CalculateEntryAmountUseCase(
            exchange=mock_exchange_port,
            policy=PositionSizingPolicy.aggressive(),
        )
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = []

        # When
        result = await use_case.execute("KRW-BTC")

        # Then
        # 공격적: 50% 배분, 5% 예비금, 4 포지션
        # 예비금: 50,000, 가용: 950,000, 최대배분: 500,000
        # 500,000 / 4 = 125,000
        assert result.amount == Decimal("125000")

    @pytest.mark.asyncio
    async def test_with_policy_method(self, use_case, mock_exchange_port):
        """with_policy()로 정책 변경 테스트"""
        # Given
        new_policy = PositionSizingPolicy.single_position()
        new_use_case = use_case.with_policy(new_policy)

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = []

        # When
        result = await new_use_case.execute("KRW-BTC")

        # Then
        # 단일 포지션: 90% 배분, 5% 예비금, 1 포지션
        # 예비금: 50,000, 가용: 950,000, 최대배분: 900,000
        # 900,000 / 1 = 900,000
        assert result.amount == Decimal("900000")

    # --- can_open_position 테스트 ---

    @pytest.mark.asyncio
    async def test_can_open_position_true(self, use_case, mock_exchange_port):
        """진입 가능 여부 확인 - True"""
        # Given
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = []

        # When
        result = await use_case.can_open_position("KRW-BTC")

        # Then
        assert result is True

    @pytest.mark.asyncio
    async def test_can_open_position_false(self, use_case, mock_exchange_port):
        """진입 가능 여부 확인 - False"""
        # Given: 최대 포지션 도달
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("100000"))
        )
        mock_exchange_port.get_all_positions.return_value = [
            create_position_info("KRW-BTC", Decimal("0.01"), Decimal("50000000")),
            create_position_info("KRW-ETH", Decimal("0.1"), Decimal("3000000")),
            create_position_info("KRW-XRP", Decimal("1000"), Decimal("500")),
        ]

        # When
        result = await use_case.can_open_position("KRW-DOGE")

        # Then
        assert result is False

    # --- 총 자본 계산 테스트 ---

    @pytest.mark.asyncio
    async def test_total_capital_calculation(self, use_case, mock_exchange_port):
        """총 자본 계산 (현금 + 투자금)"""
        # Given
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("500000"))
        )
        mock_exchange_port.get_all_positions.return_value = [
            create_position_info(
                ticker="KRW-BTC",
                volume=Decimal("0.01"),
                avg_buy_price=Decimal("50000000"),
                current_price=Decimal("50000000"),
            )
        ]

        # When
        result = await use_case.execute_with_details("KRW-ETH")

        # Then
        # 총 자본 = 500,000 (현금) + 500,000 (BTC 평가액) = 1,000,000
        assert result["total_capital"] == Decimal("1000000")


class TestPositionInfoHandling:
    """PositionInfo 처리 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        mock = AsyncMock()
        mock.get_balance = AsyncMock()
        mock.get_all_positions = AsyncMock()
        mock.get_current_price = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_handles_zero_volume_position(self, mock_exchange_port):
        """volume이 0인 포지션은 무시"""
        # Given
        use_case = CalculateEntryAmountUseCase(exchange=mock_exchange_port)
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.get_all_positions.return_value = [
            create_position_info(
                ticker="KRW-BTC",
                volume=Decimal("0"),  # 0 volume
                avg_buy_price=Decimal("50000000"),
            )
        ]

        # When
        result = await use_case.execute("KRW-BTC")

        # Then
        # 0 volume 포지션은 보유로 취급하지 않음
        assert result.is_positive()
