"""
의사결정 구조 테스트
TDD 원칙: 백테스팅 우선 의사결정 구조를 테스트합니다.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestDecisionStructure:
    """의사결정 구조 테스트 (백테스팅 우선)"""
    
    @pytest.fixture
    def passed_backtest_result(self):
        """백테스팅 통과 결과"""
        return {
            'passed': True,
            'metrics': {
                'total_return': 21.28,
                'win_rate': 47.83,
                'sharpe_ratio': 0.88,
                'profit_factor': 1.90,
                'max_drawdown': 7.50
            }
        }
    
    @pytest.fixture
    def failed_backtest_result(self):
        """백테스팅 실패 결과"""
        return {
            'passed': False,
            'metrics': {
                'total_return': -5.0,
                'win_rate': 30.0,
                'sharpe_ratio': -0.2,
                'profit_factor': 0.8,
                'max_drawdown': 25.0
            }
        }
    
    @pytest.fixture
    def sample_chart_data(self):
        """샘플 차트 데이터"""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        prices = 100 + np.random.randn(50).cumsum()
        
        return {
            'day': pd.DataFrame({
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'close': prices,
                'volume': np.random.randint(1000, 2000, 50)
            }, index=dates)
        }
    
    @pytest.fixture
    def safe_market_conditions(self):
        """안전한 시장 조건"""
        return {
            'market_correlation': {
                'market_risk': 'low',
                'beta': 0.9,
                'alpha': 0.01,
                'btc_return_1d': 0.005
            },
            'flash_crash': {
                'detected': False,
                'description': '플래시 크래시 없음'
            },
            'rsi_divergence': {
                'type': 'none',
                'description': '다이버전스 없음'
            }
        }
    
    @pytest.fixture
    def unsafe_market_conditions(self):
        """위험한 시장 조건"""
        return {
            'market_correlation': {
                'market_risk': 'high',
                'beta': 1.5,
                'alpha': -0.02,
                'btc_return_1d': -0.03,
                'risk_reason': 'BTC 하락 중, ETH 베타 높음'
            },
            'flash_crash': {
                'detected': False,
                'description': '플래시 크래시 없음'
            },
            'rsi_divergence': {
                'type': 'bearish_divergence',
                'confidence': 'high',
                'description': '하락 다이버전스 감지'
            }
        }
    
    # ==================== 기본 기능 테스트 ====================
    
    @pytest.mark.unit
    def test_execute_trading_decision_imports(self):
        """execute_trading_decision 함수를 import할 수 있는지 테스트"""
        # Given: 모듈 import
        # When & Then: ImportError가 발생하지 않아야 함
        try:
            from main import execute_trading_decision
            assert callable(execute_trading_decision)
        except ImportError as e:
            pytest.fail(f"execute_trading_decision import 실패: {e}")
    
    # ==================== 백테스팅 필터 테스트 ====================
    
    @pytest.mark.unit
    def test_backtest_failed_returns_hold(self, failed_backtest_result, sample_chart_data):
        """백테스팅 실패 시 HOLD 반환"""
        # Given: 백테스팅 실패 결과
        from main import execute_trading_decision
        
        # When: 의사결정 실행
        result = execute_trading_decision(
            backtest_result=failed_backtest_result,
            chart_data=sample_chart_data,
            market_conditions={},
            portfolio=None,
            ticker='KRW-ETH'
        )
        
        # Then: HOLD 결정
        assert result['decision'] == 'hold'
        assert '백테스팅 실패' in result['reason'] or '전략 비활성화' in result['reason']
    
    @pytest.mark.unit
    def test_backtest_passed_proceeds_to_strategy(
        self,
        passed_backtest_result,
        sample_chart_data
    ):
        """백테스팅 통과 시 전략 신호 확인으로 진행"""
        # Given: 백테스팅 통과 결과
        from main import execute_trading_decision
        
        # When: 의사결정 실행
        result = execute_trading_decision(
            backtest_result=passed_backtest_result,
            chart_data=sample_chart_data,
            market_conditions={'market_correlation': {}, 'flash_crash': {}, 'rsi_divergence': {}},
            portfolio=None,
            ticker='KRW-ETH'
        )
        
        # Then: 결정이 내려져야 함 (buy/sell/hold 중 하나)
        assert 'decision' in result
        assert result['decision'] in ['buy', 'sell', 'hold']
        assert 'reason' in result
    
    # ==================== 전략 신호 직접 호출 테스트 ====================
    
    @pytest.mark.unit
    @patch('main.RuleBasedBreakoutStrategy')
    def test_strategy_signal_directly_called(
        self,
        mock_strategy_class,
        passed_backtest_result,
        sample_chart_data,
        safe_market_conditions
    ):
        """RuleBasedBreakoutStrategy.generate_signal()이 직접 호출되는지 테스트"""
        # Given: Mock 전략
        from main import execute_trading_decision
        
        mock_signal = Mock()
        mock_signal.action = 'buy'
        mock_signal.reason = 'Volatility breakout'
        mock_signal.stop_loss = 3000000
        mock_signal.take_profit = 3500000
        mock_signal.position_size = 0.5
        
        mock_strategy = Mock()
        mock_strategy.generate_signal.return_value = mock_signal
        mock_strategy_class.return_value = mock_strategy
        
        # When: 의사결정 실행
        result = execute_trading_decision(
            backtest_result=passed_backtest_result,
            chart_data=sample_chart_data,
            market_conditions=safe_market_conditions,
            portfolio=None,
            ticker='KRW-ETH'
        )
        
        # Then: 전략의 generate_signal이 호출되었어야 함
        mock_strategy.generate_signal.assert_called_once()
    
    @pytest.mark.unit
    @patch('main.RuleBasedBreakoutStrategy')
    def test_strategy_buy_signal_with_safe_environment_returns_buy(
        self,
        mock_strategy_class,
        passed_backtest_result,
        sample_chart_data,
        safe_market_conditions
    ):
        """전략 매수 신호 + 안전한 환경 = BUY"""
        # Given: 매수 신호 + 안전한 환경
        from main import execute_trading_decision
        
        mock_signal = Mock()
        mock_signal.action = 'buy'
        mock_signal.reason = 'Volatility breakout'
        mock_signal.stop_loss = 3000000
        mock_signal.take_profit = 3500000
        mock_signal.position_size = 0.5
        
        mock_strategy = Mock()
        mock_strategy.generate_signal.return_value = mock_signal
        mock_strategy_class.return_value = mock_strategy
        
        # When: 의사결정 실행
        result = execute_trading_decision(
            backtest_result=passed_backtest_result,
            chart_data=sample_chart_data,
            market_conditions=safe_market_conditions,
            portfolio=None,
            ticker='KRW-ETH'
        )
        
        # Then: BUY 결정
        assert result['decision'] == 'buy'
        assert 'stop_loss' in result
        assert 'take_profit' in result
        assert 'position_size' in result
    
    @pytest.mark.unit
    @patch('main.RuleBasedBreakoutStrategy')
    def test_strategy_buy_signal_with_unsafe_environment_returns_hold(
        self,
        mock_strategy_class,
        passed_backtest_result,
        sample_chart_data,
        unsafe_market_conditions
    ):
        """전략 매수 신호 + 위험한 환경 = HOLD"""
        # Given: 매수 신호 + 위험한 환경
        from main import execute_trading_decision
        
        mock_signal = Mock()
        mock_signal.action = 'buy'
        mock_signal.reason = 'Volatility breakout'
        
        mock_strategy = Mock()
        mock_strategy.generate_signal.return_value = mock_signal
        mock_strategy_class.return_value = mock_strategy
        
        # When: 의사결정 실행
        result = execute_trading_decision(
            backtest_result=passed_backtest_result,
            chart_data=sample_chart_data,
            market_conditions=unsafe_market_conditions,
            portfolio=None,
            ticker='KRW-ETH'
        )
        
        # Then: HOLD 결정 (위험 요소 감지)
        assert result['decision'] == 'hold'
        assert '위험' in result['reason'] or 'risk' in result['reason'].lower()
    
    @pytest.mark.unit
    @patch('main.RuleBasedBreakoutStrategy')
    def test_strategy_sell_signal_returns_sell(
        self,
        mock_strategy_class,
        passed_backtest_result,
        sample_chart_data,
        safe_market_conditions
    ):
        """전략 매도 신호 = SELL (환경 체크 없이 바로 실행)"""
        # Given: 매도 신호
        from main import execute_trading_decision
        
        mock_signal = Mock()
        mock_signal.action = 'sell'
        mock_signal.reason = 'Take profit'
        
        mock_strategy = Mock()
        mock_strategy.generate_signal.return_value = mock_signal
        mock_strategy_class.return_value = mock_strategy
        
        # When: 의사결정 실행
        result = execute_trading_decision(
            backtest_result=passed_backtest_result,
            chart_data=sample_chart_data,
            market_conditions=safe_market_conditions,
            portfolio=Mock(),  # 포지션 있음
            ticker='KRW-ETH'
        )
        
        # Then: SELL 결정
        assert result['decision'] == 'sell'
    
    @pytest.mark.unit
    @patch('main.RuleBasedBreakoutStrategy')
    def test_strategy_no_signal_returns_hold(
        self,
        mock_strategy_class,
        passed_backtest_result,
        sample_chart_data,
        safe_market_conditions
    ):
        """전략 신호 없음 = HOLD"""
        # Given: 신호 없음 (None 또는 hold)
        from main import execute_trading_decision
        
        mock_strategy = Mock()
        mock_strategy.generate_signal.return_value = None
        mock_strategy_class.return_value = mock_strategy
        
        # When: 의사결정 실행
        result = execute_trading_decision(
            backtest_result=passed_backtest_result,
            chart_data=sample_chart_data,
            market_conditions=safe_market_conditions,
            portfolio=None,
            ticker='KRW-ETH'
        )
        
        # Then: HOLD 결정
        assert result['decision'] == 'hold'
        assert '진입 조건 미충족' in result['reason'] or 'No signal' in result['reason']
    
    # ==================== 환경 체크 로직 테스트 ====================
    
    @pytest.mark.unit
    def test_check_environment_safety_with_all_safe(self, safe_market_conditions):
        """모든 조건이 안전한 경우"""
        # Given: 안전한 시장 조건
        from main import check_environment_safety
        
        # When: 환경 안전성 체크
        result = check_environment_safety(safe_market_conditions)
        
        # Then: 안전으로 판단
        assert result['safe'] is True
        assert 'warning' not in result or result['warning'] == ''
    
    @pytest.mark.unit
    def test_check_environment_safety_with_high_market_risk(self):
        """시장 리스크 높음"""
        # Given: 높은 시장 리스크
        from main import check_environment_safety
        
        conditions = {
            'market_correlation': {
                'market_risk': 'high',
                'risk_reason': 'BTC 급락 중'
            },
            'flash_crash': {'detected': False},
            'rsi_divergence': {'type': 'none'}
        }
        
        # When: 환경 안전성 체크
        result = check_environment_safety(conditions)
        
        # Then: 위험으로 판단
        assert result['safe'] is False
        assert 'warning' in result
        assert 'BTC' in result['warning'] or 'market risk' in result['warning'].lower()
    
    @pytest.mark.unit
    def test_check_environment_safety_with_flash_crash(self):
        """플래시 크래시 감지"""
        # Given: 플래시 크래시 감지
        from main import check_environment_safety
        
        conditions = {
            'market_correlation': {'market_risk': 'low'},
            'flash_crash': {
                'detected': True,
                'description': '플래시 크래시 감지: 5% 급락'
            },
            'rsi_divergence': {'type': 'none'}
        }
        
        # When: 환경 안전성 체크
        result = check_environment_safety(conditions)
        
        # Then: 위험으로 판단
        assert result['safe'] is False
        assert '플래시 크래시' in result['warning'] or 'flash crash' in result['warning'].lower()
    
    @pytest.mark.unit
    def test_check_environment_safety_with_rsi_divergence(self):
        """RSI 하락 다이버전스 감지"""
        # Given: RSI 하락 다이버전스
        from main import check_environment_safety
        
        conditions = {
            'market_correlation': {'market_risk': 'low'},
            'flash_crash': {'detected': False},
            'rsi_divergence': {
                'type': 'bearish_divergence',
                'confidence': 'high',
                'description': '하락 다이버전스'
            }
        }
        
        # When: 환경 안전성 체크
        result = check_environment_safety(conditions)
        
        # Then: 위험으로 판단
        assert result['safe'] is False
        assert '다이버전스' in result['warning'] or 'divergence' in result['warning'].lower()
    
    # ==================== SignalAnalyzer 사용 안 함 테스트 ====================
    
    @pytest.mark.unit
    def test_signal_analyzer_not_used(
        self,
        passed_backtest_result,
        sample_chart_data,
        safe_market_conditions
    ):
        """SignalAnalyzer가 사용되지 않는지 확인"""
        # Given: 백테스팅 통과
        from main import execute_trading_decision
        
        # When: 의사결정 실행
        with patch('main.SignalAnalyzer') as mock_signal_analyzer:
            result = execute_trading_decision(
                backtest_result=passed_backtest_result,
                chart_data=sample_chart_data,
                market_conditions=safe_market_conditions,
                portfolio=None,
                ticker='KRW-ETH'
            )
            
            # Then: SignalAnalyzer가 호출되지 않아야 함
            mock_signal_analyzer.assert_not_called()



