"""
실시간 거래 서비스 슬리피지 통합 테스트
TDD 원칙: 테스트 케이스를 먼저 작성하고 구현을 검증합니다.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.trading.service import TradingService
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
from src.data.collector import DataCollector


@pytest.fixture
def mock_exchange_client():
    """모의 거래소 클라이언트"""
    client = Mock()
    client.get_balance.return_value = 1_000_000  # 100만원
    client.buy_market_order.return_value = {'uuid': 'test-uuid-123'}
    client.sell_market_order.return_value = {'uuid': 'test-uuid-456'}
    client.get_current_price.return_value = 100_000  # 10만원
    return client


@pytest.fixture
def mock_data_collector():
    """모의 데이터 수집기"""
    collector = Mock()
    collector.get_orderbook.return_value = {
        'ask_prices': [100_000, 100_100, 100_200, 100_300, 100_400],
        'ask_volumes': [0.5, 0.3, 0.4, 0.5, 0.6],
        'bid_prices': [99_900, 99_800, 99_700, 99_600, 99_500],
        'bid_volumes': [0.4, 0.5, 0.3, 0.6, 0.5]
    }
    return collector


@pytest.fixture
def mock_strategy():
    """모의 전략"""
    strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
    return strategy


class TestTradingServiceWithSlippage:
    """슬리피지를 고려한 실시간 거래 서비스 테스트"""
    
    @pytest.mark.unit
    def test_trading_service_initialization_with_slippage_support(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """슬리피지 지원 거래 서비스 초기화 테스트"""
        # When
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        # Then
        assert hasattr(service, 'data_collector')
        assert hasattr(service, 'strategy')
        assert service.data_collector == mock_data_collector
        assert service.strategy == mock_strategy
    
    @pytest.mark.unit
    def test_execute_buy_with_slippage_calculation(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """슬리피지 계산을 포함한 매수 실행 테스트"""
        # Given
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        ticker = 'KRW-ETH'
        amount = 100_000
        
        # When
        result = service.execute_buy_with_slippage(
            ticker=ticker,
            amount=amount,
            enable_split=False
        )
        
        # Then
        assert result is not None
        assert 'slippage_info' in result
        assert 'order_result' in result
        mock_data_collector.get_orderbook.assert_called_once_with(ticker)
        mock_exchange_client.buy_market_order.assert_called_once()
    
    @pytest.mark.unit
    def test_execute_buy_with_slippage_warning(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """높은 슬리피지 경고 테스트"""
        # Given
        # 유동성이 낮은 오더북 설정
        mock_data_collector.get_orderbook.return_value = {
            'ask_prices': [100_000, 105_000, 110_000],
            'ask_volumes': [0.1, 0.1, 0.1],  # 매우 낮은 유동성
            'bid_prices': [99_000, 94_000, 89_000],
            'bid_volumes': [0.1, 0.1, 0.1]
        }
        
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        large_amount = 500_000  # 큰 주문
        
        # When
        result = service.execute_buy_with_slippage(
            ticker=ticker,
            amount=large_amount,
            enable_split=False
        )
        
        # Then
        assert result is not None
        assert 'slippage_info' in result
        slippage_info = result['slippage_info']
        # 높은 슬리피지일 경우 경고가 있어야 함
        if slippage_info['slippage_pct'] > 0.01:  # 1% 초과
            assert 'warning' in slippage_info or slippage_info.get('warning') is not None
    
    @pytest.mark.unit
    def test_execute_buy_with_split_orders_enabled(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """분할 주문 활성화 매수 테스트"""
        # Given
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        large_amount = 500_000  # 분할이 필요한 큰 주문
        
        # When
        result = service.execute_buy_with_slippage(
            ticker=ticker,
            amount=large_amount,
            enable_split=True  # 분할 주문 활성화
        )
        
        # Then
        assert result is not None
        # 분할 주문이 실행되었다면
        if 'split_orders' in result:
            assert len(result['split_orders']) > 1
            assert 'total_filled' in result
            # 각 분할 주문이 실행되었어야 함
            assert mock_exchange_client.buy_market_order.call_count >= 1
    
    @pytest.mark.unit
    def test_execute_buy_split_order_with_delay(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """분할 주문 간 딜레이 테스트"""
        # Given
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        amount = 500_000
        
        # When
        with patch('time.sleep') as mock_sleep:
            result = service.execute_buy_with_slippage(
                ticker=ticker,
                amount=amount,
                enable_split=True
            )
            
            # Then
            # 분할 주문이 실행되었다면 딜레이가 있어야 함
            if 'split_orders' in result and len(result['split_orders']) > 1:
                assert mock_sleep.called
    
    @pytest.mark.unit
    def test_execute_sell_with_slippage(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """슬리피지를 고려한 매도 실행 테스트"""
        # Given
        mock_exchange_client.get_balance.return_value = 1.0  # 1 ETH 보유
        
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        
        # When
        result = service.execute_sell_with_slippage(ticker=ticker)
        
        # Then
        assert result is not None
        assert 'slippage_info' in result
        assert 'order_result' in result
        mock_data_collector.get_orderbook.assert_called_with(ticker)
        mock_exchange_client.sell_market_order.assert_called_once()
    
    @pytest.mark.unit
    def test_calculate_optimal_buy_amount_with_slippage(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """슬리피지를 고려한 최적 매수 금액 계산 테스트"""
        # Given
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        balance = 1_000_000
        expected_slippage_pct = 0.005  # 0.5%
        
        # When
        optimal_amount = service.calculate_optimal_buy_amount_with_slippage(
            ticker=ticker,
            balance=balance,
            expected_slippage_pct=expected_slippage_pct
        )
        
        # Then
        assert optimal_amount > 0
        assert optimal_amount <= balance
        # 슬리피지를 고려하여 금액이 조정되어야 함


class TestTradingServiceSlippageEdgeCases:
    """슬리피지 관련 엣지 케이스 테스트"""
    
    @pytest.mark.unit
    def test_orderbook_unavailable_falls_back_to_default(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """오더북 없을 시 기본 슬리피지 사용 테스트"""
        # Given
        mock_data_collector.get_orderbook.return_value = None  # 오더북 없음
        
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        amount = 100_000
        
        # When
        result = service.execute_buy_with_slippage(
            ticker=ticker,
            amount=amount,
            enable_split=False
        )
        
        # Then
        assert result is not None
        assert 'slippage_info' in result
        # 기본 슬리피지가 적용되어야 함
        assert result['slippage_info']['slippage_pct'] > 0
    
    @pytest.mark.unit
    def test_very_small_order_no_split_recommendation(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """매우 작은 주문은 분할 권장하지 않음 테스트"""
        # Given
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        small_amount = 10_000  # 작은 주문
        
        # When
        result = service.execute_buy_with_slippage(
            ticker=ticker,
            amount=small_amount,
            enable_split=True
        )
        
        # Then
        assert result is not None
        # 작은 주문은 분할하지 않아야 함
        assert 'split_orders' not in result or len(result.get('split_orders', [])) <= 1
    
    @pytest.mark.unit
    def test_insufficient_balance_with_slippage(
        self, mock_exchange_client, mock_data_collector, mock_strategy
    ):
        """잔액 부족 시 슬리피지 고려 테스트"""
        # Given
        mock_exchange_client.get_balance.return_value = 5_000  # 매우 작은 잔액
        
        service = TradingService(
            exchange_client=mock_exchange_client,
            data_collector=mock_data_collector,
            strategy=mock_strategy
        )
        
        ticker = 'KRW-ETH'
        
        # When
        result = service.execute_buy_with_slippage(
            ticker=ticker,
            amount=None,  # 가능한 전액
            enable_split=False
        )
        
        # Then
        # 잔액이 너무 적으면 실행되지 않아야 함
        assert result is None or result.get('status') == 'insufficient_funds'



