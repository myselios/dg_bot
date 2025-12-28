"""
AIService 백테스팅 결과 포함 테스트
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ai.service import AIService


class TestAIServiceBacktestIntegration:
    """AIService 백테스팅 결과 통합 테스트"""
    
    @pytest.mark.unit
    def test_prepare_analysis_data_with_backtest_result(self):
        """백테스팅 결과 포함 테스트"""
        # Given
        ai_service = AIService()
        chart_data = {'day': Mock(), 'minute60': Mock(), 'minute15': Mock()}
        orderbook_summary = {}
        current_status = {'current_price': 100000}
        technical_indicators = {}
        position_info = {}
        fear_greed_index = {}
        
        backtest_result = {
            'passed': True,
            'metrics': {
                'total_return': 10.0,
                'win_rate': 60.0,
                'sharpe_ratio': 1.5,
                'max_drawdown': -10.0
            },
            'filter_results': {'return': True},
            'reason': '통과'
        }
        
        # Mock 메서드들
        with patch.object(ai_service, '_create_chart_summary', return_value={}):
            with patch.object(ai_service, '_calculate_volatility_indicators', return_value=None):
                with patch.object(ai_service, '_calculate_volume_analysis', return_value=None):
                    with patch.object(ai_service, '_calculate_momentum_indicators', return_value=None):
                        with patch.object(ai_service, '_calculate_market_structure', return_value=None):
                            with patch.object(ai_service, '_calculate_multi_timeframe_analysis', return_value=None):
                                with patch.object(ai_service, '_calculate_risk_metrics', return_value=None):
                                    with patch.object(ai_service, '_analyze_advanced_orderbook', return_value=None):
                                        with patch.object(ai_service, '_detect_candlestick_patterns', return_value=None):
                                            # When
                                            analysis_data = ai_service.prepare_analysis_data(
                                                chart_data,
                                                orderbook_summary,
                                                current_status,
                                                technical_indicators,
                                                position_info,
                                                fear_greed_index,
                                                backtest_result=backtest_result
                                            )
                                            
                                            # Then
                                            assert 'backtest_result' in analysis_data
                                            assert analysis_data['backtest_result'] == backtest_result
    
    @pytest.mark.unit
    def test_prepare_analysis_data_without_backtest_result(self):
        """백테스팅 결과 없을 때 테스트"""
        # Given
        ai_service = AIService()
        chart_data = {'day': Mock(), 'minute60': Mock(), 'minute15': Mock()}
        orderbook_summary = {}
        current_status = {'current_price': 100000}
        
        # Mock 메서드들
        with patch.object(ai_service, '_create_chart_summary', return_value={}):
            with patch.object(ai_service, '_calculate_volatility_indicators', return_value=None):
                with patch.object(ai_service, '_calculate_volume_analysis', return_value=None):
                    with patch.object(ai_service, '_calculate_momentum_indicators', return_value=None):
                        with patch.object(ai_service, '_calculate_market_structure', return_value=None):
                            with patch.object(ai_service, '_calculate_multi_timeframe_analysis', return_value=None):
                                with patch.object(ai_service, '_calculate_risk_metrics', return_value=None):
                                    with patch.object(ai_service, '_analyze_advanced_orderbook', return_value=None):
                                        with patch.object(ai_service, '_detect_candlestick_patterns', return_value=None):
                                            # When (backtest_result=None)
                                            analysis_data = ai_service.prepare_analysis_data(
                                                chart_data,
                                                orderbook_summary,
                                                current_status,
                                                technical_indicators=None,
                                                position_info=None,
                                                fear_greed_index=None,
                                                backtest_result=None
                                            )
                                            
                                            # Then
                                            assert 'backtest_result' not in analysis_data




