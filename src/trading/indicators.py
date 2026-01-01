"""
기술적 지표 계산
"""
import pandas as pd
import numpy as np
from typing import Dict


class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
        """
        이동평균선 계산
        
        Args:
            df: DataFrame
            period: 기간
            column: 계산할 컬럼명
            
        Returns:
            이동평균선 Series
        """
        return df[column].rolling(window=period).mean()
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
        """
        지수이동평균선 계산
        
        Args:
            df: DataFrame
            period: 기간
            column: 계산할 컬럼명
            
        Returns:
            지수이동평균선 Series
        """
        return df[column].ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
        """
        RSI (Relative Strength Index) 계산
        
        Args:
            df: DataFrame
            period: 기간 (기본값: 14)
            column: 계산할 컬럼명
            
        Returns:
            RSI Series
        """
        delta = df[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(
        df: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        column: str = 'close'
    ) -> Dict[str, pd.Series]:
        """
        MACD (Moving Average Convergence Divergence) 계산
        
        Args:
            df: DataFrame
            fast_period: 빠른 기간 (기본값: 12)
            slow_period: 느린 기간 (기본값: 26)
            signal_period: 시그널 기간 (기본값: 9)
            column: 계산할 컬럼명
            
        Returns:
            MACD 딕셔너리 (macd, signal, histogram)
        """
        ema_fast = df[column].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def calculate_bollinger_bands(
        df: pd.DataFrame,
        period: int = 20,
        std_dev: int = 2,
        column: str = 'close'
    ) -> Dict[str, pd.Series]:
        """
        볼린저 밴드 계산
        
        Args:
            df: DataFrame
            period: 기간 (기본값: 20)
            std_dev: 표준편차 배수 (기본값: 2)
            column: 계산할 컬럼명
            
        Returns:
            볼린저 밴드 딕셔너리 (upper, middle, lower)
        """
        middle_band = df[column].rolling(window=period).mean()
        std = df[column].rolling(window=period).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        return {
            'upper': upper_band,
            'middle': middle_band,
            'lower': lower_band
        }

    @staticmethod
    def calculate_bb_width(data: pd.DataFrame, period: int = 20) -> float:
        """
        볼린저 밴드 폭 계산

        BB Width = (Upper Band - Lower Band) / Middle Band × 100

        - BB Width < 4%: 수축 중 (진입 비추천)
        - BB Width >= 4%: 확장 중 (진입 가능)

        Args:
            data: DataFrame
            period: 기간 (기본값: 20)

        Returns:
            볼린저 밴드 폭 (%)
        """
        if len(data) < period:
            return 0.0

        close = data['close']

        # 볼린저 밴드 계산
        middle_band = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = middle_band + (std * 2)
        lower_band = middle_band - (std * 2)

        # BB Width 계산
        bb_width = ((upper_band - lower_band) / middle_band * 100).iloc[-1]

        if pd.isna(bb_width):
            return 0.0

        return float(bb_width)

    @staticmethod
    def calculate_atr(
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.Series:
        """
        ATR (Average True Range) 계산
        
        Args:
            df: DataFrame (high, low, close 컬럼 필요)
            period: 기간 (기본값: 14)
            
        Returns:
            ATR Series
        """
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def calculate_stochastic(
        df: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3
    ) -> Dict[str, pd.Series]:
        """
        Stochastic Oscillator 계산
        
        Args:
            df: DataFrame (high, low, close 컬럼 필요)
            k_period: %K 기간 (기본값: 14)
            d_period: %D 기간 (기본값: 3)
            
        Returns:
            Stochastic 딕셔너리 (k, d)
        """
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        
        k_percent = 100 * ((df['close'] - low_min) / (high_max - low_min))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'k': k_percent,
            'd': d_percent
        }
    
    @staticmethod
    def calculate_adx(
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.Series:
        """
        ADX (Average Directional Index) 계산
        
        Args:
            df: DataFrame (high, low, close 컬럼 필요)
            period: 기간 (기본값: 14)
            
        Returns:
            ADX Series
        """
        # True Range 계산
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Directional Movement
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # +DM과 -DM 중 큰 값만 남김
        condition = plus_dm > minus_dm
        plus_dm[~condition] = 0
        minus_dm[condition] = 0
        
        # Smoothing
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # DX 계산
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        
        # ADX는 DX의 이동평균
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    @staticmethod
    def calculate_obv(df: pd.DataFrame) -> pd.Series:
        """
        OBV (On-Balance Volume) 계산
        
        Args:
            df: DataFrame (close, volume 컬럼 필요)
            
        Returns:
            OBV Series
        """
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = df['volume'].iloc[0]
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    @staticmethod
    def calculate_cci(
        df: pd.DataFrame,
        period: int = 20
    ) -> pd.Series:
        """
        CCI (Commodity Channel Index) 계산
        
        Args:
            df: DataFrame (high, low, close 컬럼 필요)
            period: 기간 (기본값: 20)
            
        Returns:
            CCI Series
        """
        tp = (df['high'] + df['low'] + df['close']) / 3  # Typical Price
        sma_tp = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(
            lambda x: np.abs(x - x.mean()).mean()
        )
        
        cci = (tp - sma_tp) / (0.015 * mad)
        
        return cci
    
    @staticmethod
    def calculate_mfi(
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.Series:
        """
        MFI (Money Flow Index) 계산
        
        Args:
            df: DataFrame (high, low, close, volume 컬럼 필요)
            period: 기간 (기본값: 14)
            
        Returns:
            MFI Series
        """
        tp = (df['high'] + df['low'] + df['close']) / 3  # Typical Price
        raw_money_flow = tp * df['volume']
        
        positive_flow = raw_money_flow.where(tp > tp.shift(), 0)
        negative_flow = raw_money_flow.where(tp < tp.shift(), 0)
        
        positive_flow_sum = positive_flow.rolling(window=period).sum()
        negative_flow_sum = negative_flow.rolling(window=period).sum()
        
        money_flow_ratio = positive_flow_sum / negative_flow_sum
        mfi = 100 - (100 / (1 + money_flow_ratio))
        
        return mfi
    
    @staticmethod
    def calculate_williams_r(
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.Series:
        """
        Williams %R 계산
        
        Args:
            df: DataFrame (high, low, close 컬럼 필요)
            period: 기간 (기본값: 14)
            
        Returns:
            Williams %R Series
        """
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()
        
        williams_r = -100 * ((highest_high - df['close']) / (highest_high - lowest_low))
        
        return williams_r
    
    @staticmethod
    def get_latest_indicators(df: pd.DataFrame) -> Dict[str, float]:
        """
        최신 기술적 지표 값 계산
        
        Args:
            df: DataFrame
            
        Returns:
            최신 기술적 지표 딕셔너리
        """
        indicators = {}
        
        # 이동평균선
        for period in [5, 20, 60]:
            ma = TechnicalIndicators.calculate_ma(df, period)
            if not ma.empty:
                indicators[f'ma{period}'] = float(ma.iloc[-1])
        
        # RSI
        rsi = TechnicalIndicators.calculate_rsi(df)
        if not rsi.empty and not pd.isna(rsi.iloc[-1]):
            indicators['rsi'] = float(rsi.iloc[-1])
        
        # MACD
        macd_data = TechnicalIndicators.calculate_macd(df)
        if not macd_data['macd'].empty:
            indicators['macd'] = float(macd_data['macd'].iloc[-1])
            indicators['macd_signal'] = float(macd_data['signal'].iloc[-1])
            indicators['macd_histogram'] = float(macd_data['histogram'].iloc[-1])
        
        # 볼린저 밴드
        bb = TechnicalIndicators.calculate_bollinger_bands(df)
        if not bb['upper'].empty:
            indicators['bb_upper'] = float(bb['upper'].iloc[-1])
            indicators['bb_middle'] = float(bb['middle'].iloc[-1])
            indicators['bb_lower'] = float(bb['lower'].iloc[-1])

            # 볼린저 밴드 폭 계산
            bb_width_pct = TechnicalIndicators.calculate_bb_width(df)
            if bb_width_pct is not None:
                indicators['bb_width_pct'] = float(bb_width_pct)
        
        # ATR
        atr = TechnicalIndicators.calculate_atr(df)
        if not atr.empty and not pd.isna(atr.iloc[-1]):
            indicators['atr'] = float(atr.iloc[-1])
        
        # EMA (지수이동평균선)
        for period in [12, 26, 50]:
            ema = TechnicalIndicators.calculate_ema(df, period)
            if not ema.empty and not pd.isna(ema.iloc[-1]):
                indicators[f'ema{period}'] = float(ema.iloc[-1])
        
        # Stochastic Oscillator
        stoch = TechnicalIndicators.calculate_stochastic(df)
        if not stoch['k'].empty and not pd.isna(stoch['k'].iloc[-1]):
            indicators['stoch_k'] = float(stoch['k'].iloc[-1])
        if not stoch['d'].empty and not pd.isna(stoch['d'].iloc[-1]):
            indicators['stoch_d'] = float(stoch['d'].iloc[-1])
        
        # ADX
        adx = TechnicalIndicators.calculate_adx(df)
        if not adx.empty and not pd.isna(adx.iloc[-1]):
            indicators['adx'] = float(adx.iloc[-1])
        
        # OBV
        obv = TechnicalIndicators.calculate_obv(df)
        if not obv.empty and not pd.isna(obv.iloc[-1]):
            indicators['obv'] = float(obv.iloc[-1])
            # OBV 변화율 계산
            if len(obv) >= 2:
                obv_change = ((obv.iloc[-1] - obv.iloc[-2]) / obv.iloc[-2]) * 100
                indicators['obv_change_pct'] = float(obv_change)
        
        # CCI
        cci = TechnicalIndicators.calculate_cci(df)
        if not cci.empty and not pd.isna(cci.iloc[-1]):
            indicators['cci'] = float(cci.iloc[-1])
        
        # MFI
        mfi = TechnicalIndicators.calculate_mfi(df)
        if not mfi.empty and not pd.isna(mfi.iloc[-1]):
            indicators['mfi'] = float(mfi.iloc[-1])
        
        # Williams %R
        williams_r = TechnicalIndicators.calculate_williams_r(df)
        if not williams_r.empty and not pd.isna(williams_r.iloc[-1]):
            indicators['williams_r'] = float(williams_r.iloc[-1])
        
        # ROC (Rate of Change)
        roc = TechnicalIndicators.calculate_roc(df)
        if not roc.empty and not pd.isna(roc.iloc[-1]):
            indicators['roc'] = float(roc.iloc[-1])
        
        # ADX의 +DI, -DI
        di_data = TechnicalIndicators.calculate_directional_indicators(df)
        if not di_data['plus_di'].empty and not pd.isna(di_data['plus_di'].iloc[-1]):
            indicators['plus_di'] = float(di_data['plus_di'].iloc[-1])
        if not di_data['minus_di'].empty and not pd.isna(di_data['minus_di'].iloc[-1]):
            indicators['minus_di'] = float(di_data['minus_di'].iloc[-1])
        
        # 볼린저 밴드 폭 계산
        if 'bb_upper' in indicators and 'bb_lower' in indicators and 'bb_middle' in indicators:
            bb_width = ((indicators['bb_upper'] - indicators['bb_lower']) / indicators['bb_middle']) * 100
            indicators['bb_width'] = float(bb_width)
        
        # 켈트너 채널
        keltner = TechnicalIndicators.calculate_keltner_channels(df)
        if not keltner['upper'].empty:
            indicators['keltner_upper'] = float(keltner['upper'].iloc[-1])
            indicators['keltner_middle'] = float(keltner['middle'].iloc[-1])
            indicators['keltner_lower'] = float(keltner['lower'].iloc[-1])
        
        return indicators
    
    @staticmethod
    def calculate_roc(df: pd.DataFrame, period: int = 10, column: str = 'close') -> pd.Series:
        """
        ROC (Rate of Change) 계산
        
        Args:
            df: DataFrame
            period: 기간 (기본값: 10)
            column: 계산할 컬럼명
            
        Returns:
            ROC Series
        """
        roc = ((df[column] - df[column].shift(period)) / df[column].shift(period)) * 100
        return roc
    
    @staticmethod
    def calculate_directional_indicators(
        df: pd.DataFrame,
        period: int = 14
    ) -> Dict[str, pd.Series]:
        """
        방향성 지표 (+DI, -DI) 계산
        
        Args:
            df: DataFrame (high, low, close 컬럼 필요)
            period: 기간 (기본값: 14)
            
        Returns:
            방향성 지표 딕셔너리 (plus_di, minus_di)
        """
        # True Range 계산
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Directional Movement
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # +DM과 -DM 중 큰 값만 남김
        condition = plus_dm > minus_dm
        plus_dm[~condition] = 0
        minus_dm[condition] = 0
        
        # Smoothing
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        return {
            'plus_di': plus_di,
            'minus_di': minus_di
        }
    
    @staticmethod
    def calculate_keltner_channels(
        df: pd.DataFrame,
        period: int = 20,
        multiplier: float = 2.0,
        column: str = 'close'
    ) -> Dict[str, pd.Series]:
        """
        켈트너 채널 계산
        
        Args:
            df: DataFrame
            period: 기간 (기본값: 20)
            multiplier: ATR 배수 (기본값: 2.0)
            column: 계산할 컬럼명
            
        Returns:
            켈트너 채널 딕셔너리 (upper, middle, lower)
        """
        middle_band = df[column].rolling(window=period).mean()
        atr = TechnicalIndicators.calculate_atr(df, period=period)
        upper_band = middle_band + (atr * multiplier)
        lower_band = middle_band - (atr * multiplier)
        
        return {
            'upper': upper_band,
            'middle': middle_band,
            'lower': lower_band
        }
    
    @staticmethod
    def calculate_volume_indicators(df: pd.DataFrame) -> Dict[str, float]:
        """
        거래량 지표 계산
        
        Args:
            df: DataFrame (volume 컬럼 필요)
            
        Returns:
            거래량 지표 딕셔너리
        """
        indicators = {}
        
        if 'volume' not in df.columns:
            return indicators
        
        # 20일 평균 거래량
        volume_ma_20 = df['volume'].rolling(window=20).mean()
        if not volume_ma_20.empty and not pd.isna(volume_ma_20.iloc[-1]):
            indicators['volume_ma_20'] = float(volume_ma_20.iloc[-1])
            
            # 현재 거래량 / 평균 거래량 비율
            current_volume = df['volume'].iloc[-1]
            if indicators['volume_ma_20'] > 0:
                indicators['volume_ratio'] = float(current_volume / indicators['volume_ma_20'])
        
        # 거래량 추세
        if len(df) >= 5:
            recent_volumes = df['volume'].tail(5)
            if recent_volumes.is_monotonic_increasing:
                indicators['volume_trend'] = 'increasing'
            elif recent_volumes.is_monotonic_decreasing:
                indicators['volume_trend'] = 'decreasing'
            else:
                indicators['volume_trend'] = 'stable'
        
        # 평균의 2배 이상 거래량 여부
        if 'volume_ratio' in indicators:
            indicators['unusual_volume'] = indicators['volume_ratio'] >= 2.0
        
        return indicators
    
    @staticmethod
    def calculate_support_resistance_levels(
        df: pd.DataFrame,
        window: int = 20,
        num_levels: int = 3
    ) -> Dict[str, list]:
        """
        지지/저항 레벨 계산
        
        Args:
            df: DataFrame
            window: 분석 기간 (기본값: 20)
            num_levels: 반환할 레벨 수 (기본값: 3)
            
        Returns:
            지지/저항 레벨 딕셔너리
        """
        current_price = df['close'].iloc[-1]
        recent_data = df.tail(window)
        
        # 저점과 고점 찾기
        lows = recent_data['low'].rolling(window=3, center=True).min()
        highs = recent_data['high'].rolling(window=3, center=True).max()
        
        # 지지선 (현재가보다 낮은 저점들)
        support_levels = []
        for i, low in enumerate(lows):
            if not pd.isna(low) and low < current_price:
                # 같은 가격대에 몇 번 터치되었는지 계산
                touches = sum(abs(recent_data['low'] - low) < (current_price * 0.01))
                support_levels.append({
                    'price': float(low),
                    'strength': 'strong' if touches >= 3 else 'moderate' if touches >= 2 else 'weak',
                    'touches': int(touches)
                })
        
        # 저항선 (현재가보다 높은 고점들)
        resistance_levels = []
        for i, high in enumerate(highs):
            if not pd.isna(high) and high > current_price:
                touches = sum(abs(recent_data['high'] - high) < (current_price * 0.01))
                resistance_levels.append({
                    'price': float(high),
                    'strength': 'strong' if touches >= 3 else 'moderate' if touches >= 2 else 'weak',
                    'touches': int(touches)
                })
        
        # 가격 순으로 정렬하고 가까운 것만 선택
        support_levels.sort(key=lambda x: x['price'], reverse=True)
        resistance_levels.sort(key=lambda x: x['price'])
        
        return {
            'support_levels': support_levels[:num_levels],
            'resistance_levels': resistance_levels[:num_levels]
        }
    
    @staticmethod
    def detect_flash_crash(
        df: pd.DataFrame,
        threshold: float = 0.05,
        lookback: int = 5
    ) -> Dict[str, any]:
        """
        플래시 크래시 감지 (ATR 대비 변동성 체크 포함)
        
        정의:
        1. 최근 N개 캔들에서 threshold 이상 급락
        2. 급락 속도가 비정상적으로 빠름 (ATR 대비 체크)
        
        Args:
            df: 차트 데이터
            threshold: 급락 기준 (기본 5%)
            lookback: 확인할 캔들 수 (기본 5개)
            
        Returns:
            {
                'detected': bool,
                'max_drop': float,  # 최대 하락률 (%)
                'abnormal_ratio': float,  # ATR 대비 비율
                'description': str
            }
        """
        if df.empty or len(df) < lookback + 20:  # ATR 계산을 위해 최소 20일 필요
            return {
                'detected': False,
                'max_drop': 0.0,
                'abnormal_ratio': 0.0,
                'description': '데이터 부족 (ATR 계산 불가)'
            }
        
        try:
            recent = df.tail(lookback)
            
            # 1. 절대적 하락률 체크
            max_high = recent['high'].max()
            current_price = recent['close'].iloc[-1]
            price_change = (current_price - max_high) / max_high
            
            # 2. ATR 대비 하락폭 체크 (변동성 고려)
            atr = TechnicalIndicators.calculate_atr(df, period=14)
            if atr.empty or pd.isna(atr.iloc[-1]):
                atr_value = max_high * 0.02  # Fallback: 2%
            else:
                atr_value = float(atr.iloc[-1])
            
            expected_move = atr_value * lookback  # N일간 예상 변동폭
            actual_move = abs(current_price - max_high)
            
            abnormal_ratio = actual_move / expected_move if expected_move > 0 else 0
            
            # 3. 비정상적 하락 판단
            is_abnormal_drop = abnormal_ratio > 2.0  # 예상의 2배 이상
            
            if price_change < -threshold and is_abnormal_drop:
                return {
                    'detected': True,
                    'max_drop': abs(price_change) * 100,
                    'abnormal_ratio': float(abnormal_ratio),
                    'description': f'플래시 크래시 감지: {lookback}개 캔들에서 {abs(price_change)*100:.2f}% 급락 (ATR 대비 {abnormal_ratio:.1f}배)'
                }
            
            return {
                'detected': False,
                'max_drop': abs(price_change) * 100 if price_change < 0 else 0.0,
                'abnormal_ratio': float(abnormal_ratio),
                'description': '플래시 크래시 없음'
            }
            
        except Exception as e:
            return {
                'detected': False,
                'max_drop': 0.0,
                'abnormal_ratio': 0.0,
                'description': f'계산 오류: {str(e)}'
            }
    
    @staticmethod
    def detect_rsi_divergence(
        df: pd.DataFrame,
        lookback: int = 20,
        rsi_period: int = 14
    ) -> Dict[str, any]:
        """
        RSI 다이버전스 감지
        
        다이버전스 정의:
        - Bearish (하락): 가격 고점 상승, RSI 고점 하락
        - Bullish (상승): 가격 저점 하락, RSI 저점 상승
        
        Args:
            df: 차트 데이터
            lookback: 분석 기간 (기본 20일)
            rsi_period: RSI 계산 기간 (기본 14)
            
        Returns:
            {
                'type': 'bearish_divergence' | 'bullish_divergence' | 'none',
                'confidence': 'high' | 'medium' | 'low',
                'price_peaks': [peak1, peak2],  # 하락 다이버전스 시
                'rsi_peaks': [rsi1, rsi2],  # 하락 다이버전스 시
                'price_troughs': [trough1, trough2],  # 상승 다이버전스 시
                'rsi_troughs': [rsi1, rsi2],  # 상승 다이버전스 시
                'description': str
            }
        """
        if df.empty or len(df) < lookback + rsi_period:
            return {
                'type': 'none',
                'confidence': 'low',
                'description': '데이터 부족'
            }
        
        try:
            # RSI 계산
            rsi = TechnicalIndicators.calculate_rsi(df, period=rsi_period)
            
            if len(rsi) < lookback:
                return {
                    'type': 'none',
                    'confidence': 'low',
                    'description': 'RSI 데이터 부족'
                }
            
            # 최근 데이터
            recent_price = df['close'].tail(lookback).values
            recent_high = df['high'].tail(lookback).values
            recent_low = df['low'].tail(lookback).values
            recent_rsi = rsi.tail(lookback).values
            
            # scipy 사용 시도, 없으면 대안 사용
            try:
                from scipy.signal import find_peaks
                use_scipy = True
            except ImportError:
                use_scipy = False
            
            if use_scipy:
                # scipy를 사용한 고점/저점 찾기 (prominence 낮춤: 2 → 0.5)
                price_peaks, _ = find_peaks(recent_high, prominence=0.5)
                rsi_peaks, _ = find_peaks(recent_rsi, prominence=2)
                price_troughs, _ = find_peaks(-recent_low, prominence=0.5)
                rsi_troughs, _ = find_peaks(-recent_rsi, prominence=2)
            else:
                # numpy만 사용한 간단한 고점/저점 찾기
                price_peaks = TechnicalIndicators._find_peaks_simple(recent_high, prominence=0.5)
                rsi_peaks = TechnicalIndicators._find_peaks_simple(recent_rsi, prominence=2)
                price_troughs = TechnicalIndicators._find_peaks_simple(-recent_low, prominence=0.5)
                rsi_troughs = TechnicalIndicators._find_peaks_simple(-recent_rsi, prominence=2)
            
            # 디버깅: 고점/저점 개수 로깅
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🔍 다이버전스 분석: price_peaks={len(price_peaks)}, rsi_peaks={len(rsi_peaks)}, price_troughs={len(price_troughs)}, rsi_troughs={len(rsi_troughs)}")
            
            # 하락 다이버전스 체크 (최근 2개 고점 비교)
            if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
                # 가격 고점은 상승
                price_higher = recent_high[price_peaks[-1]] > recent_high[price_peaks[-2]]
                # RSI 고점은 하락
                rsi_lower = recent_rsi[rsi_peaks[-1]] < recent_rsi[rsi_peaks[-2]]
                
                if price_higher and rsi_lower:
                    # 고점 간 거리로 신뢰도 판단
                    peak_distance = abs(price_peaks[-1] - rsi_peaks[-1])
                    confidence = 'high' if peak_distance < 3 else 'medium'
                    
                    return {
                        'type': 'bearish_divergence',
                        'confidence': confidence,
                        'price_peaks': [float(recent_high[p]) for p in price_peaks[-2:]],
                        'rsi_peaks': [float(recent_rsi[p]) for p in rsi_peaks[-2:]],
                        'description': f'가격 고점 {recent_high[price_peaks[-2]]:.0f}→{recent_high[price_peaks[-1]]:.0f}, RSI 고점 {recent_rsi[rsi_peaks[-2]]:.1f}→{recent_rsi[rsi_peaks[-1]]:.1f}'
                    }
            
            # 상승 다이버전스 체크 (저점 찾기)
            if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
                # 가격 저점은 하락
                price_lower = recent_low[price_troughs[-1]] < recent_low[price_troughs[-2]]
                # RSI 저점은 상승
                rsi_higher = recent_rsi[rsi_troughs[-1]] > recent_rsi[rsi_troughs[-2]]
                
                if price_lower and rsi_higher:
                    trough_distance = abs(price_troughs[-1] - rsi_troughs[-1])
                    confidence = 'high' if trough_distance < 3 else 'medium'
                    
                    return {
                        'type': 'bullish_divergence',
                        'confidence': confidence,
                        'price_troughs': [float(recent_low[t]) for t in price_troughs[-2:]],
                        'rsi_troughs': [float(recent_rsi[t]) for t in rsi_troughs[-2:]],
                        'description': f'가격 저점 {recent_low[price_troughs[-2]]:.0f}→{recent_low[price_troughs[-1]]:.0f}, RSI 저점 {recent_rsi[rsi_troughs[-2]]:.1f}→{recent_rsi[rsi_troughs[-1]]:.1f}'
                    }
            
            return {
                'type': 'none',
                'confidence': 'low',
                'description': '다이버전스 없음'
            }
            
        except Exception as e:
            return {
                'type': 'none',
                'confidence': 'low',
                'description': f'계산 오류: {str(e)}'
            }
    
    @staticmethod
    def _find_peaks_simple(data: np.ndarray, prominence: float = 2.0) -> np.ndarray:
        """
        scipy 없이 간단한 고점 찾기
        
        고점 정의: 양옆보다 높은 점 (prominence는 필터링용)
        
        Args:
            data: 데이터 배열
            prominence: 최소 돌출도 (단순 비교에서는 사용 안 함, 호환성용)
            
        Returns:
            고점 인덱스 배열
        """
        peaks = []
        
        for i in range(1, len(data) - 1):
            # 단순히 양옆보다 높으면 고점으로 인정 (prominence 조건 완화)
            left_higher = data[i] >= data[i-1]
            right_higher = data[i] >= data[i+1]
            
            if left_higher and right_higher:
                peaks.append(i)
        
        return np.array(peaks)

