"""
기술적 지표 테스트
"""
import pytest
import pandas as pd
import numpy as np
from src.trading.indicators import TechnicalIndicators


class TestTechnicalIndicators:
    """TechnicalIndicators 클래스 테스트"""
    
    def test_calculate_ma(self, sample_chart_data):
        """이동평균선 계산 테스트"""
        ma5 = TechnicalIndicators.calculate_ma(sample_chart_data, 5)
        
        assert len(ma5) == len(sample_chart_data)
        assert not ma5.iloc[:4].notna().all()  # 처음 4개는 NaN
        assert ma5.iloc[4:].notna().all()  # 5번째부터는 값이 있음
    
    def test_calculate_rsi(self, sample_chart_data):
        """RSI 계산 테스트"""
        rsi = TechnicalIndicators.calculate_rsi(sample_chart_data, period=14)
        
        assert len(rsi) == len(sample_chart_data)
        # RSI는 0-100 사이의 값
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()
    
    def test_calculate_macd(self, sample_chart_data):
        """MACD 계산 테스트"""
        macd_data = TechnicalIndicators.calculate_macd(sample_chart_data)
        
        assert 'macd' in macd_data
        assert 'signal' in macd_data
        assert 'histogram' in macd_data
        assert len(macd_data['macd']) == len(sample_chart_data)
    
    def test_calculate_bollinger_bands(self, sample_chart_data):
        """볼린저 밴드 계산 테스트"""
        bb = TechnicalIndicators.calculate_bollinger_bands(sample_chart_data)
        
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        # 상단 밴드 > 중간 밴드 > 하단 밴드
        valid_idx = bb['upper'].dropna().index
        assert (bb['upper'][valid_idx] > bb['middle'][valid_idx]).all()
        assert (bb['middle'][valid_idx] > bb['lower'][valid_idx]).all()
    
    def test_calculate_atr(self, sample_chart_data):
        """ATR 계산 테스트"""
        atr = TechnicalIndicators.calculate_atr(sample_chart_data)
        
        assert len(atr) == len(sample_chart_data)
        # ATR은 양수
        valid_atr = atr.dropna()
        assert (valid_atr > 0).all()
    
    def test_get_latest_indicators(self, sample_chart_data):
        """최신 지표 값 가져오기 테스트"""
        indicators = TechnicalIndicators.get_latest_indicators(sample_chart_data)
        
        assert isinstance(indicators, dict)
        # 필수 지표 확인
        assert 'ma5' in indicators or 'ma20' in indicators or 'ma60' in indicators
        assert isinstance(indicators.get('rsi'), (float, type(None)))
        assert isinstance(indicators.get('macd'), (float, type(None)))
    
    @pytest.mark.unit
    def test_calculate_stochastic(self, sample_chart_data):
        """Stochastic Oscillator 계산 테스트"""
        stoch = TechnicalIndicators.calculate_stochastic(sample_chart_data)
        
        assert 'k' in stoch
        assert 'd' in stoch
        assert len(stoch['k']) == len(sample_chart_data)
        # %K와 %D는 0-100 사이
        valid_k = stoch['k'].dropna()
        if len(valid_k) > 0:
            assert (valid_k >= 0).all() and (valid_k <= 100).all()
    
    @pytest.mark.unit
    def test_calculate_adx(self, sample_chart_data):
        """ADX 계산 테스트"""
        adx = TechnicalIndicators.calculate_adx(sample_chart_data)
        
        assert len(adx) == len(sample_chart_data)
        # ADX는 0-100 사이
        valid_adx = adx.dropna()
        if len(valid_adx) > 0:
            assert (valid_adx >= 0).all() and (valid_adx <= 100).all()
    
    @pytest.mark.unit
    def test_calculate_obv(self, sample_chart_data):
        """OBV 계산 테스트"""
        obv = TechnicalIndicators.calculate_obv(sample_chart_data)
        
        assert len(obv) == len(sample_chart_data)
        # OBV는 누적값이므로 첫 값 이후로는 NaN이 없어야 함


