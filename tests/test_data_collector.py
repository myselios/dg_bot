"""
데이터 수집 테스트
"""
import pytest
from unittest.mock import patch, MagicMock
from src.data.collector import DataCollector


class TestDataCollector:
    """DataCollector 클래스 테스트"""
    
    @patch('src.data.collector.pyupbit.get_ohlcv')
    def test_get_chart_data_success(self, mock_get_ohlcv, sample_chart_data):
        """차트 데이터 조회 성공 테스트"""
        mock_get_ohlcv.return_value = sample_chart_data
        
        result = DataCollector.get_chart_data("KRW-ETH")
        
        assert result is not None
        assert 'day' in result
        assert 'minute60' in result
        assert 'minute15' in result
        assert mock_get_ohlcv.call_count == 3
    
    @patch('src.data.collector.pyupbit.get_ohlcv')
    def test_get_chart_data_failure(self, mock_get_ohlcv):
        """차트 데이터 조회 실패 테스트"""
        mock_get_ohlcv.side_effect = Exception("API Error")
        
        result = DataCollector.get_chart_data("KRW-ETH")
        
        assert result is None
    
    def test_get_orderbook_summary(self, sample_orderbook):
        """오더북 요약 추출 테스트"""
        result = DataCollector.get_orderbook_summary(sample_orderbook)
        
        assert isinstance(result, dict)
        assert 'ask_prices' in result
        assert 'bid_prices' in result
        assert 'ask_volumes' in result
        assert 'bid_volumes' in result
        assert len(result['ask_prices']) == 5
        assert len(result['bid_prices']) == 5
    
    def test_get_orderbook_summary_empty(self):
        """빈 오더북 요약 테스트"""
        result = DataCollector.get_orderbook_summary(None)
        
        assert isinstance(result, dict)
        assert result['ask_prices'] == []
        assert result['bid_prices'] == []
    
    def test_get_orderbook_summary_with_depth(self, sample_orderbook):
        """깊이 지정 오더북 요약 테스트"""
        result = DataCollector.get_orderbook_summary(sample_orderbook, depth=3)
        
        assert len(result['ask_prices']) == 3
        assert len(result['bid_prices']) == 3
    
    @pytest.mark.unit
    @patch('src.data.collector.requests.get')
    def test_get_fear_greed_index_success(self, mock_get):
        """공포탐욕지수 조회 성공 테스트"""
        # API 응답 모킹
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "Fear and Greed Index",
            "data": [
                {
                    "value": "45",
                    "value_classification": "Fear",
                    "timestamp": "1230768000",
                    "time_until_update": "34567"
                }
            ],
            "metadata": {
                "error": None
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = DataCollector.get_fear_greed_index()
        
        assert result is not None
        assert result['value'] == 45
        assert result['classification'] == "Fear"
        assert isinstance(result['value'], int)
        assert 0 <= result['value'] <= 100
    
    @pytest.mark.unit
    @patch('src.data.collector.requests.get')
    def test_get_fear_greed_index_api_error(self, mock_get):
        """공포탐욕지수 API 에러 테스트"""
        mock_get.side_effect = Exception("API Error")
        
        result = DataCollector.get_fear_greed_index()
        
        assert result is None
    
    @pytest.mark.unit
    @patch('src.data.collector.requests.get')
    def test_get_fear_greed_index_extreme_fear(self, mock_get):
        """공포탐욕지수 극도의 공포 테스트"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "Fear and Greed Index",
            "data": [
                {
                    "value": "15",
                    "value_classification": "Extreme Fear",
                    "timestamp": "1230768000",
                    "time_until_update": "34567"
                }
            ],
            "metadata": {
                "error": None
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = DataCollector.get_fear_greed_index()
        
        assert result is not None
        assert result['value'] == 15
        assert result['classification'] == "Extreme Fear"
    
    @pytest.mark.unit
    @patch('src.data.collector.requests.get')
    def test_get_fear_greed_index_extreme_greed(self, mock_get):
        """공포탐욕지수 극도의 탐욕 테스트"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "Fear and Greed Index",
            "data": [
                {
                    "value": "85",
                    "value_classification": "Extreme Greed",
                    "timestamp": "1230768000",
                    "time_until_update": "34567"
                }
            ],
            "metadata": {
                "error": None
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = DataCollector.get_fear_greed_index()
        
        assert result is not None
        assert result['value'] == 85
        assert result['classification'] == "Extreme Greed"


class TestBTCDataCollection:
    """BTC 데이터 수집 테스트 (Phase 2)
    
    TDD 원칙: BTC 데이터 수집 기능을 테스트로 먼저 검증합니다.
    """
    
    @pytest.mark.unit
    @patch('src.data.collector.pyupbit.get_ohlcv')
    def test_get_btc_chart_data_success(self, mock_get_ohlcv, sample_chart_data):
        """BTC 차트 데이터 조회 성공 테스트"""
        # Given
        mock_get_ohlcv.return_value = sample_chart_data
        
        # When
        result = DataCollector.get_btc_chart_data()
        
        # Then
        assert result is not None
        assert 'day' in result
        assert 'minute60' in result
        assert 'minute15' in result
        # KRW-BTC 티커로 3번 호출 (일봉, 60분봉, 15분봉)
        assert mock_get_ohlcv.call_count == 3
        # 첫 번째 호출의 티커가 KRW-BTC인지 확인
        first_call_ticker = mock_get_ohlcv.call_args_list[0][0][0]
        assert first_call_ticker == "KRW-BTC"
    
    @pytest.mark.unit
    @patch('src.data.collector.pyupbit.get_ohlcv')
    def test_get_btc_chart_data_failure(self, mock_get_ohlcv):
        """BTC 차트 데이터 조회 실패 테스트"""
        # Given
        mock_get_ohlcv.side_effect = Exception("API Error")
        
        # When
        result = DataCollector.get_btc_chart_data()
        
        # Then
        assert result is None
    
    @pytest.mark.unit
    @patch('src.data.collector.pyupbit.get_ohlcv')
    def test_get_chart_data_with_btc_success(self, mock_get_ohlcv, sample_chart_data):
        """ETH + BTC 차트 데이터 동시 조회 성공 테스트"""
        # Given
        mock_get_ohlcv.return_value = sample_chart_data
        
        # When
        result = DataCollector.get_chart_data_with_btc("KRW-ETH")
        
        # Then
        assert result is not None
        assert 'eth' in result
        assert 'btc' in result
        
        # ETH 데이터 검증
        assert 'day' in result['eth']
        assert 'minute60' in result['eth']
        assert 'minute15' in result['eth']
        
        # BTC 데이터 검증
        assert 'day' in result['btc']
        assert 'minute60' in result['btc']
        assert 'minute15' in result['btc']
        
        # ETH 3번 + BTC 3번 = 총 6번 호출
        assert mock_get_ohlcv.call_count == 6
    
    @pytest.mark.unit
    @patch('src.data.collector.pyupbit.get_ohlcv')
    def test_get_chart_data_with_btc_eth_failure(self, mock_get_ohlcv):
        """ETH 데이터 조회 실패 시 BTC 데이터도 반환 안함"""
        # Given
        mock_get_ohlcv.side_effect = Exception("API Error")
        
        # When
        result = DataCollector.get_chart_data_with_btc("KRW-ETH")
        
        # Then
        assert result is None
    
    @pytest.mark.unit
    @patch('src.data.collector.pyupbit.get_ohlcv')
    def test_get_chart_data_with_btc_partial_failure(self, mock_get_ohlcv, sample_chart_data):
        """ETH는 성공, BTC는 실패 시 처리"""
        # Given
        # 첫 3번(ETH)은 성공, 다음 3번(BTC)은 실패
        mock_get_ohlcv.side_effect = [
            sample_chart_data, sample_chart_data, sample_chart_data,  # ETH 성공
            Exception("API Error"), None, None  # BTC 실패
        ]
        
        # When
        result = DataCollector.get_chart_data_with_btc("KRW-ETH")
        
        # Then
        # BTC 데이터 실패 시 전체 실패 처리
        assert result is None

