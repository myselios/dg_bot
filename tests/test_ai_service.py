"""
AI 서비스 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from src.ai.service import AIService


class TestAIService:
    """AIService 클래스 테스트"""
    
    @pytest.fixture
    def ai_service(self):
        """AIService 인스턴스"""
        return AIService()
    
    @pytest.mark.unit
    @patch('src.ai.service.OpenAI')
    def test_analyze_korean_response(self, mock_openai_class):
        """AI 응답이 한글로 번역되는지 테스트"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"decision": "buy", "reason": "기술적 지표가 상승 추세를 보이고 있습니다", "confidence": "high"}'
        mock_client.chat.completions.create.return_value = mock_response
        
        service = AIService()
        
        analysis_data = {
            'daily_chart': {},
            'hourly_chart': {},
            'orderbook_summary': {},
            'current_status': {
                'krw_balance': 1000000,
                'coin_balance': 1.0,
                'current_price': 2000000
            }
        }
        
        result = service.analyze("KRW-ETH", analysis_data)
        
        assert result is not None
        assert result['decision'] == 'buy'
        assert 'reason' in result
        # 프롬프트에 한글로 응답하라는 지시가 포함되어야 함
        call_args = mock_client.chat.completions.create.call_args
        system_prompt = call_args[1]['messages'][0]['content']
        user_prompt = call_args[1]['messages'][1]['content']
        
        assert '한국어' in system_prompt or 'Korean' in system_prompt
        assert '한국어' in user_prompt or '한국어로' in user_prompt
    
    @pytest.mark.unit
    def test_prepare_analysis_data_includes_all_data(self, ai_service):
        """분석 데이터 준비 테스트"""
        chart_data = {
            'day': MagicMock(),
            'minute60': MagicMock()
        }
        orderbook_summary = {'ask_prices': [100, 101]}
        current_status = {'krw_balance': 1000000}
        technical_indicators = {'rsi': 50}
        position_info = {'avg_buy_price': 2000000}
        fear_greed_index = {'value': 45, 'classification': 'Fear'}
        
        with patch('src.ai.service.df_to_json_dict') as mock_df_to_json:
            mock_df_to_json.return_value = {}
            
            result = ai_service.prepare_analysis_data(
                chart_data,
                orderbook_summary,
                current_status,
                technical_indicators,
                position_info,
                fear_greed_index
            )
            
            assert 'daily_chart_summary' in result
            assert 'hourly_chart_summary' in result
            assert 'orderbook_summary' in result
            assert 'current_status' in result
            assert 'technical_indicators' in result
            assert 'position_info' in result
            assert 'fear_greed_index' in result


