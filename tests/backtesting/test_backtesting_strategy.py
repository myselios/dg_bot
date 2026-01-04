"""
백테스팅 전략 테스트
"""
import pytest
import pandas as pd
from datetime import datetime
from src.backtesting.strategy import Strategy, Signal
from src.backtesting.portfolio import Portfolio


class MockStrategy(Strategy):
    """테스트용 Mock 전략"""
    
    def __init__(self, signals=None):
        self.signals = signals or []
        self.call_count = 0
    
    def generate_signal(self, data: pd.DataFrame):
        """신호 생성"""
        if self.call_count < len(self.signals):
            signal = self.signals[self.call_count]
            self.call_count += 1
            return signal
        return None
    
    def calculate_position_size(self, signal: Signal, portfolio: Portfolio) -> float:
        """포지션 크기 계산"""
        return 1.0  # 고정 크기


class TestSignal:
    """Signal 클래스 테스트"""
    
    @pytest.mark.unit
    def test_signal_creation_with_basic_fields(self):
        """기본 필드로 Signal 생성 테스트"""
        # Given
        action = 'buy'
        price = 100.0
        
        # When
        signal = Signal(action=action, price=price)
        
        # Then
        assert signal.action == action
        assert signal.price == price
        assert signal.size is None
        assert signal.stop_loss is None
        assert signal.take_profit is None
        assert signal.reason == {}
        assert signal.timestamp is not None
    
    @pytest.mark.unit
    def test_signal_creation_with_all_fields(self):
        """모든 필드로 Signal 생성 테스트"""
        # Given
        action = 'buy'
        price = 100.0
        size = 1.5
        stop_loss = 95.0
        take_profit = 110.0
        reason = {'confidence': 'high'}
        
        # When
        signal = Signal(
            action=action,
            price=price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason
        )
        
        # Then
        assert signal.action == action
        assert signal.price == price
        assert signal.size == size
        assert signal.stop_loss == stop_loss
        assert signal.take_profit == take_profit
        assert signal.reason == reason


class TestStrategy:
    """Strategy 인터페이스 테스트"""
    
    @pytest.mark.unit
    def test_strategy_generate_signal(self, sample_chart_data):
        """전략 신호 생성 테스트"""
        # Given
        buy_signal = Signal(action='buy', price=100.0)
        strategy = MockStrategy(signals=[buy_signal])
        
        # When
        result = strategy.generate_signal(sample_chart_data)
        
        # Then
        assert result is not None
        assert result.action == 'buy'
        assert result.price == 100.0
    
    @pytest.mark.unit
    def test_strategy_generate_signal_returns_none(self, sample_chart_data):
        """신호가 없을 때 None 반환 테스트"""
        # Given
        strategy = MockStrategy(signals=[])
        
        # When
        result = strategy.generate_signal(sample_chart_data)
        
        # Then
        assert result is None
    
    @pytest.mark.unit
    def test_strategy_calculate_position_size(self):
        """포지션 크기 계산 테스트"""
        # Given
        strategy = MockStrategy()
        signal = Signal(action='buy', price=100.0)
        portfolio = Portfolio(initial_capital=10000.0)
        
        # When
        size = strategy.calculate_position_size(signal, portfolio)
        
        # Then
        assert size == 1.0
    
    @pytest.mark.unit
    def test_strategy_multiple_signals(self, sample_chart_data):
        """여러 신호 생성 테스트"""
        # Given
        signals = [
            Signal(action='buy', price=100.0),
            Signal(action='sell', price=110.0),
            Signal(action='buy', price=105.0)
        ]
        strategy = MockStrategy(signals=signals)
        
        # When & Then
        for expected_signal in signals:
            result = strategy.generate_signal(sample_chart_data)
            assert result is not None
            assert result.action == expected_signal.action
            assert result.price == expected_signal.price
        
        # 더 이상 신호가 없어야 함
        assert strategy.generate_signal(sample_chart_data) is None




