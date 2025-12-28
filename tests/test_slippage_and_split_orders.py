"""
슬리피지 및 분할매수 테스트
TDD 원칙: 테스트 케이스를 먼저 작성하고 구현을 검증합니다.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
from src.backtesting.strategy import Signal
from src.backtesting.portfolio import Portfolio


class TestSlippageCalculation:
    """슬리피지 계산 테스트"""
    
    @pytest.mark.unit
    def test_calculate_slippage_for_buy_order(self):
        """매수 주문 슬리피지 계산 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        expected_price = 100_000  # 예상 가격
        order_size = 1.0  # 1 ETH
        orderbook_summary = {
            'ask_prices': [100_000, 100_100, 100_200, 100_300],
            'ask_volumes': [0.5, 0.3, 0.5, 1.0]  # 호가별 물량
        }
        
        # When
        slippage_info = strategy.calculate_slippage(
            order_type='buy',
            expected_price=expected_price,
            order_size=order_size,
            orderbook=orderbook_summary
        )
        
        # Then
        assert slippage_info is not None
        assert 'actual_avg_price' in slippage_info
        assert 'slippage_pct' in slippage_info
        assert 'slippage_amount' in slippage_info
        # 매수는 더 높은 가격에 체결되므로 슬리피지는 양수
        assert slippage_info['slippage_pct'] >= 0
        # 평균 체결가는 예상가보다 높아야 함
        assert slippage_info['actual_avg_price'] >= expected_price
    
    @pytest.mark.unit
    def test_calculate_slippage_for_sell_order(self):
        """매도 주문 슬리피지 계산 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        expected_price = 100_000  # 예상 가격
        order_size = 1.0  # 1 ETH
        orderbook_summary = {
            'bid_prices': [100_000, 99_900, 99_800, 99_700],
            'bid_volumes': [0.5, 0.3, 0.5, 1.0]  # 호가별 물량
        }
        
        # When
        slippage_info = strategy.calculate_slippage(
            order_type='sell',
            expected_price=expected_price,
            order_size=order_size,
            orderbook=orderbook_summary
        )
        
        # Then
        assert slippage_info is not None
        assert 'actual_avg_price' in slippage_info
        assert 'slippage_pct' in slippage_info
        assert 'slippage_amount' in slippage_info
        # 매도는 더 낮은 가격에 체결되므로 슬리피지는 양수
        assert slippage_info['slippage_pct'] >= 0
        # 평균 체결가는 예상가보다 낮아야 함
        assert slippage_info['actual_avg_price'] <= expected_price
    
    @pytest.mark.unit
    def test_slippage_exceeds_tolerance(self):
        """슬리피지가 허용치를 초과하는 경우 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        expected_price = 100_000
        order_size = 10.0  # 큰 주문 (오더북 유동성 부족 가정)
        orderbook_summary = {
            'ask_prices': [100_000, 101_000, 102_000, 103_000],
            'ask_volumes': [0.5, 1.0, 1.5, 2.0]  # 작은 물량
        }
        slippage_tolerance = 0.01  # 1% 허용치
        
        # When
        slippage_info = strategy.calculate_slippage(
            order_type='buy',
            expected_price=expected_price,
            order_size=order_size,
            orderbook=orderbook_summary
        )
        
        # Then
        assert slippage_info is not None
        # 슬리피지가 허용치를 초과하는지 체크
        if slippage_info['slippage_pct'] > slippage_tolerance:
            assert slippage_info.get('warning') is not None
            assert '허용치 초과' in slippage_info.get('warning', '')


