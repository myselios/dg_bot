"""
CalculateEntryAmountUseCase 통합 테스트

UseCase가 Container를 통해 올바르게 와이어링되고,
PositionSizingPolicy가 적용되는지 검증합니다.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.container import Container
from src.domain.value_objects.position_sizing import PositionSizingPolicy
from src.domain.value_objects.money import Money, Currency


@pytest.mark.integration
class TestEntryAmountIntegration:
    """진입 금액 계산 통합 테스트"""

    @pytest.fixture
    def mock_exchange_port(self):
        """Mock ExchangePort"""
        mock = AsyncMock()
        mock.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("1000000"))
        ))
        mock.get_all_positions = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def container_with_mocks(self, mock_exchange_port):
        """Mock이 주입된 Container"""
        return Container(exchange_port=mock_exchange_port)

    @pytest.mark.asyncio
    async def test_container_provides_use_case(self, container_with_mocks):
        """Container가 UseCase를 제공하는지 확인"""
        # When: UseCase 획득
        use_case = container_with_mocks.get_calculate_entry_amount_use_case()

        # Then: UseCase가 존재해야 함
        assert use_case is not None
        assert use_case.policy is not None

    @pytest.mark.asyncio
    async def test_policy_is_applied(self, container_with_mocks):
        """PositionSizingPolicy가 적용되는지 확인"""
        # Given: 기본 정책 (40% 배분, 10% 예비금, 3 포지션)
        use_case = container_with_mocks.get_calculate_entry_amount_use_case()

        # When: 진입 금액 계산 (1,000,000원, 0개 포지션)
        result = await use_case.execute("KRW-BTC")

        # Then: 정책에 따른 계산
        # 예비금: 100,000 (10%)
        # 가용: 900,000
        # 최대 배분: 400,000 (40%)
        # 슬롯 3개 → 400,000 / 3 = 133,333
        assert result.amount == Decimal("133333")

    @pytest.mark.asyncio
    async def test_custom_policy_is_respected(self, mock_exchange_port):
        """커스텀 정책이 적용되는지 확인"""
        # Given: 보수적 정책
        conservative = PositionSizingPolicy.conservative()
        container = Container(exchange_port=mock_exchange_port)
        use_case = container.get_calculate_entry_amount_use_case(
            policy=conservative
        )

        # When: 진입 금액 계산
        result = await use_case.execute("KRW-BTC")

        # Then: 보수적 정책 적용
        # 20% 배분, 20% 예비금, 2 포지션
        # 예비금: 200,000, 가용: 800,000, 최대: 200,000
        # 200,000 / 2 = 100,000
        assert result.amount == Decimal("100000")

    @pytest.mark.asyncio
    async def test_aggressive_policy(self, mock_exchange_port):
        """공격적 정책 적용 테스트"""
        # Given: 공격적 정책
        aggressive = PositionSizingPolicy.aggressive()
        container = Container(exchange_port=mock_exchange_port)
        use_case = container.get_calculate_entry_amount_use_case(
            policy=aggressive
        )

        # When: 진입 금액 계산
        result = await use_case.execute("KRW-BTC")

        # Then: 공격적 정책 적용
        # 50% 배분, 5% 예비금, 4 포지션
        # 예비금: 50,000, 가용: 950,000, 최대: 500,000
        # 500,000 / 4 = 125,000
        assert result.amount == Decimal("125000")

    @pytest.mark.asyncio
    async def test_single_position_policy(self, mock_exchange_port):
        """단일 포지션 정책 적용 테스트"""
        # Given: 단일 포지션 정책
        single = PositionSizingPolicy.single_position()
        container = Container(exchange_port=mock_exchange_port)
        use_case = container.get_calculate_entry_amount_use_case(
            policy=single
        )

        # When: 진입 금액 계산
        result = await use_case.execute("KRW-BTC")

        # Then: 단일 포지션 정책 적용
        # 90% 배분, 5% 예비금, 1 포지션
        # 예비금: 50,000, 가용: 950,000, 최대: 900,000
        # 900,000 / 1 = 900,000
        assert result.amount == Decimal("900000")

    @pytest.mark.asyncio
    async def test_use_case_is_cached(self, container_with_mocks):
        """UseCase가 캐싱되는지 확인"""
        # When: 두 번 호출
        use_case1 = container_with_mocks.get_calculate_entry_amount_use_case()
        use_case2 = container_with_mocks.get_calculate_entry_amount_use_case()

        # Then: 같은 인스턴스 반환
        assert use_case1 is use_case2

    @pytest.mark.asyncio
    async def test_custom_policy_creates_new_instance(self, mock_exchange_port):
        """커스텀 정책 시 새 인스턴스 생성 확인"""
        # Given: Container
        container = Container(exchange_port=mock_exchange_port)

        # When: 다른 정책으로 두 번 호출
        use_case1 = container.get_calculate_entry_amount_use_case()
        use_case2 = container.get_calculate_entry_amount_use_case(
            policy=PositionSizingPolicy.conservative()
        )

        # Then: 다른 인스턴스 반환
        assert use_case1 is not use_case2

    @pytest.mark.asyncio
    async def test_container_set_policy(self, mock_exchange_port):
        """Container에 정책 설정 시 적용되는지 확인"""
        # Given: Container에 정책 설정
        container = Container(exchange_port=mock_exchange_port)
        container.set_position_sizing_policy(PositionSizingPolicy.conservative())

        # When: UseCase 획득
        use_case = container.get_calculate_entry_amount_use_case()

        # When: 진입 금액 계산
        result = await use_case.execute("KRW-BTC")

        # Then: 설정된 정책 적용 (보수적: 100,000)
        assert result.amount == Decimal("100000")


@pytest.mark.integration
class TestEntryAmountWithPositions:
    """기존 포지션 있을 때 진입 금액 계산 테스트"""

    @pytest.fixture
    def create_position_info(self):
        """PositionInfo 헬퍼 함수"""
        from src.application.dto.trading import PositionInfo

        def _create(
            ticker: str,
            volume: Decimal,
            avg_buy_price: Decimal,
            current_price: Decimal = None,
        ) -> PositionInfo:
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

        return _create

    @pytest.mark.asyncio
    async def test_with_existing_positions(self, create_position_info):
        """기존 포지션 있을 때 진입 금액 계산"""
        # Given: 1개 포지션 보유
        mock_exchange = AsyncMock()
        mock_exchange.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("600000"))
        ))
        mock_exchange.get_all_positions = AsyncMock(return_value=[
            create_position_info(
                ticker="KRW-ETH",
                volume=Decimal("0.1"),
                avg_buy_price=Decimal("4000000"),
                current_price=Decimal("4000000"),
            )
        ])

        container = Container(exchange_port=mock_exchange)
        use_case = container.get_calculate_entry_amount_use_case()

        # When: 진입 금액 계산
        result = await use_case.execute("KRW-BTC")

        # Then: 기존 포지션 고려
        # 총 자본: 600,000 + 400,000 = 1,000,000
        # 예비금: 100,000 (10%)
        # 가용: 600,000 - 100,000 = 500,000
        # 최대 배분: 400,000 (40%)
        # 슬롯 2개 → 400,000 / 2 = 200,000
        assert result.amount == Decimal("200000")

    @pytest.mark.asyncio
    async def test_max_positions_reached(self, create_position_info):
        """최대 포지션 도달 시 0 반환"""
        # Given: 3개 포지션 보유 (기본 max_positions = 3)
        mock_exchange = AsyncMock()
        mock_exchange.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("500000"))
        ))
        mock_exchange.get_all_positions = AsyncMock(return_value=[
            create_position_info("KRW-BTC", Decimal("0.01"), Decimal("50000000")),
            create_position_info("KRW-ETH", Decimal("0.1"), Decimal("3000000")),
            create_position_info("KRW-XRP", Decimal("1000"), Decimal("500")),
        ])

        container = Container(exchange_port=mock_exchange)
        use_case = container.get_calculate_entry_amount_use_case()

        # When: 진입 금액 계산
        result = await use_case.execute("KRW-DOGE")

        # Then: 0 반환 (최대 포지션 도달)
        assert result.is_zero()

    @pytest.mark.asyncio
    async def test_already_has_ticker_position(self, create_position_info):
        """이미 해당 코인 보유 시 0 반환"""
        # Given: BTC 포지션 보유
        mock_exchange = AsyncMock()
        mock_exchange.get_balance = AsyncMock(return_value=MagicMock(
            available=Money.krw(Decimal("1000000"))
        ))
        mock_exchange.get_all_positions = AsyncMock(return_value=[
            create_position_info("KRW-BTC", Decimal("0.01"), Decimal("50000000")),
        ])

        container = Container(exchange_port=mock_exchange)
        use_case = container.get_calculate_entry_amount_use_case()

        # When: 동일 코인 진입 시도
        result = await use_case.execute("KRW-BTC")

        # Then: 0 반환 (이미 보유)
        assert result.is_zero()
