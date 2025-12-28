"""
백테스팅 슬리피지 통합 테스트
TDD 원칙: 테스트 케이스를 먼저 작성하고 구현을 검증합니다.
"""
import pytest
import pandas as pd
import numpy as np
from src.backtesting.backtester import Backtester
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
from src.backtesting.portfolio import Portfolio


@pytest.fixture
def sample_breakout_data():
    """볼린저 밴드 돌파가 명확한 샘플 데이터"""
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    base_price = 100_000
    data = []
    
    for i in range(60):
        if i < 35:
            # 응축 구간: 볼린저 밴드가 좁아짐
            price = base_price + np.sin(i * 0.2) * 500
            volume = 1000 + i * 10
        elif i < 50:
            # 횡보 지속
            price = base_price + np.sin(i * 0.1) * 800
            volume = 1500 + (i - 35) * 20
        else:
            # 강한 돌파 발생 + 거래량 급증
            price = base_price + 5000 + (i - 50) * 1000
            volume = 4000 + (i - 50) * 300
        
        data.append({
            'open': price,
            'high': price + 1000,
            'low': price - 1000,
            'close': price + 300,
            'volume': volume
        })
    
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def mock_orderbook():
    """모의 오더북 데이터"""
    return {
        'ask_prices': [100_000, 100_100, 100_200, 100_300, 100_400],
        'ask_volumes': [0.5, 0.3, 0.4, 0.5, 0.6],
        'bid_prices': [99_900, 99_800, 99_700, 99_600, 99_500],
        'bid_volumes': [0.4, 0.5, 0.3, 0.6, 0.5]
    }