class TestSplitOrderCalculation:
    """분할매수 계산 테스트"""
    
    @pytest.mark.unit
    def test_split_order_into_multiple_chunks(self):
        """주문을 여러 개로 분할하는 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        total_order_size = 10.0  # 10 ETH
        num_splits = 5  # 5개로 분할
        
        # When
        split_orders = strategy.split_order(
            total_size=total_order_size,
            num_splits=num_splits
        )
        
        # Then
        assert len(split_orders) == num_splits
        # 각 분할 주문의 크기가 균등해야 함
        expected_chunk_size = total_order_size / num_splits
        for order in split_orders:
            assert abs(order['size'] - expected_chunk_size) < 0.001
        # 전체 합이 원래 주문량과 같아야 함
        total_split_size = sum(order['size'] for order in split_orders)
        assert abs(total_split_size - total_order_size) < 0.001
    
    @pytest.mark.unit
    def test_split_order_with_min_chunk_size(self):
        """최소 분할 크기를 고려한 주문 분할 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        total_order_size = 1.0  # 1 ETH
        num_splits = 10  # 10개로 분할 시도
        min_chunk_size = 0.2  # 최소 0.2 ETH
        
        # When
        split_orders = strategy.split_order(
            total_size=total_order_size,
            num_splits=num_splits,
            min_chunk_size=min_chunk_size
        )
        
        # Then
        # 최소 크기보다 작은 분할은 생성되지 않아야 함
        # 1 ETH를 0.2 ETH씩 분할하면 최대 5개
        assert len(split_orders) <= total_order_size / min_chunk_size
        for order in split_orders:
            assert order['size'] >= min_chunk_size or order['size'] == total_order_size
        # 전체 합이 원래 주문량과 같아야 함
        total_split_size = sum(order['size'] for order in split_orders)
        assert abs(total_split_size - total_order_size) < 0.001
    
    @pytest.mark.unit
    def test_calculate_optimal_splits_based_on_orderbook(self):
        """오더북 유동성 기반 최적 분할 개수 계산 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        order_size = 5.0  # 5 ETH
        orderbook_summary = {
            'ask_prices': [100_000, 100_100, 100_200, 100_300, 100_400],
            'ask_volumes': [1.0, 1.5, 1.2, 0.8, 2.0]  # 호가별 물량
        }
        
        # When
        optimal_splits = strategy.calculate_optimal_splits(
            order_size=order_size,
            orderbook=orderbook_summary,
            order_type='buy'
        )
        
        # Then
        assert optimal_splits >= 1
        # 주문량이 개별 호가 물량보다 크므로 여러 개로 분할되어야 함
        max_single_ask_volume = max(orderbook_summary['ask_volumes'])
        if order_size > max_single_ask_volume:
            assert optimal_splits > 1
    
    @pytest.mark.unit
    def test_split_order_execution_simulation(self):
        """분할 주문 실행 시뮬레이션 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        total_order_size = 3.0  # 3 ETH
        num_splits = 3
        orderbook_summary = {
            'ask_prices': [100_000, 100_100, 100_200],
            'ask_volumes': [1.0, 1.0, 1.0]
        }
        
        # When
        execution_result = strategy.simulate_split_order_execution(
            total_size=total_order_size,
            num_splits=num_splits,
            orderbook=orderbook_summary,
            order_type='buy'
        )
        
        # Then
        assert execution_result is not None
        assert 'filled_orders' in execution_result
        assert 'avg_execution_price' in execution_result
        assert 'total_slippage' in execution_result
        assert len(execution_result['filled_orders']) == num_splits
        # 각 분할 주문이 체결되었는지 확인
        total_filled = sum(order['filled_size'] for order in execution_result['filled_orders'])
        assert abs(total_filled - total_order_size) < 0.001