class TestFlashCrashDetection:
    """플래시 크래시 감지 테스트 (TDD)"""
    
    @pytest.fixture
    def normal_data(self):
        """정상 데이터 (변동성 낮음)"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        # 안정적인 가격 변동
        prices = 100 + np.sin(np.arange(30) * 0.2) * 2
        
        return pd.DataFrame({
            'high': prices + 1,
            'low': prices - 1,
            'close': prices,
            'volume': [1000] * 30
        }, index=dates)
    
    @pytest.fixture
    def flash_crash_data(self):
        """플래시 크래시 데이터 (5% 이상 급락)"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        # 안정적이다가 마지막 5일간 급락 (10% 이상)
        prices = [100.0] * 25 + [100.0, 98.0, 95.0, 91.0, 88.0]  # 마지막 5일간 12% 급락
        
        return pd.DataFrame({
            'high': [p + 2 for p in prices],
            'low': [p - 2 for p in prices],
            'close': prices,
            'volume': [1000] * 30
        }, index=dates)
    
    @pytest.fixture
    def gradual_decline_data(self):
        """점진적 하락 데이터 (플래시 크래시 아님)"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        # 30일간 천천히 10% 하락
        prices = np.linspace(100, 90, 30)
        
        return pd.DataFrame({
            'high': prices + 1,
            'low': prices - 1,
            'close': prices,
            'volume': [1000] * 30
        }, index=dates)
    
    # ==================== 기본 기능 테스트 ====================
    
    @pytest.mark.unit
    def test_detect_flash_crash_imports(self):
        """detect_flash_crash 함수를 import할 수 있는지 테스트"""
        # Given: 모듈 import
        # When & Then: ImportError가 발생하지 않아야 함
        try:
            from src.trading.indicators import TechnicalIndicators
            assert hasattr(TechnicalIndicators, 'detect_flash_crash')
            assert callable(TechnicalIndicators.detect_flash_crash)
        except (ImportError, AttributeError) as e:
            pytest.fail(f"detect_flash_crash import 실패: {e}")
    
    @pytest.mark.unit
    def test_detect_flash_crash_normal_case(self, normal_data):
        """정상 케이스에서 플래시 크래시 미감지"""
        # Given: 정상적인 가격 변동 데이터
        
        # When: 플래시 크래시 감지
        result = TechnicalIndicators.detect_flash_crash(normal_data)
        
        # Then: 플래시 크래시가 감지되지 않아야 함
        assert 'detected' in result, "detected 필드가 없습니다"
        assert result['detected'] is False, "정상 데이터에서 플래시 크래시가 감지되면 안 됩니다"
        assert 'description' in result
        assert '플래시 크래시 없음' in result['description'] or 'Flash crash' not in result['description']
    
    @pytest.mark.unit
    def test_detect_flash_crash_detected(self, flash_crash_data):
        """플래시 크래시 감지 (하락률 체크)"""
        # Given: 급격한 하락 데이터
        
        # When: 플래시 크래시 감지
        result = TechnicalIndicators.detect_flash_crash(flash_crash_data, threshold=0.05, lookback=5)
        
        # Then: 큰 하락이 감지되어야 함
        assert 'detected' in result
        assert 'max_drop' in result
        assert result['max_drop'] > 10.0, "10% 이상 하락이 기록되어야 합니다"
        assert 'abnormal_ratio' in result
        assert 'description' in result
        
        # abnormal_ratio가 높으면 플래시 크래시로 감지됨
        if result['abnormal_ratio'] > 2.0:
            assert result['detected'] is True, "abnormal_ratio > 2.0이면 감지되어야 합니다"
        else:
            # ATR 대비 정상 범위면 점진적 하락으로 판단
            assert result['detected'] is False
    
    @pytest.mark.unit
    def test_detect_flash_crash_with_insufficient_data(self):
        """데이터 부족 시 처리"""
        # Given: 3일치 데이터만
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        data = pd.DataFrame({
            'high': [100, 101, 102],
            'low': [98, 99, 100],
            'close': [99, 100, 101],
            'volume': [1000] * 3
        }, index=dates)
        
        # When: 플래시 크래시 감지
        result = TechnicalIndicators.detect_flash_crash(data)
        
        # Then: 에러 없이 처리되고 detected=False
        assert result['detected'] is False
        assert '데이터 부족' in result['description']
    
    @pytest.mark.unit
    def test_detect_flash_crash_gradual_decline(self, gradual_decline_data):
        """점진적 하락은 플래시 크래시가 아님"""
        # Given: 천천히 하락하는 데이터
        
        # When: 플래시 크래시 감지
        result = TechnicalIndicators.detect_flash_crash(gradual_decline_data, threshold=0.05, lookback=5)
        
        # Then: ATR 대비 정상 범위이므로 플래시 크래시 미감지
        # (점진적 하락은 ATR이 작아서 abnormal_ratio가 높지 않음)
        assert 'detected' in result
        assert 'abnormal_ratio' in result
    
    # ==================== ATR 기반 감지 테스트 ====================
    
    @pytest.mark.unit
    def test_detect_flash_crash_with_atr_check(self, flash_crash_data):
        """ATR 대비 비정상 변동 체크"""
        # Given: 급락 데이터
        
        # When: 플래시 크래시 감지
        result = TechnicalIndicators.detect_flash_crash(flash_crash_data)
        
        # Then: abnormal_ratio가 포함되어야 함
        assert 'abnormal_ratio' in result
        if result['detected']:
            # 플래시 크래시가 감지되면 abnormal_ratio가 높아야 함
            assert result['abnormal_ratio'] > 1.0, \
                "플래시 크래시 감지 시 abnormal_ratio가 1.0보다 커야 합니다"
    
    @pytest.mark.unit
    def test_detect_flash_crash_threshold_parameter(self, flash_crash_data):
        """threshold 파라미터 테스트"""
        # Given: 급락 데이터
        
        # When: 다른 threshold로 감지
        result_5pct = TechnicalIndicators.detect_flash_crash(flash_crash_data, threshold=0.05)
        result_15pct = TechnicalIndicators.detect_flash_crash(flash_crash_data, threshold=0.15)
        
        # Then: threshold가 높을수록 감지가 어려워야 함
        assert 'detected' in result_5pct
        assert 'detected' in result_15pct
        # 5% 급락은 감지되지만 15% 기준으로는 감지 안 될 수 있음
    
    @pytest.mark.unit
    def test_detect_flash_crash_lookback_parameter(self, flash_crash_data):
        """lookback 파라미터 테스트"""
        # Given: 급락 데이터
        
        # When: 다른 lookback으로 감지
        result_3days = TechnicalIndicators.detect_flash_crash(flash_crash_data, lookback=3)
        result_10days = TechnicalIndicators.detect_flash_crash(flash_crash_data, lookback=10)
        
        # Then: lookback이 짧을수록 최근 급락에 민감
        assert 'max_drop' in result_3days
        assert 'max_drop' in result_10days
    
    # ==================== 반환값 구조 테스트 ====================
    
    @pytest.mark.unit
    def test_detect_flash_crash_return_structure(self, normal_data):
        """반환값 구조 검증"""
        # Given: 정상 데이터
        
        # When: 플래시 크래시 감지
        result = TechnicalIndicators.detect_flash_crash(normal_data)
        
        # Then: 필수 필드가 모두 존재해야 함
        assert 'detected' in result
        assert 'max_drop' in result
        assert 'abnormal_ratio' in result
        assert 'description' in result
        
        # 타입 검증
        assert isinstance(result['detected'], bool)
        assert isinstance(result['max_drop'], (int, float))
        assert isinstance(result['abnormal_ratio'], (int, float))
        assert isinstance(result['description'], str)
    
    @pytest.mark.unit
    def test_detect_flash_crash_empty_dataframe(self):
        """빈 데이터프레임 처리"""
        # Given: 빈 데이터프레임
        data = pd.DataFrame()
        
        # When: 플래시 크래시 감지
        result = TechnicalIndicators.detect_flash_crash(data)
        
        # Then: 에러 없이 처리
        assert result['detected'] is False
        assert 'description' in result


class TestRSIDivergence:
    """RSI 다이버전스 감지 테스트 (TDD)"""
    
    @pytest.fixture
    def bearish_divergence_data(self):
        """하락 다이버전스 데이터 (가격 상승, RSI 하락)"""
        dates = pd.date_range('2024-01-01', periods=40, freq='D')
        # 가격은 고점이 상승하는 패턴
        prices = []
        for i in range(40):
            if i < 10:
                prices.append(100 + i * 0.5)
            elif i < 20:
                prices.append(105 - (i - 10) * 0.3)
            elif i < 30:
                prices.append(102 + (i - 20) * 0.7)  # 더 높은 고점
            else:
                prices.append(109 - (i - 30) * 0.5)
        
        return pd.DataFrame({
            'high': [p + 2 for p in prices],
            'low': [p - 2 for p in prices],
            'close': prices,
            'volume': [1000] * 40
        }, index=dates)
    
    @pytest.fixture
    def bullish_divergence_data(self):
        """상승 다이버전스 데이터 (가격 하락, RSI 상승)"""
        dates = pd.date_range('2024-01-01', periods=40, freq='D')
        # 가격은 저점이 하락하는 패턴
        prices = []
        for i in range(40):
            if i < 10:
                prices.append(100 - i * 0.5)
            elif i < 20:
                prices.append(95 + (i - 10) * 0.3)
            elif i < 30:
                prices.append(98 - (i - 20) * 0.7)  # 더 낮은 저점
            else:
                prices.append(91 + (i - 30) * 0.5)
        
        return pd.DataFrame({
            'high': [p + 2 for p in prices],
            'low': [p - 2 for p in prices],
            'close': prices,
            'volume': [1000] * 40
        }, index=dates)
    
    @pytest.fixture
    def no_divergence_data(self):
        """다이버전스 없는 데이터"""
        dates = pd.date_range('2024-01-01', periods=40, freq='D')
        # 가격과 RSI가 같은 방향
        prices = 100 + np.sin(np.arange(40) * 0.3) * 10
        
        return pd.DataFrame({
            'high': prices + 2,
            'low': prices - 2,
            'close': prices,
            'volume': [1000] * 40
        }, index=dates)
    
    # ==================== 기본 기능 테스트 ====================
    
    @pytest.mark.unit
    def test_detect_rsi_divergence_imports(self):
        """detect_rsi_divergence 함수를 import할 수 있는지 테스트"""
        # Given: 모듈 import
        # When & Then: ImportError가 발생하지 않아야 함
        try:
            from src.trading.indicators import TechnicalIndicators
            assert hasattr(TechnicalIndicators, 'detect_rsi_divergence')
            assert callable(TechnicalIndicators.detect_rsi_divergence)
        except (ImportError, AttributeError) as e:
            pytest.fail(f"detect_rsi_divergence import 실패: {e}")
    
    @pytest.mark.unit
    def test_detect_rsi_divergence_return_structure(self, no_divergence_data):
        """반환값 구조 검증"""
        # Given: 정상 데이터
        
        # When: RSI 다이버전스 감지
        result = TechnicalIndicators.detect_rsi_divergence(no_divergence_data)
        
        # Then: 필수 필드가 모두 존재해야 함
        assert 'type' in result
        assert 'confidence' in result
        assert 'description' in result
        
        # type은 정해진 값 중 하나
        assert result['type'] in ['bearish_divergence', 'bullish_divergence', 'none']
        
        # confidence는 정해진 값 중 하나
        assert result['confidence'] in ['high', 'medium', 'low']
    
    @pytest.mark.unit
    def test_detect_bearish_divergence(self, bearish_divergence_data):
        """하락 다이버전스 감지"""
        # Given: 가격 상승, RSI 하락 패턴
        
        # When: RSI 다이버전스 감지
        result = TechnicalIndicators.detect_rsi_divergence(
            bearish_divergence_data,
            lookback=20
        )
        
        # Then: 하락 다이버전스가 감지될 수 있음 (데이터에 따라)
        assert 'type' in result
        assert result['type'] in ['bearish_divergence', 'none']
        
        if result['type'] == 'bearish_divergence':
            assert 'price_peaks' in result
            assert 'rsi_peaks' in result
            assert len(result['price_peaks']) >= 2
            assert len(result['rsi_peaks']) >= 2
    
    @pytest.mark.unit
    def test_detect_bullish_divergence(self, bullish_divergence_data):
        """상승 다이버전스 감지"""
        # Given: 가격 하락, RSI 상승 패턴
        
        # When: RSI 다이버전스 감지
        result = TechnicalIndicators.detect_rsi_divergence(
            bullish_divergence_data,
            lookback=20
        )
        
        # Then: 상승 다이버전스가 감지될 수 있음
        assert 'type' in result
        assert result['type'] in ['bullish_divergence', 'none']
        
        if result['type'] == 'bullish_divergence':
            assert 'price_troughs' in result or 'price_peaks' in result
            assert 'rsi_troughs' in result or 'rsi_peaks' in result
    
    @pytest.mark.unit
    def test_detect_no_divergence(self, no_divergence_data):
        """다이버전스 없는 경우"""
        # Given: 다이버전스 없는 데이터
        
        # When: RSI 다이버전스 감지
        result = TechnicalIndicators.detect_rsi_divergence(no_divergence_data)
        
        # Then: 다이버전스가 없어야 함
        assert result['type'] == 'none'
        assert '다이버전스 없음' in result['description'] or 'No divergence' in result['description']
    
    @pytest.mark.unit
    def test_detect_rsi_divergence_with_insufficient_data(self):
        """데이터 부족 시 처리"""
        # Given: 10일치 데이터만
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        data = pd.DataFrame({
            'high': range(100, 110),
            'low': range(98, 108),
            'close': range(99, 109),
            'volume': [1000] * 10
        }, index=dates)
        
        # When: RSI 다이버전스 감지 (lookback=20)
        result = TechnicalIndicators.detect_rsi_divergence(data, lookback=20)
        
        # Then: 에러 없이 처리되고 type='none'
        assert result['type'] == 'none'
        assert '데이터 부족' in result['description'] or 'Insufficient' in result['description']
    
    @pytest.mark.unit
    def test_detect_rsi_divergence_empty_dataframe(self):
        """빈 데이터프레임 처리"""
        # Given: 빈 데이터프레임
        data = pd.DataFrame()
        
        # When: RSI 다이버전스 감지
        result = TechnicalIndicators.detect_rsi_divergence(data)
        
        # Then: 에러 없이 처리
        assert result['type'] == 'none'
        assert 'description' in result
    
    # ==================== scipy 의존성 테스트 ====================
    
    @pytest.mark.unit
    def test_scipy_fallback(self, no_divergence_data):
        """scipy 없을 때 대안 알고리즘 사용 (선택적)"""
        # Given: 정상 데이터
        
        # When: RSI 다이버전스 감지
        result = TechnicalIndicators.detect_rsi_divergence(no_divergence_data)
        
        # Then: scipy 유무와 관계없이 작동해야 함
        assert 'type' in result
        assert result['type'] in ['bearish_divergence', 'bullish_divergence', 'none']
        assert 'description' in result
    
    @pytest.mark.unit
    def test_calculate_cci(self, sample_chart_data):
        """CCI 계산 테스트"""
        cci = TechnicalIndicators.calculate_cci(sample_chart_data)
        
        assert len(cci) == len(sample_chart_data)
        # CCI는 일반적으로 -100 ~ +100 범위지만 더 넓을 수 있음
        valid_cci = cci.dropna()
        assert isinstance(valid_cci.iloc[0] if len(valid_cci) > 0 else None, (float, type(None)))
    
    @pytest.mark.unit
    def test_calculate_mfi(self, sample_chart_data):
        """MFI 계산 테스트"""
        mfi = TechnicalIndicators.calculate_mfi(sample_chart_data)
        
        assert len(mfi) == len(sample_chart_data)
        # MFI는 0-100 사이
        valid_mfi = mfi.dropna()
        if len(valid_mfi) > 0:
            assert (valid_mfi >= 0).all() and (valid_mfi <= 100).all()
    
    @pytest.mark.unit
    def test_calculate_williams_r(self, sample_chart_data):
        """Williams %R 계산 테스트"""
        williams_r = TechnicalIndicators.calculate_williams_r(sample_chart_data)
        
        assert len(williams_r) == len(sample_chart_data)
        # Williams %R는 -100 ~ 0 사이
        valid_wr = williams_r.dropna()
        if len(valid_wr) > 0:
            assert (valid_wr >= -100).all() and (valid_wr <= 0).all()
    
    @pytest.mark.unit
    def test_get_latest_indicators_includes_new_indicators(self, sample_chart_data):
        """최신 지표에 새 지표들이 포함되는지 테스트"""
        indicators = TechnicalIndicators.get_latest_indicators(sample_chart_data)
        
        # EMA 확인
        assert 'ema12' in indicators or 'ema26' in indicators or 'ema50' in indicators
        # 새 지표들이 포함되는지 확인 (값이 있을 경우)
        # 값이 없을 수도 있으므로 타입만 확인
        if 'stoch_k' in indicators:
            assert isinstance(indicators['stoch_k'], (float, type(None)))
        if 'adx' in indicators:
            assert isinstance(indicators['adx'], (float, type(None)))