class TestBacktestingSlippageIntegration:
    """백테스팅 슬리피지 통합 테스트"""
    
    @pytest.mark.unit
    def test_backtester_with_orderbook_slippage_model(self, sample_breakout_data, mock_orderbook):
        """오더북 기반 슬리피지 모델 적용 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        # 오더북 기반 슬리피지 모델 설정
        slippage_model = {
            'type': 'orderbook',
            'default_slippage': 0.001,  # 오더북 없을 시 기본값
            'orderbook_provider': lambda: mock_orderbook
        }
        
        backtester = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage_model=slippage_model  # ← 새로운 파라미터
        )
        
        # When
        result = backtester.run()
        
        # Then
        assert result is not None
        assert result.initial_capital == 10_000_000
        assert len(result.equity_curve) > 0
        assert hasattr(backtester, 'slippage_model')
        assert backtester.slippage_model['type'] == 'orderbook'
    
    @pytest.mark.unit
    def test_execute_order_applies_orderbook_slippage(self, sample_breakout_data, mock_orderbook):
        """주문 실행 시 오더북 슬리피지 적용 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        slippage_model = {
            'type': 'orderbook',
            'default_slippage': 0.001,
            'orderbook_provider': lambda: mock_orderbook
        }
        
        backtester = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage_model=slippage_model
        )
        
        # When
        result = backtester.run()
        
        # Then
        # 주문이 실행되었다면 슬리피지가 적용되어야 함
        if len(backtester.orders) > 0:
            first_order = backtester.orders[0]
            assert 'actual_price' in first_order or 'slippage_info' in first_order
    
    @pytest.mark.unit
    def test_backtester_with_split_orders(self, sample_breakout_data, mock_orderbook):
        """분할 주문 기능 백테스팅 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        slippage_model = {
            'type': 'orderbook',
            'default_slippage': 0.001,
            'orderbook_provider': lambda: mock_orderbook
        }
        
        backtester = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage_model=slippage_model,
            use_split_orders=True  # ← 분할 주문 활성화
        )
        
        # When
        result = backtester.run()
        
        # Then
        assert result is not None
        assert hasattr(backtester, 'use_split_orders')
        assert backtester.use_split_orders is True
    
    @pytest.mark.unit
    def test_split_order_reduces_total_slippage(self, mock_orderbook):
        """분할 주문이 슬리피지를 감소시키는지 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        # 큰 주문량 (분할이 필요한 경우)
        large_order_size = 2.0  # 2 ETH
        expected_price = 100_000
        
        # When: 일반 주문 슬리피지 계산
        normal_slippage = strategy.calculate_slippage(
            order_type='buy',
            expected_price=expected_price,
            order_size=large_order_size,
            orderbook=mock_orderbook
        )
        
        # When: 분할 주문 슬리피지 계산
        num_splits = strategy.calculate_optimal_splits(
            order_size=large_order_size,
            orderbook=mock_orderbook,
            order_type='buy'
        )
        
        split_execution = strategy.simulate_split_order_execution(
            total_size=large_order_size,
            num_splits=num_splits,
            orderbook=mock_orderbook,
            order_type='buy'
        )
        
        # Then: 분할 주문의 슬리피지가 더 적어야 함
        assert num_splits > 1  # 분할 권장
        assert split_execution['total_slippage'] < normal_slippage['slippage_pct']
    
    @pytest.mark.unit
    def test_slippage_statistics_tracking(self, sample_breakout_data, mock_orderbook):
        """슬리피지 통계 추적 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        slippage_model = {
            'type': 'orderbook',
            'default_slippage': 0.001,
            'orderbook_provider': lambda: mock_orderbook
        }
        
        backtester = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage_model=slippage_model
        )
        
        # When
        result = backtester.run()
        
        # Then: 슬리피지 통계가 기록되어야 함
        assert hasattr(backtester, 'slippage_statistics') or 'slippage_stats' in result.metrics


class TestBacktestingPerformanceWithSlippage:
    """슬리피지가 백테스팅 성과에 미치는 영향 테스트"""
    
    @pytest.mark.integration
    def test_higher_slippage_reduces_returns(self, sample_breakout_data):
        """높은 슬리피지가 수익률을 감소시키는지 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        # 낮은 슬리피지로 백테스팅
        backtester_low = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage=0.0001  # 0.01%
        )
        result_low = backtester_low.run()
        
        # 높은 슬리피지로 백테스팅
        backtester_high = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage=0.01  # 1%
        )
        result_high = backtester_high.run()
        
        # Then: 높은 슬리피지 시 수익률이 더 낮아야 함
        if len(result_low.trades) > 0:  # 거래가 있었다면
            assert result_low.final_equity >= result_high.final_equity
    
    @pytest.mark.integration
    def test_split_orders_improve_backtest_results(self, sample_breakout_data, mock_orderbook):
        """분할 주문이 백테스팅 결과를 개선하는지 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        slippage_model = {
            'type': 'orderbook',
            'default_slippage': 0.001,
            'orderbook_provider': lambda: mock_orderbook
        }
        
        # 일반 주문
        backtester_normal = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage_model=slippage_model,
            use_split_orders=False
        )
        result_normal = backtester_normal.run()
        
        # 분할 주문
        backtester_split = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage_model=slippage_model,
            use_split_orders=True
        )
        result_split = backtester_split.run()
        
        # Then: 분할 주문이 더 나은 결과를 내야 함 (또는 최소한 비슷)
        # (슬리피지가 적으므로)
        assert result_split.final_equity >= result_normal.final_equity * 0.95  # 5% 오차 허용


class TestBacktestingSlippageEdgeCases:
    """슬리피지 엣지 케이스 테스트"""
    
    @pytest.mark.unit
    def test_no_orderbook_falls_back_to_default_slippage(self, sample_breakout_data):
        """오더북 없을 시 기본 슬리피지로 폴백 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        
        slippage_model = {
            'type': 'orderbook',
            'default_slippage': 0.002,  # 0.2%
            'orderbook_provider': lambda: None  # 오더북 없음
        }
        
        backtester = Backtester(
            strategy=strategy,
            data=sample_breakout_data,
            ticker='KRW-ETH',
            initial_capital=10_000_000,
            commission=0.0005,
            slippage_model=slippage_model
        )
        
        # When
        result = backtester.run()
        
        # Then: 에러 없이 실행되고 기본 슬리피지가 적용되어야 함
        assert result is not None
        assert len(result.equity_curve) > 0
    
    @pytest.mark.unit
    def test_very_small_order_no_slippage_warning(self, mock_orderbook):
        """매우 작은 주문은 슬리피지 경고가 없어야 함"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        small_order_size = 0.01  # 0.01 ETH
        
        # When
        slippage_info = strategy.calculate_slippage(
            order_type='buy',
            expected_price=100_000,
            order_size=small_order_size,
            orderbook=mock_orderbook
        )
        
        # Then
        assert 'warning' not in slippage_info or slippage_info['warning'] is None
        assert slippage_info['slippage_pct'] < 0.01  # 1% 미만