class TestIntegratedSlippageAndSplitOrders:
    """슬리피지와 분할매수 통합 테스트"""
    
    @pytest.mark.unit
    def test_split_order_reduces_slippage(self):
        """분할 주문이 슬리피지를 감소시키는지 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        order_size = 5.0
        expected_price = 100_000
        orderbook_summary = {
            'ask_prices': [100_000, 100_200, 100_500, 101_000],
            'ask_volumes': [1.0, 1.5, 1.5, 2.0]
        }
        
        # When: 전체 주문 실행 (분할 없음)
        single_order_slippage = strategy.calculate_slippage(
            order_type='buy',
            expected_price=expected_price,
            order_size=order_size,
            orderbook=orderbook_summary
        )
        
        # When: 분할 주문 실행 (5개로 분할)
        split_execution = strategy.simulate_split_order_execution(
            total_size=order_size,
            num_splits=5,
            orderbook=orderbook_summary,
            order_type='buy'
        )
        
        # Then
        # 분할 주문의 슬리피지가 단일 주문보다 작아야 함
        single_slippage_pct = single_order_slippage['slippage_pct']
        split_slippage_pct = split_execution['total_slippage']
        assert split_slippage_pct <= single_slippage_pct
    
    @pytest.mark.unit
    def test_generate_signal_with_split_order_recommendation(self):
        """매수 신호 생성 시 분할 주문 권장 사항 포함 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        # 모든 관문 통과 데이터
        data = []
        for i in range(30):
            if i < 20:
                price = 100 + np.sin(i * 0.05) * 0.5
            else:
                price = 100 + 5 + (i - 20) * 1.5
            data.append({
                'open': price,
                'high': price + 1.5,
                'low': price - 1.5,
                'close': price + 0.5,
                'volume': 2500 if i >= 25 else 1000
            })
        df = pd.DataFrame(data, index=dates)
        portfolio = Portfolio(initial_capital=10_000_000)
        
        # When
        signal = strategy.generate_signal(df, portfolio=portfolio)
        
        # Then
        if signal and signal.action == 'buy':
            # 포지션 사이즈 정보에 분할 주문 권장사항이 있어야 함
            assert hasattr(signal, 'split_recommendation')
            if signal.split_recommendation:
                assert 'num_splits' in signal.split_recommendation
                assert 'reason' in signal.split_recommendation
                assert signal.split_recommendation['num_splits'] >= 1
    
    @pytest.mark.unit
    def test_position_size_with_slippage_adjustment(self):
        """슬리피지를 고려한 포지션 크기 조정 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH', risk_per_trade=0.02)
        portfolio = Portfolio(initial_capital=10_000_000)
        signal = Signal(
            action='buy',
            price=100_000,
            stop_loss=98_000
        )
        expected_slippage_pct = 0.005  # 0.5% 예상 슬리피지
        
        # When
        position_size_without_slippage = strategy.calculate_position_size(signal, portfolio)
        position_size_with_slippage = strategy.calculate_position_size_with_slippage(
            signal, 
            portfolio,
            expected_slippage_pct=expected_slippage_pct
        )
        
        # Then
        # 슬리피지를 고려하면 포지션 크기가 조정되어야 함
        assert position_size_with_slippage is not None
        # 슬리피지 고려 시 실제 진입가가 높아지므로 포지션 크기 조정
        # (동일 리스크 금액 유지를 위해)
        assert position_size_with_slippage <= position_size_without_slippage


class TestSlippageInBacktesting:
    """백테스팅에서 슬리피지 적용 테스트"""
    
    @pytest.mark.unit
    def test_backtest_includes_slippage_cost(self):
        """백테스팅 결과에 슬리피지 비용 포함 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-ETH')
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        data = pd.DataFrame({
            'open': [100 + i * 0.5 for i in range(30)],
            'high': [105 + i * 0.5 for i in range(30)],
            'low': [95 + i * 0.5 for i in range(30)],
            'close': [100 + i * 0.5 for i in range(30)],
            'volume': [1000] * 30
        }, index=dates)
        portfolio = Portfolio(initial_capital=10_000_000)
        
        # 슬리피지 설정
        slippage_model = {
            'type': 'percentage',
            'buy_slippage': 0.001,  # 0.1% 매수 슬리피지
            'sell_slippage': 0.001  # 0.1% 매도 슬리피지
        }
        
        # When
        # 백테스팅 실행 (슬리피지 포함)
        # 실제 백테스터에 슬리피지 모델을 적용하는 로직은 별도 구현 필요
        signal = strategy.generate_signal(data, portfolio=portfolio)
        
        # Then
        if signal and signal.action == 'buy':
            # 신호에 슬리피지 정보가 포함되어야 함
            assert hasattr(signal, 'expected_slippage') or 'slippage' in signal.reason



