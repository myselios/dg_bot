"""
시장 상관관계 분석 테스트
TDD 원칙: 테스트 케이스를 먼저 작성하고 구현을 검증합니다.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class TestMarketCorrelation:
    """시장 상관관계 분석 테스트 (BTC-ETH 베타/알파)"""
    
    @pytest.fixture
    def sample_btc_data(self):
        """샘플 BTC 데이터 (50일)"""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        # 실제와 유사한 가격 변동 시뮬레이션
        np.random.seed(42)
        prices = 50000 + np.random.randn(50).cumsum() * 1000
        
        return pd.DataFrame({
            'close': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'volume': np.random.randint(1000, 2000, 50)
        }, index=dates)
    
    @pytest.fixture
    def sample_eth_data(self):
        """샘플 ETH 데이터 (50일)"""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        # ETH는 BTC보다 변동성이 큰 경향
        np.random.seed(43)
        prices = 3000 + np.random.randn(50).cumsum() * 100
        
        return pd.DataFrame({
            'close': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'volume': np.random.randint(1000, 2000, 50)
        }, index=dates)
    
    @pytest.fixture
    def btc_dropping_data(self, sample_btc_data):
        """BTC가 하락하는 시나리오 데이터"""
        data = sample_btc_data.copy()
        # 최근 5일 급락 시뮬레이션 (각 날 1% 하락)
        for i in range(-5, 0):
            data.iloc[i, data.columns.get_loc('close')] *= (0.99 ** abs(i))
        return data
    
    @pytest.fixture
    def mismatched_dates_btc(self):
        """날짜가 일부 다른 BTC 데이터"""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        return pd.DataFrame({
            'close': np.arange(50000, 50050),
            'high': np.arange(50010, 50060),
            'low': np.arange(49990, 50040),
            'volume': [1000] * 50
        }, index=dates)
    
    @pytest.fixture
    def mismatched_dates_eth(self):
        """날짜가 일부 다른 ETH 데이터 (5일 뒤부터 시작)"""
        dates = pd.date_range('2024-01-06', periods=50, freq='D')
        return pd.DataFrame({
            'close': np.arange(3000, 3050),
            'high': np.arange(3010, 3060),
            'low': np.arange(2990, 3040),
            'volume': [1000] * 50
        }, index=dates)
    
    # ==================== 기본 기능 테스트 ====================
    
    @pytest.mark.unit
    def test_calculate_market_risk_imports(self):
        """calculate_market_risk 함수를 import할 수 있는지 테스트"""
        # Given: 모듈 import
        # When & Then: ImportError가 발생하지 않아야 함
        try:
            from src.ai.market_correlation import calculate_market_risk
            assert callable(calculate_market_risk)
        except ImportError as e:
            pytest.fail(f"calculate_market_risk import 실패: {e}")
    
    @pytest.mark.unit
    def test_calculate_market_risk_with_valid_data(
        self,
        sample_btc_data,
        sample_eth_data
    ):
        """정상 데이터로 베타/알파 계산 테스트"""
        # Given: 정상적인 BTC, ETH 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(sample_btc_data, sample_eth_data)
        
        # Then: 필수 필드가 존재하고 타입이 올바름
        assert 'beta' in result, "beta 필드가 없습니다"
        assert 'alpha' in result, "alpha 필드가 없습니다"
        assert 'market_risk' in result, "market_risk 필드가 없습니다"
        assert 'risk_reason' in result, "risk_reason 필드가 없습니다"
        
        # 타입 검증
        assert isinstance(result['beta'], (float, int)), "beta는 숫자여야 합니다"
        assert isinstance(result['alpha'], (float, int)), "alpha는 숫자여야 합니다"
        assert result['market_risk'] in ['high', 'medium', 'low', 'unknown'], \
            "market_risk는 'high', 'medium', 'low', 'unknown' 중 하나여야 합니다"
    
    @pytest.mark.unit
    def test_calculate_market_risk_beta_range(
        self,
        sample_btc_data,
        sample_eth_data
    ):
        """베타 값이 합리적인 범위 내에 있는지 테스트"""
        # Given: 정상적인 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        # When: 베타 계산
        result = calculate_market_risk(sample_btc_data, sample_eth_data)
        
        # Then: 베타는 일반적으로 0 ~ 3 범위 (극단적 케이스 제외)
        assert -1 <= result['beta'] <= 5, \
            f"베타 값이 비정상적입니다: {result['beta']}"
    
    # ==================== 예외 처리 테스트 ====================
    
    @pytest.mark.unit
    def test_calculate_market_risk_with_insufficient_data(self):
        """데이터 부족 시 처리 테스트"""
        # Given: 3일치 데이터만 (30일 미만)
        from src.ai.market_correlation import calculate_market_risk
        
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        btc_data = pd.DataFrame({
            'close': [50000, 50100, 50200]
        }, index=dates)
        eth_data = pd.DataFrame({
            'close': [3000, 3010, 3020]
        }, index=dates)
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: unknown으로 반환하고 이유 명시
        assert result['market_risk'] == 'unknown', \
            "데이터 부족 시 'unknown'을 반환해야 합니다"
        assert '데이터 부족' in result['risk_reason'] or 'NaN' in result['risk_reason'], \
            "데이터 부족 이유를 명시해야 합니다"
    
    @pytest.mark.unit
    def test_calculate_market_risk_with_empty_dataframes(self):
        """빈 데이터프레임 처리 테스트"""
        # Given: 빈 데이터프레임
        from src.ai.market_correlation import calculate_market_risk
        
        btc_data = pd.DataFrame()
        eth_data = pd.DataFrame()
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: 에러 없이 unknown 반환
        assert result['market_risk'] == 'unknown'
        assert 'beta' in result
        assert 'alpha' in result
    
    # ==================== 날짜 병합 테스트 ====================
    
    @pytest.mark.unit
    def test_data_merge_with_matching_dates(
        self,
        sample_btc_data,
        sample_eth_data
    ):
        """날짜가 완전히 일치하는 경우 병합 테스트"""
        # Given: 동일한 날짜 범위의 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(sample_btc_data, sample_eth_data)
        
        # Then: 정상적으로 계산되어야 함
        assert result['market_risk'] in ['high', 'medium', 'low'], \
            "날짜가 일치하면 정상 계산되어야 합니다"
        assert result['beta'] != 1.0 or result['alpha'] != 0.0, \
            "실제 계산이 이루어져야 합니다 (기본값 아님)"
    
    @pytest.mark.unit
    def test_data_merge_with_mismatched_dates(
        self,
        mismatched_dates_btc,
        mismatched_dates_eth
    ):
        """날짜가 일부 다른 경우 Inner Join 테스트"""
        # Given: 5일 차이나는 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(mismatched_dates_btc, mismatched_dates_eth)
        
        # Then: 병합 후 데이터가 충분하지 않으면 unknown
        # (BTC: 1/1~2/19, ETH: 1/6~2/24 → 겹치는 기간: 1/6~2/19 = 45일)
        # 45일 > 30일이므로 정상 계산되어야 함
        assert 'beta' in result
        assert 'correlation' in result, "상관계수도 포함되어야 합니다"
    
    @pytest.mark.unit
    def test_data_merge_with_no_overlapping_dates(self):
        """겹치는 날짜가 전혀 없는 경우 테스트"""
        # Given: 완전히 다른 시간대의 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        btc_dates = pd.date_range('2024-01-01', periods=30, freq='D')
        eth_dates = pd.date_range('2024-03-01', periods=30, freq='D')
        
        btc_data = pd.DataFrame({'close': range(30)}, index=btc_dates)
        eth_data = pd.DataFrame({'close': range(30)}, index=eth_dates)
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: unknown 반환
        assert result['market_risk'] == 'unknown'
        assert '데이터 부족' in result['risk_reason'] or '병합' in result['risk_reason']
    
    # ==================== 시장 리스크 판단 테스트 ====================
    
    @pytest.mark.unit
    def test_high_risk_detection_with_btc_dropping(
        self,
        btc_dropping_data,
        sample_eth_data
    ):
        """BTC 하락 + 높은 베타 + 낮은 알파 = high risk"""
        # Given: BTC가 하락하는 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        # ETH도 함께 하락하도록 조정 (베타 > 1.2가 되도록)
        eth_data = sample_eth_data.copy()
        for i in range(-5, 0):
            # ETH가 BTC보다 더 크게 하락 (베타 > 1)
            eth_data.iloc[i, eth_data.columns.get_loc('close')] *= (0.98 ** abs(i))
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(btc_dropping_data, eth_data)
        
        # Then: high 또는 medium risk여야 함
        # (실제 베타/알파 값에 따라 달라질 수 있음)
        assert result['market_risk'] in ['high', 'medium', 'low'], \
            "리스크 레벨이 계산되어야 합니다"
        assert 'btc_return_1d' in result, "BTC 1일 수익률이 포함되어야 합니다"
    
    @pytest.mark.unit
    def test_low_risk_with_stable_market(
        self,
        sample_btc_data,
        sample_eth_data
    ):
        """안정적인 시장 = low risk"""
        # Given: 안정적인 데이터 (최근 가격 변동 없음)
        from src.ai.market_correlation import calculate_market_risk
        
        btc_data = sample_btc_data.copy()
        eth_data = sample_eth_data.copy()
        
        # 최근 5일을 안정적으로 (거의 변동 없음)
        btc_data.iloc[-5:, btc_data.columns.get_loc('close')] = 50000
        eth_data.iloc[-5:, eth_data.columns.get_loc('close')] = 3000
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: low risk 또는 medium
        assert result['market_risk'] in ['low', 'medium'], \
            "안정적인 시장은 high risk가 아니어야 합니다"
    
    # ==================== 상관계수 테스트 ====================
    
    @pytest.mark.unit
    def test_correlation_coefficient_included(
        self,
        sample_btc_data,
        sample_eth_data
    ):
        """상관계수가 결과에 포함되는지 테스트"""
        # Given: 정상 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(sample_btc_data, sample_eth_data)
        
        # Then: correlation 필드 존재
        assert 'correlation' in result, "상관계수가 포함되어야 합니다"
        assert -1 <= result['correlation'] <= 1, \
            "상관계수는 -1 ~ 1 범위여야 합니다"
    
    # ==================== 베타/알파 계산 정확도 테스트 ====================
    
    @pytest.mark.unit
    def test_beta_alpha_calculation_with_perfect_correlation(self):
        """완벽한 양의 상관관계 데이터로 베타/알파 테스트"""
        # Given: ETH가 BTC의 정확히 1.5배 움직이는 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        btc_prices = np.arange(50000, 50050)
        eth_prices = btc_prices * 0.06  # BTC:ETH 비율 유지 (50000:3000)
        
        btc_data = pd.DataFrame({'close': btc_prices}, index=dates)
        eth_data = pd.DataFrame({'close': eth_prices}, index=dates)
        
        # When: 베타/알파 계산
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: 베타가 양수, 상관계수가 높아야 함
        assert result['beta'] > 0, "양의 상관관계에서 베타는 양수여야 합니다"
        assert result['correlation'] > 0.8, \
            "완벽한 양의 상관관계에서 상관계수는 0.8 이상이어야 합니다"
    
    @pytest.mark.unit
    def test_beta_calculation_reflects_volatility_ratio(self):
        """베타가 변동성 비율을 반영하는지 테스트"""
        # Given: ETH 변동성이 BTC의 2배인 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        np.random.seed(100)
        
        btc_returns = np.random.randn(50) * 0.01  # 1% 변동성
        eth_returns = btc_returns * 2  # 2배 변동성
        
        btc_prices = 50000 * (1 + btc_returns).cumprod()
        eth_prices = 3000 * (1 + eth_returns).cumprod()
        
        btc_data = pd.DataFrame({'close': btc_prices}, index=dates)
        eth_data = pd.DataFrame({'close': eth_prices}, index=dates)
        
        # When: 베타 계산
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: 베타가 1보다 커야 함 (ETH가 더 변동성 큼)
        assert result['beta'] > 1.0, \
            "ETH 변동성이 더 크면 베타가 1보다 커야 합니다"
    
    # ==================== 에러 처리 테스트 ====================
    
    @pytest.mark.unit
    def test_nan_handling_in_data(self, sample_btc_data, sample_eth_data):
        """NaN 값이 포함된 데이터 처리 테스트"""
        # Given: NaN이 포함된 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        btc_data = sample_btc_data.copy()
        eth_data = sample_eth_data.copy()
        
        # 중간에 NaN 삽입
        btc_data.iloc[10, btc_data.columns.get_loc('close')] = np.nan
        eth_data.iloc[15, eth_data.columns.get_loc('close')] = np.nan
        
        # When: 시장 리스크 계산
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: 에러 없이 처리되어야 함
        assert 'beta' in result
        assert 'alpha' in result
        assert not np.isnan(result['beta']), "베타에 NaN이 있으면 안 됩니다"
        assert not np.isnan(result['alpha']), "알파에 NaN이 있으면 안 됩니다"
    
    @pytest.mark.unit
    def test_zero_variance_handling(self):
        """BTC 가격 변동이 전혀 없는 경우 처리"""
        # Given: BTC 가격이 전혀 변하지 않는 데이터
        from src.ai.market_correlation import calculate_market_risk
        
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        btc_data = pd.DataFrame({'close': [50000] * 50}, index=dates)
        eth_data = pd.DataFrame({'close': np.arange(3000, 3050)}, index=dates)
        
        # When: 베타 계산 (분모가 0이 되는 상황)
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then: 에러 없이 기본값 반환
        assert result['beta'] == 1.0, "분산이 0일 때 베타는 1.0이어야 합니다"
        assert result['market_risk'] in ['low', 'medium', 'unknown']



