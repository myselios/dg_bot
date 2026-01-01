"""
변동성 돌파 전략 기반 룰 전략

AI 호출 없이 3단계 관문 룰만으로 거래 신호를 생성합니다.
변동성 돌파 전략의 특성:
- 승률은 낮지만 손익비로 수익을 내는 전략
- 빠른 진입/진출이 핵심
- 스탑로스를 짧게 잡아 손실을 최소화
"""
from typing import Optional, Tuple
import pandas as pd
import numpy as np
from .strategy import Strategy, Signal
from .portfolio import Portfolio
from ..trading.indicators import TechnicalIndicators

# 상수 정의
DEFAULT_RISK_PER_TRADE = 0.02  # 거래당 리스크 2%
DEFAULT_MAX_POSITION_SIZE = 0.3  # 최대 포지션 30%
DEFAULT_DONCHIAN_PERIOD = 20  # Donchian Channel 기간
DEFAULT_VOLUME_MULTIPLIER = 1.5  # 거래량 배수
DEFAULT_K_VALUE = 0.5  # 래리 윌리엄스 K 값
DEFAULT_TIMEOUT_BARS = 24  # 타임아웃 바 수 (24봉)

# 포지션 사이징 상수
MIN_RISK_PCT = 0.015  # 최소 1.5% 리스크
MAX_RISK_PCT = 0.05   # 최대 5% 리스크
MIN_POSITION_SIZE = 0.05  # 최소 포지션 5%
FALLBACK_POSITION_SIZE = 0.1  # 기본 포지션 10%

# 매도 조건 상수
FAKEOUT_THRESHOLD_BARS = 3  # Fakeout 체크 기간 (3봉)
FAKEOUT_PRICE_DROP = 0.98  # Fakeout 가격 하락률 (2%)
ADX_WEAKENING_THRESHOLD = 0.8  # ADX 약화 임계값
ADX_WEAK_TREND = 20  # 약한 추세 ADX 기준값
PROFIT_THRESHOLD_FOR_TIMEOUT = 0.02  # 타임아웃 시 최소 수익률 (2%)

# 스탑로스/테이크프로핏 배수
STOP_LOSS_ATR_MULTIPLIER = 2.0  # 스탑로스 ATR 배수
TAKE_PROFIT_ATR_MULTIPLIER = 3.0  # 테이크프로핏 ATR 배수

# 추세 필터 상수
DEFAULT_TREND_MA_PERIOD = 50  # 기본 추세 필터 이동평균 기간 (50일)
MIN_TREND_MA_PERIOD = 20  # 최소 추세 필터 이동평균 기간
DEFAULT_USE_DYNAMIC_K = False  # 기본값: 고정 K 사용


class RuleBasedBreakoutStrategy(Strategy):
    """
    변동성 돌파 전략 - 4단계 관문 룰 기반 (최신 퀀트 트렌드 반영)

    최신 트렌드 반영:
    - Gate 0: 추세 필터 (Trend Filter) - 이동평균선 필터로 하락장 가짜 돌파(데드캣 바운스) 차단
    - Gate 1: 응축(Squeeze) 확인 - 볼린저 밴드 폭 축소 또는 ADX < 20
    - Gate 2: 돌파(Breakout) 발생 - 20일 고점 갱신 또는 래리 윌리엄스 방식
      * 동적 K값 지원: 노이즈 비율에 따라 K값 자동 조정 (use_dynamic_k=True)
    - Gate 3: 거래량(Volume) 확인 - 평균의 1.5배 이상 또는 OBV 정배열 확인

    주요 특징:
    - 하락장에서의 가짜 돌파 차단으로 승률 향상
    - 노이즈가 많은 장세에서 진입장벽 자동 조정
    - 5가지 매도 조건 (스탑로스, Fakeout, 타겟가, ADX, 타임아웃)

    성능 최적화:
    - prepare_indicators()로 지표 사전 계산 (O(N²) → O(N))
    - 캐싱된 지표 활용으로 백테스팅 속도 대폭 향상
    """

    def __init__(
        self,
        ticker: str,
        risk_per_trade: float = DEFAULT_RISK_PER_TRADE,
        max_position_size: float = DEFAULT_MAX_POSITION_SIZE,
        donchian_period: int = DEFAULT_DONCHIAN_PERIOD,
        volume_multiplier: float = DEFAULT_VOLUME_MULTIPLIER,
        k_value: float = DEFAULT_K_VALUE,
        timeout_bars: int = DEFAULT_TIMEOUT_BARS,
        trend_filter_enabled: bool = True,  # 추세 필터 사용 여부
        trend_ma_period: int = DEFAULT_TREND_MA_PERIOD,  # 추세 필터 이동평균 기간
        use_dynamic_k: bool = DEFAULT_USE_DYNAMIC_K  # 동적 K값 사용 여부
    ):
        self.ticker = ticker
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        self.donchian_period = donchian_period
        self.volume_multiplier = volume_multiplier
        self.k_value = k_value  # 고정 K값 (use_dynamic_k=False일 때 사용)
        self.timeout_bars = timeout_bars
        self.trend_filter_enabled = trend_filter_enabled
        self.trend_ma_period = max(trend_ma_period, MIN_TREND_MA_PERIOD)  # 최소값 보장
        self.use_dynamic_k = use_dynamic_k

        # 포지션 추적 (매도 신호 생성을 위해)
        self.current_position = None  # {'entry_price', 'stop_loss', 'take_profit', 'entry_bar_index'}

        # [최적화] 캐싱된 지표 저장소
        self._cached_indicators: Optional[pd.DataFrame] = None
        self._indicators_prepared = False

    def prepare_indicators(self, data: pd.DataFrame) -> None:
        """
        지표 사전 계산 (Vectorization) - O(N²) → O(N) 최적화

        백테스트 시작 전에 한 번만 호출되어 전체 데이터에 대해 지표를 계산합니다.

        Args:
            data: 전체 과거 데이터
        """
        # 원본 데이터 복사 (한 번만)
        df = data.copy()

        # 1. 볼린저 밴드 및 폭(Bandwidth) 계산
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['std20'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['ma20'] + (df['std20'] * 2)
        df['bb_lower'] = df['ma20'] - (df['std20'] * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['ma20'].replace(0, np.nan)

        # 2. 거래량 이동평균
        df['vol_ma20'] = df['volume'].rolling(window=20).mean()

        # 3. 추세 필터용 이동평균
        df['trend_ma'] = df['close'].rolling(window=self.trend_ma_period).mean()

        # 4. ATR 계산
        df['atr'] = TechnicalIndicators.calculate_atr(df, period=14)

        # 5. ADX 계산
        df['adx'] = TechnicalIndicators.calculate_adx(df, period=14)

        # 6. OBV 계산
        df['obv'] = TechnicalIndicators.calculate_obv(df)

        # 7. OBV 이동평균
        df['obv_ma5'] = df['obv'].rolling(window=5).mean()
        df['obv_ma20'] = df['obv'].rolling(window=20).mean()

        # 8. 볼린저 밴드 폭의 20일 이동평균 (Gate 1용)
        df['bb_width_ma20'] = df['bb_width'].rolling(window=20).mean()

        # 9. Donchian Channel 고점 (현재 봉 제외)
        df['donchian_high'] = df['high'].shift(1).rolling(window=self.donchian_period).max()

        # 10. 동적 K값용 노이즈 비율
        ranges = df['high'] - df['low']
        ranges = ranges.replace(0, np.nan)
        bodies = (df['open'] - df['close']).abs()
        noise_ratios = 1 - (bodies / ranges)
        df['noise_ratio_ma20'] = noise_ratios.rolling(window=20).mean()
        df['dynamic_k'] = df['noise_ratio_ma20'].clip(0.3, 0.7)

        # 캐시 저장
        self._cached_indicators = df
        self._indicators_prepared = True
    
    def generate_signal(self, data: pd.DataFrame, portfolio: Optional[Portfolio] = None) -> Optional[Signal]:
        """
        룰 기반 거래 신호 생성 (AI 호출 없음)

        Args:
            data: 현재 시점까지의 차트 데이터
            portfolio: 포트폴리오 객체 (옵션, 매도 신호 생성을 위해)

        Returns:
            Signal 객체 또는 None
        """
        # 최소 데이터 요구량 체크
        if len(data) < self.donchian_period + 5:
            return None

        current_bar_index = len(data) - 1

        # ---------------------------------------------------------
        # [최적화] 캐싱된 지표 사용 (O(N²) → O(N))
        # prepare_indicators()가 호출되었으면 캐시 사용, 아니면 기존 방식
        # ---------------------------------------------------------
        if self._indicators_prepared and self._cached_indicators is not None:
            # 캐싱된 지표에서 현재 시점 데이터 추출 (인덱싱만 수행 - O(1))
            current_row = self._cached_indicators.iloc[current_bar_index]
            current_price = current_row['close']
            current_volume = current_row['volume']

            # 캐싱된 지표 참조용 df
            df = self._cached_indicators.iloc[:current_bar_index + 1]
        else:
            # 캐시 없음: 기존 방식 (매번 계산 - 느림)
            df = data.copy()

            # 1. 볼린저 밴드 및 폭(Bandwidth) 계산
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['std20'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['ma20'] + (df['std20'] * 2)
            df['bb_lower'] = df['ma20'] - (df['std20'] * 2)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['ma20'].replace(0, np.nan)

            # 2. 거래량 이동평균
            df['vol_ma20'] = df['volume'].rolling(window=20).mean()

            current_price = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
        
        # ===================================================
        # 1. 포지션 추적 정보 업데이트 (Source of Truth: Portfolio)
        # ===================================================
        has_position = portfolio and self.ticker in portfolio.positions
        
        if has_position:
            position = portfolio.positions[self.ticker]
            
            # 포지션 정보 초기화 또는 업데이트 (Source of Truth는 Portfolio)
            if not self.current_position:
                # 새로운 포지션 진입 (백테스터가 매수 주문 실행함)
                # Signal에서 설정한 stop_loss, take_profit 사용
                self.current_position = {
                    'entry_price': position.entry_price,
                    'stop_loss': getattr(position, 'stop_loss', position.entry_price * 0.98),
                    'take_profit': getattr(position, 'take_profit', position.entry_price * 1.03),
                    'entry_bar_index': current_bar_index
                }
            # else: 포지션 유지 중 - 추가 업데이트 불필요 (Source of Truth는 Portfolio)
        else:
            # 포지션 없음 - 추적 정보 초기화
            if self.current_position:
                self.current_position = None
        
        # ===================================================
        # 2. 포지션이 있을 때: 매도 신호 체크 (우선순위 순)
        # ===================================================
        if has_position and self.current_position:  # 두 조건 모두 확인
            entry_price = self.current_position.get('entry_price', current_price)
            entry_bar_index = self.current_position.get('entry_bar_index')
            
            # entry_bar_index가 None이 아닐 때만 hold_bars 계산
            if entry_bar_index is not None:
                hold_bars = current_bar_index - entry_bar_index
            else:
                hold_bars = 0  # 진입 시점 모름
            
            # ATR 가져오기 (캐싱된 값 우선 사용)
            if self._indicators_prepared and self._cached_indicators is not None:
                atr = self._cached_indicators.iloc[current_bar_index].get('atr', current_price * 0.02)
            else:
                indicators = TechnicalIndicators.get_latest_indicators(data)
                atr = indicators.get('atr', current_price * 0.02)  # fallback 2%
            
            # ---------------------------------------------------
            # 매도 조건 1: 스탑로스 체크 (손실 보호 최우선)
            # ---------------------------------------------------
            stop_loss = self.current_position.get('stop_loss')
            if stop_loss and current_price <= stop_loss:
                self.current_position = None
                return Signal(
                    action='sell',
                    price=current_price,
                    reason={'type': 'stop_loss', 'msg': f'손절 실행 ({current_price:.0f} <= {stop_loss:.0f})'}
                )
            
            # ---------------------------------------------------
            # 매도 조건 2: Fakeout 감지 (진입 직후 초기 탈출)
            # ---------------------------------------------------
            # Fakeout은 진입 후 초반 N봉 이내에 진입가보다 하락할 때만 체크
            if hold_bars <= FAKEOUT_THRESHOLD_BARS:
                # 진입가보다 2% 이상 하락하면 즉시 손절 (칼손절)
                # ATR 기반으로도 체크 가능하지만, 초기에는 고정 2%가 더 안전
                fakeout_threshold = entry_price * FAKEOUT_PRICE_DROP
                
                if current_price < fakeout_threshold:
                    self.current_position = None
                    return Signal(
                        action='sell',
                        price=current_price,
                        reason={'type': 'fakeout', 'msg': f'진입 직후 급락 (Fakeout, {current_price:.0f} < {fakeout_threshold:.0f})'}
                    )
            
            # ---------------------------------------------------
            # 매도 조건 3: 타겟가 체크 (이익 실현)
            # ---------------------------------------------------
            take_profit = self.current_position.get('take_profit')
            if take_profit and current_price >= take_profit:
                self.current_position = None
                return Signal(
                    action='sell',
                    price=current_price,
                    reason={'type': 'take_profit', 'msg': f'익절 실행 ({current_price:.0f} >= {take_profit:.0f})'}
                )
            
            # ---------------------------------------------------
            # 매도 조건 4: 추세 반전 체크 (ADX)
            # ---------------------------------------------------
            # ADX 가져오기 (캐싱된 값 우선 사용)
            if self._indicators_prepared and self._cached_indicators is not None and current_bar_index >= 1:
                current_adx = self._cached_indicators.iloc[current_bar_index].get('adx', 25)
                prev_adx = self._cached_indicators.iloc[current_bar_index - 1].get('adx', 25)

                # ADX 급격히 하락 = 추세 약화
                if not pd.isna(current_adx) and not pd.isna(prev_adx):
                    if current_adx < prev_adx * ADX_WEAKENING_THRESHOLD and current_adx < ADX_WEAK_TREND:
                        self.current_position = None
                        return Signal(
                            action='sell',
                            price=current_price,
                            reason={'type': 'trend_weakening', 'msg': f'ADX 하락 (추세 약화: {current_adx:.1f})'}
                        )
            else:
                # 캐시 없는 경우 기존 방식
                adx = TechnicalIndicators.calculate_adx(df)
                if not adx.empty and len(adx) >= 2:
                    current_adx = adx.iloc[-1]
                    prev_adx = adx.iloc[-2]

                    # ADX 급격히 하락 = 추세 약화
                    if current_adx < prev_adx * ADX_WEAKENING_THRESHOLD and current_adx < ADX_WEAK_TREND:
                        self.current_position = None
                        return Signal(
                            action='sell',
                            price=current_price,
                            reason={'type': 'trend_weakening', 'msg': f'ADX 하락 (추세 약화: {current_adx:.1f})'}
                        )
            
            # ---------------------------------------------------
            # 매도 조건 5: 타임아웃 체크 (모멘텀 부족)
            # ---------------------------------------------------
            profit_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0
            
            if hold_bars > self.timeout_bars:
                if profit_pct < PROFIT_THRESHOLD_FOR_TIMEOUT:  # 2% 미만 수익
                    self.current_position = None
                    return Signal(
                        action='sell',
                        price=current_price,
                        reason={'type': 'timeout', 'msg': f'타임아웃 (모멘텀 부족, {hold_bars}봉 경과, 수익: {profit_pct*100:.2f}%)'}
                    )
        
        # ===================================================
        # 3. 포지션이 없을 때: 매수 신호 체크
        # ===================================================
        if not has_position:  # 포지션 없을 때만 매수 검토
            # ---------------------------------------------------
            # Gate 0: 추세 필터 (Trend Filter) - 하락장 돌파 차단
            # ---------------------------------------------------
            if self.trend_filter_enabled:
                trend_passed = self._check_trend_filter(df, current_price)
                if not trend_passed:
                    # 추세 필터 실패 시 매수 신호 생성 안 함
                    return None
            
            # 3단계 관문 체크 실행
            gate1_passed, gate1_reason = self._check_gate1_squeeze(df)
            
            # Gate 2: 동적 K값 사용 여부에 따라 다른 K값 전달
            if self.use_dynamic_k:
                dynamic_k = self._get_dynamic_k(df)
                gate2_passed, gate2_reason = self._check_gate2_breakout(df, current_price, k_value=dynamic_k)
            else:
                gate2_passed, gate2_reason = self._check_gate2_breakout(df, current_price, k_value=self.k_value)
            
            gate3_passed, gate3_reason = self._check_gate3_volume(df, current_volume)
            
            # 모든 관문 통과 시 (AND 조건)
            if gate1_passed and gate2_passed and gate3_passed:
                # ATR 가져오기 (캐싱된 값 우선 사용)
                if self._indicators_prepared and self._cached_indicators is not None:
                    atr = self._cached_indicators.iloc[current_bar_index].get('atr', current_price * 0.02)
                else:
                    indicators = TechnicalIndicators.get_latest_indicators(data)
                    atr = indicators.get('atr', current_price * 0.02)  # fallback 2%

                # 전략적 스탑로스/테이크프로핏 설정
                # 돌파 매매는 손절을 짧게 잡는 것이 핵심 (돌파 실패 = 즉시 탈출)
                stop_loss = current_price - (STOP_LOSS_ATR_MULTIPLIER * atr)
                take_profit = current_price + (TAKE_PROFIT_ATR_MULTIPLIER * atr)  # 손익비 1:1.5
                
                # 포지션 정보 저장
                self.current_position = {
                    'entry_price': current_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'entry_bar_index': current_bar_index
                }
                
                reason = {
                    'strategy': 'volatility_breakout',
                    'gate0': f'추세 필터 통과 (MA{self.trend_ma_period} 위)' if self.trend_filter_enabled else '추세 필터 비활성화',
                    'gate1': gate1_reason,
                    'gate2': gate2_reason,
                    'gate3': gate3_reason,
                    'score': 'pass'
                }
                
                return Signal(
                    action='buy',
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=reason
                )
        
        return None
    
    def _check_trend_filter(self, df: pd.DataFrame, current_price: float) -> bool:
        """
        [Gate 0] 추세 필터 (Trend Filter)
        최신 퀀트 트렌드: 하락장에서의 가짜 돌파(데드캣 바운스) 차단

        현재 가격이 이동평균선 위에 있을 때만 상승 추세로 간주하여 진입 허용

        Args:
            df: 차트 데이터
            current_price: 현재가

        Returns:
            True: 상승 추세 (진입 허용)
            False: 하락 추세 (진입 차단)
        """
        if len(df) < self.trend_ma_period:
            # 데이터 부족 시 패스 (기존 동작 유지)
            return True

        # [최적화] 캐싱된 지표 사용
        if self._indicators_prepared and self._cached_indicators is not None:
            ma = df.iloc[-1].get('trend_ma', None)
            if ma is not None and not pd.isna(ma):
                return current_price > ma
            return True  # NaN인 경우 패스

        # 기존 방식: 이동평균선 계산
        ma = df['close'].rolling(window=self.trend_ma_period).mean().iloc[-1]

        # 현재 가격이 이동평균선 위에 있어야 상승 추세
        if current_price > ma:
            return True

        # 하락 추세: 진입 차단
        return False
    
    def _get_dynamic_k(self, df: pd.DataFrame) -> float:
        """
        노이즈 비율을 반영한 동적 K값 계산
        최신 이론: Noise Ratio = 1 - |Open - Close| / (High - Low)

        노이즈가 많으면(꼬리 긴 캔들) K값을 높여서 진입장벽을 높임
        추세가 깔끔하면(몸통 긴 캔들) K값을 낮춰서 빠르게 진입

        Args:
            df: 차트 데이터

        Returns:
            동적 K값 (0.3 ~ 0.7 범위로 클램핑)
        """
        if len(df) < 20:
            # 데이터 부족 시 기본값 반환
            return self.k_value

        # [최적화] 캐싱된 지표 사용
        if self._indicators_prepared and self._cached_indicators is not None:
            dynamic_k = df.iloc[-1].get('dynamic_k', None)
            if dynamic_k is not None and not pd.isna(dynamic_k):
                return dynamic_k
            return self.k_value  # NaN인 경우 기본값

        # 기존 방식: 캔들 범위 (High - Low)
        ranges = df['high'] - df['low']
        ranges = ranges.replace(0, np.nan)  # 0으로 나누기 방지

        # 몸통 길이 (|Open - Close|)
        bodies = (df['open'] - df['close']).abs()

        # 노이즈 비율 계산
        # 0에 가까우면: 몸통이 긴 깔끔한 캔들 (추세 명확)
        # 1에 가까우면: 꼬리가 긴 십자형 캔들 (노이즈 많음)
        noise_ratios = 1 - (bodies / ranges)

        # 최근 20일 평균 노이즈 비율
        avg_noise = noise_ratios.rolling(window=20).mean().iloc[-1]

        # NaN 체크
        if pd.isna(avg_noise):
            return self.k_value

        # K값 보정: 노이즈 비율 자체를 K로 사용하되, 0.3 ~ 0.7 범위로 클램핑
        # 노이즈가 많으면(avg_noise 높음) K값을 높여서 확실한 돌파만 진입
        # 노이즈가 적으면(avg_noise 낮음) K값을 낮춰서 빠른 진입
        dynamic_k = max(0.3, min(avg_noise, 0.7))

        return dynamic_k
    
    def _check_gate1_squeeze(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        [관문 1 수정] 응축 확인 (강화된 기준)
        논리 수정: '현재'가 아니라 '돌파 직전(1~3봉 전)'에 응축이 있었는가?

        문제점: 돌파가 일어나는 순간은 가격이 급변하므로 볼린저 밴드가 벌어지는(확장) 순간입니다.
        따라서 현재 캔들에서 응축과 돌파를 동시에 체크하는 것은 논리적으로 불가능합니다.
        """
        if len(df) < 20:
            return False, "데이터 부족"

        # [최적화] 캐싱된 지표 사용
        if self._indicators_prepared and self._cached_indicators is not None:
            # 캐싱된 bb_width_ma20 사용
            avg_width = df.iloc[-1].get('bb_width_ma20', None)
            if avg_width is None or pd.isna(avg_width):
                avg_width = df['bb_width'].iloc[-20:].mean() if len(df) >= 20 else df['bb_width'].mean()

            # 최근 10일 최소값
            if len(df) >= 10:
                recent_min_width = df['bb_width'].iloc[-10:].min()
                if not pd.isna(recent_min_width) and recent_min_width < avg_width * 0.8:
                    return True, f"강한 응축 확인 (최소 폭: {recent_min_width:.4f} < 평균의 80%)"

            # 직전 캔들 폭 확인
            if len(df) >= 3:
                prev_width = df['bb_width'].iloc[-2]
                prev_prev_width = df['bb_width'].iloc[-3]

                is_squeezed = (not pd.isna(prev_width) and prev_width < avg_width) or \
                              (not pd.isna(prev_prev_width) and prev_prev_width < avg_width)

                if is_squeezed:
                    return True, f"직전 응축 확인 (폭: {prev_width:.4f} < 평균: {avg_width:.4f})"

            # 캐싱된 ADX 사용
            if len(df) >= 2:
                prev_adx = df['adx'].iloc[-2] if 'adx' in df.columns else None
                if prev_adx is not None and not pd.isna(prev_adx) and prev_adx < 25:
                    return True, f"ADX 횡보 확인 ({prev_adx:.1f} < 25)"

            return False, "응축 없음 (이미 변동성 확대 상태)"

        # 기존 방식 (캐시 없는 경우)
        # 최근 20일 평균 밴드폭
        avg_width = df['bb_width'].rolling(window=20).mean().iloc[-1]

        # 더 엄격한 응축 기준: 최근 10일 중 가장 좁은 폭 체크
        if len(df) >= 10:
            recent_min_width = df['bb_width'].tail(10).min()

            # 평균의 80% 이하 = 강한 응축
            if recent_min_width < avg_width * 0.8:
                return True, f"강한 응축 확인 (최소 폭: {recent_min_width:.4f} < 평균의 80%)"

        # 직전 캔들(iloc[-2]) 또는 그 전(iloc[-3])의 밴드폭 확인
        # 이유: 돌파 캔들(iloc[-1])에서는 이미 밴드가 벌어졌을 수 있음
        if len(df) >= 3:
            prev_width = df['bb_width'].iloc[-2]
            prev_prev_width = df['bb_width'].iloc[-3]

            is_squeezed = (prev_width < avg_width) or (prev_prev_width < avg_width)

            if is_squeezed:
                return True, f"직전 응축 확인 (폭: {prev_width:.4f} < 평균: {avg_width:.4f})"

        # 보조 지표: ADX (추세 강도가 약했을 때 = 횡보)
        # 원본 데이터를 사용하여 ADX 계산
        adx = TechnicalIndicators.calculate_adx(df)
        if not adx.empty and len(adx) >= 2:
            prev_adx = adx.iloc[-2]  # 직전 ADX
            if prev_adx < 25:
                return True, f"ADX 횡보 확인 ({prev_adx:.1f} < 25)"

        return False, "응축 없음 (이미 변동성 확대 상태)"
    
    def _calculate_atr_based_breakout(
        self,
        df: pd.DataFrame,
        current_idx: int
    ) -> Optional[float]:
        """
        ATR 기반 동적 돌파가 계산

        공식: 돌파가 = 전일_종가 + ATR(14) × K
        - 저변동성 (ATR < 2%): K = 2.0
        - 중변동성 (2% ≤ ATR < 4%): K = 1.5
        - 고변동성 (ATR ≥ 4%): K = 1.0

        Args:
            df: 차트 데이터
            current_idx: 현재 인덱스

        Returns:
            ATR 기반 돌파가 (데이터 부족 시 None)
        """
        if current_idx < 14:  # ATR 계산 최소 기간
            return None

        # ATR 계산
        atr_series = TechnicalIndicators.calculate_atr(df.iloc[:current_idx], period=14)
        if atr_series.empty or len(atr_series) == 0:
            return None

        current_atr = atr_series.iloc[-1]
        yesterday_close = df.iloc[current_idx - 1]['close']

        if yesterday_close <= 0:
            return None

        # ATR 비율 계산
        atr_pct = (current_atr / yesterday_close) * 100

        # 동적 K값 결정
        if atr_pct < 2.0:
            k_value = 2.0  # 저변동성: 큰 돌파 필요
        elif atr_pct < 4.0:
            k_value = 1.5  # 중변동성
        else:
            k_value = 1.0  # 고변동성: 작은 돌파로도 진입

        # 돌파가 계산
        target_price = yesterday_close + current_atr * k_value

        return target_price

    def _check_gate2_breakout(self, df: pd.DataFrame, current_price: float, k_value: Optional[float] = None) -> Tuple[bool, str]:
        """
        [관문 2 수정] 돌파 확인 (강도 측정 추가 + 동적 K값 지원)
        논리 수정: Look-ahead Bias 제거 (현재 캔들 제외한 과거 고점 비교)

        문제점: tail(20)에는 현재 형성 중인 캔들의 고점도 포함될 수 있습니다.
        현재가가 현재 고점과 같으므로 > 조건이 성립하지 않거나,
        이미 지나간 고점을 보고 들어가는 오류가 생길 수 있습니다.

        Args:
            df: 차트 데이터
            current_price: 현재가
            k_value: 래리 윌리엄스 K값 (None이면 self.k_value 사용)
        """
        if k_value is None:
            k_value = self.k_value

        if len(df) < self.donchian_period + 1:
            return False, "데이터 부족"

        # [최적화] 캐싱된 Donchian 고점 사용
        if self._indicators_prepared and self._cached_indicators is not None and 'donchian_high' in df.columns:
            highest_high = df.iloc[-1].get('donchian_high', None)
            if highest_high is not None and not pd.isna(highest_high):
                if current_price > highest_high:
                    # 돌파 강도 측정
                    breakout_strength = (current_price - highest_high) / highest_high

                    if breakout_strength > 0.01:
                        return True, f"강한 돌파 ({breakout_strength*100:.2f}% 상승, {current_price:.0f} > {highest_high:.0f})"
                    else:
                        return True, f"약한 돌파 (주의 필요, {breakout_strength*100:.2f}% 상승)"

        else:
            # 기존 방식: Donchian Channel (최근 20일 고점, 오늘 제외!)
            past_highs = df['high'].iloc[-(self.donchian_period + 1):-1]
            highest_high = past_highs.max()

            if current_price > highest_high:
                # 돌파 강도 측정 (얼마나 세게 뚫었는가?)
                breakout_strength = (current_price - highest_high) / highest_high

                if breakout_strength > 0.01:  # 1% 이상 강하게 돌파
                    return True, f"강한 돌파 ({breakout_strength*100:.2f}% 상승, {current_price:.0f} > {highest_high:.0f})"
                else:
                    return True, f"약한 돌파 (주의 필요, {breakout_strength*100:.2f}% 상승)"

        # 2. Larry Williams Volatility Breakout (동적/고정 K값 사용)
        if len(df) >= 2:
            prev_close = df['close'].iloc[-2]
            prev_high = df['high'].iloc[-2]
            prev_low = df['low'].iloc[-2]
            prev_range = prev_high - prev_low

            breakout_level = prev_close + (prev_range * k_value)

            if current_price > breakout_level:
                k_type = "동적" if self.use_dynamic_k else "고정"
                return True, f"변동성 돌파 성공 (K={k_value:.2f}, {k_type}, {current_price:.0f} > {breakout_level:.0f})"

        return False, "돌파 실패"
    
    def _check_gate3_volume(self, df: pd.DataFrame, current_volume: float) -> Tuple[bool, str]:
        """
        [관문 3] 거래량 확인 (OBV 로직 수정)
        엄밀하게 하려면 어제까지의 평균과 비교

        OBV는 누적 지표이므로 현재값 > 평균값 비교는 의미가 없습니다.
        OBV의 추세(기울기)를 확인해야 합니다.
        """
        if len(df) < 21:
            return False, "데이터 부족"

        # 어제까지의 평균 거래량 (현재 캔들 제외)
        avg_vol_prev = df['volume'].iloc[-21:-1].mean()

        if current_volume > avg_vol_prev * self.volume_multiplier:
            return True, f"거래량 폭발 ({current_volume:.0f} > {avg_vol_prev:.0f} * {self.volume_multiplier})"

        # [최적화] 캐싱된 OBV 지표 사용
        if self._indicators_prepared and self._cached_indicators is not None and 'obv' in df.columns:
            current_obv = df['obv'].iloc[-1]
            obv_ma5 = df['obv_ma5'].iloc[-1] if 'obv_ma5' in df.columns else None
            obv_ma20 = df['obv_ma20'].iloc[-1] if 'obv_ma20' in df.columns else None

            # OBV가 이동평균선 위에 있고 + 골든크로스
            if obv_ma5 is not None and obv_ma20 is not None:
                if not pd.isna(current_obv) and not pd.isna(obv_ma5) and not pd.isna(obv_ma20):
                    if current_obv > obv_ma20 and obv_ma5 > obv_ma20:
                        return True, f"OBV 정배열 및 골든크로스 (매수세 유입, OBV: {current_obv:,.0f} > MA20: {obv_ma20:,.0f})"

                    # OBV 기울기 체크
                    if len(df) >= 6:
                        obv_slope = df['obv'].iloc[-1] - df['obv'].iloc[-6]
                        if current_obv > obv_ma20 and obv_slope > 0:
                            return True, f"OBV 정배열 및 상승 추세 (매집 확인, 변화량: {obv_slope:,.0f})"

            # 가격-OBV 다이버전스 체크
            if len(df) >= 5:
                price_trend = df['close'].iloc[-5:].diff().sum()
                obv_trend = df['obv'].iloc[-5:].diff().sum()

                if price_trend > 0 and obv_trend > 0:
                    return True, f"가격-OBV 동반 상승 (건강한 추세)"
                elif price_trend > 0 and obv_trend < 0:
                    return False, "가격-OBV 다이버전스 (약한 상승, 위험)"

            return False, "거래량 부족"

        # 기존 방식 (캐시 없는 경우)
        obv = TechnicalIndicators.calculate_obv(df)
        if not obv.empty and len(obv) >= 20:
            # 방법 1: OBV 이동평균 크로스 (추천: 가장 신뢰성 높음)
            obv_short = obv.rolling(5).mean().iloc[-1]
            obv_long = obv.rolling(20).mean().iloc[-1]
            current_obv = obv.iloc[-1]

            # OBV가 이동평균선 위에 있고 + 골든크로스
            if current_obv > obv_long and obv_short > obv_long:
                return True, f"OBV 정배열 및 골든크로스 (매수세 유입, OBV: {current_obv:,.0f} > MA20: {obv_long:,.0f})"

        # 방법 2: OBV 기울기 (강화: 이동평균선 위에서 상승 추세)
        if not obv.empty and len(obv) >= 20:
            obv_ma20 = obv.rolling(20).mean().iloc[-1]
            current_obv = obv.iloc[-1]
            obv_slope = obv.iloc[-1] - obv.iloc[-6]  # 최근 5일 변화량

            # OBV가 이동평균선 위에 있고 + 기울기 양수
            if current_obv > obv_ma20 and obv_slope > 0:
                return True, f"OBV 정배열 및 상승 추세 (매집 확인, 변화량: {obv_slope:,.0f})"

        # 방법 3: OBV와 가격 다이버전스 체크 (고급)
        if not obv.empty and len(obv) >= 5 and len(df) >= 5:
            price_trend = df['close'].iloc[-5:].diff().sum()
            obv_trend = obv.iloc[-5:].diff().sum()

            if price_trend > 0 and obv_trend > 0:
                # 가격 상승 + OBV 상승 = 건강한 상승
                return True, f"가격-OBV 동반 상승 (건강한 추세)"
            elif price_trend > 0 and obv_trend < 0:
                # 가격 상승 but OBV 하락 = 약한 상승 (위험)
                return False, "가격-OBV 다이버전스 (약한 상승, 위험)"

        return False, "거래량 부족"
    
    def calculate_position_size(
        self, 
        signal: Signal, 
        portfolio: Portfolio
    ) -> float:
        """
        포지션 크기 계산 (리스크 기반 + 안전장치)
        
        안전장치:
        - 최소/최대 리스크 비율 제한
        - 최소/최대 포지션 크기 제한
        
        Args:
            signal: 거래 신호
            portfolio: 포트폴리오 객체
            
        Returns:
            계산된 포지션 크기 (코인 수량)
        """
        
        if signal.stop_loss and signal.stop_loss > 0:
            # 리스크 계산
            price_risk = signal.price - signal.stop_loss
            risk_pct = price_risk / signal.price if signal.price > 0 else 0
            
            # 리스크가 너무 작으면 스탑로스 재조정
            if risk_pct < MIN_RISK_PCT:
                signal.stop_loss = signal.price * (1 - MIN_RISK_PCT)
                price_risk = signal.price * MIN_RISK_PCT
                risk_pct = MIN_RISK_PCT
            
            # 리스크가 너무 크면 포지션 축소
            if risk_pct > MAX_RISK_PCT:
                price_risk = signal.price * MAX_RISK_PCT
                risk_pct = MAX_RISK_PCT
            
            # 포지션 크기 계산
            risk_amount = portfolio.equity * self.risk_per_trade
            position_size = risk_amount / price_risk if price_risk > 0 else 0
            
            # 최대 포지션 제한 (30%)
            max_size = (portfolio.equity * self.max_position_size) / signal.price
            position_size = min(position_size, max_size)
            
            # 최소 포지션 제한 (너무 작으면 의미 없음)
            min_size = (portfolio.equity * MIN_POSITION_SIZE) / signal.price
            position_size = max(position_size, min_size)
            
            return position_size
        
        # Fallback: 포트폴리오의 기본 비율
        return (portfolio.equity * FALLBACK_POSITION_SIZE) / signal.price
    
    def calculate_slippage(
        self,
        order_type: str,
        expected_price: float,
        order_size: float,
        orderbook: dict
    ) -> dict:
        """
        오더북 기반 슬리피지 계산
        
        슬리피지는 예상 가격과 실제 체결 가격의 차이입니다.
        큰 주문일수록 오더북의 여러 호가를 소진하면서 불리한 가격에 체결됩니다.
        
        Args:
            order_type: 'buy' 또는 'sell'
            expected_price: 예상 가격 (현재가)
            order_size: 주문 수량
            orderbook: 오더북 정보 {'ask_prices': [...], 'ask_volumes': [...]} 또는
                                  {'bid_prices': [...], 'bid_volumes': [...]}
        
        Returns:
            {
                'actual_avg_price': 실제 평균 체결가,
                'slippage_amount': 슬리피지 금액 (절대값),
                'slippage_pct': 슬리피지 비율 (%),
                'warning': 경고 메시지 (허용치 초과 시)
            }
        """
        if order_type == 'buy':
            prices = orderbook.get('ask_prices', [])
            volumes = orderbook.get('ask_volumes', [])
        else:  # sell
            prices = orderbook.get('bid_prices', [])
            volumes = orderbook.get('bid_volumes', [])
        
        if not prices or not volumes:
            # 오더북 정보 없으면 기본 슬리피지 가정 (0.1%)
            slippage_pct = 0.001
            actual_avg_price = expected_price * (1 + slippage_pct) if order_type == 'buy' else expected_price * (1 - slippage_pct)
            return {
                'actual_avg_price': actual_avg_price,
                'slippage_amount': abs(actual_avg_price - expected_price) * order_size,
                'slippage_pct': slippage_pct,
                'warning': '오더북 정보 없음 - 기본 슬리피지 0.1% 가정'
            }
        
        # 오더북 호가를 순회하며 체결 시뮬레이션
        remaining_size = order_size
        total_cost = 0.0
        filled_size = 0.0
        
        for price, volume in zip(prices, volumes):
            if remaining_size <= 0:
                break
            
            # 이 호가에서 체결 가능한 수량
            fill_size = min(remaining_size, volume)
            total_cost += fill_size * price
            filled_size += fill_size
            remaining_size -= fill_size
        
        # 남은 수량이 있으면 마지막 가격으로 체결 (최악의 시나리오)
        if remaining_size > 0 and prices:
            total_cost += remaining_size * prices[-1]
            filled_size += remaining_size
        
        # 평균 체결가 계산
        actual_avg_price = total_cost / filled_size if filled_size > 0 else expected_price
        
        # 슬리피지 계산
        slippage_amount = abs(actual_avg_price - expected_price)
        slippage_pct = slippage_amount / expected_price if expected_price > 0 else 0
        
        result = {
            'actual_avg_price': actual_avg_price,
            'slippage_amount': slippage_amount * order_size,
            'slippage_pct': slippage_pct
        }
        
        # 슬리피지 허용치 체크 (1% 기준)
        if slippage_pct > 0.01:
            result['warning'] = f'슬리피지 허용치 초과: {slippage_pct*100:.2f}% (기준: 1%)'
        
        return result
    
    def split_order(
        self,
        total_size: float,
        num_splits: int,
        min_chunk_size: float = 0.0
    ) -> list:
        """
        주문을 여러 개로 분할
        
        큰 주문을 여러 작은 주문으로 나누면:
        - 시장 영향(market impact) 감소
        - 슬리피지 감소
        - 더 나은 평균 진입가 확보
        
        Args:
            total_size: 전체 주문 수량
            num_splits: 분할 개수
            min_chunk_size: 최소 분할 크기 (기본값: 0)
        
        Returns:
            분할된 주문 리스트 [{'size': ..., 'order_num': ...}, ...]
        """
        # 최소 크기 제약이 있으면 최대 분할 개수 조정
        if min_chunk_size > 0:
            max_possible_splits = int(total_size / min_chunk_size)
            num_splits = min(num_splits, max_possible_splits)
        
        # 최소 1개로 분할
        num_splits = max(1, num_splits)
        
        # 균등 분할
        chunk_size = total_size / num_splits
        
        split_orders = []
        for i in range(num_splits):
            split_orders.append({
                'size': chunk_size,
                'order_num': i + 1
            })
        
        return split_orders
    
    def calculate_optimal_splits(
        self,
        order_size: float,
        orderbook: dict,
        order_type: str
    ) -> int:
        """
        오더북 유동성 기반 최적 분할 개수 계산
        
        오더북의 호가별 물량을 분석하여 슬리피지를 최소화하는
        최적 분할 개수를 결정합니다.
        
        Args:
            order_size: 주문 수량
            orderbook: 오더북 정보
            order_type: 'buy' 또는 'sell'
        
        Returns:
            최적 분할 개수 (1 이상)
        """
        if order_type == 'buy':
            volumes = orderbook.get('ask_volumes', [])
        else:
            volumes = orderbook.get('bid_volumes', [])
        
        if not volumes:
            return 1
        
        # 상위 5개 호가의 평균 물량
        top_volumes = volumes[:5]
        avg_volume = sum(top_volumes) / len(top_volumes) if top_volumes else order_size
        
        # 주문량이 평균 호가 물량보다 크면 분할 권장
        if order_size > avg_volume:
            # 주문량을 평균 물량으로 나눈 값 (최소 2개, 최대 10개)
            optimal_splits = int(order_size / avg_volume)
            optimal_splits = max(2, min(optimal_splits, 10))
            return optimal_splits
        
        return 1
    
    def simulate_split_order_execution(
        self,
        total_size: float,
        num_splits: int,
        orderbook: dict,
        order_type: str
    ) -> dict:
        """
        분할 주문 실행 시뮬레이션
        
        Args:
            total_size: 전체 주문 수량
            num_splits: 분할 개수
            orderbook: 오더북 정보
            order_type: 'buy' 또는 'sell'
        
        Returns:
            {
                'filled_orders': 체결된 분할 주문 리스트,
                'avg_execution_price': 평균 체결가,
                'total_slippage': 전체 슬리피지 비율
            }
        """
        split_orders = self.split_order(total_size, num_splits)
        
        filled_orders = []
        total_cost = 0.0
        total_filled = 0.0
        
        # 첫 번째 주문의 예상 가격 (슬리피지 계산용)
        if order_type == 'buy':
            expected_price = orderbook.get('ask_prices', [100000])[0]
        else:
            expected_price = orderbook.get('bid_prices', [100000])[0]
        
        for order in split_orders:
            # 각 분할 주문의 슬리피지 계산
            slippage_info = self.calculate_slippage(
                order_type=order_type,
                expected_price=expected_price,
                order_size=order['size'],
                orderbook=orderbook
            )
            
            filled_orders.append({
                'order_num': order['order_num'],
                'filled_size': order['size'],
                'avg_price': slippage_info['actual_avg_price'],
                'slippage_pct': slippage_info['slippage_pct']
            })
            
            total_cost += order['size'] * slippage_info['actual_avg_price']
            total_filled += order['size']
        
        avg_execution_price = total_cost / total_filled if total_filled > 0 else expected_price
        total_slippage = abs(avg_execution_price - expected_price) / expected_price if expected_price > 0 else 0
        
        return {
            'filled_orders': filled_orders,
            'avg_execution_price': avg_execution_price,
            'total_slippage': total_slippage
        }
    
    def calculate_position_size_with_slippage(
        self,
        signal: Signal,
        portfolio: Portfolio,
        expected_slippage_pct: float = 0.005
    ) -> float:
        """
        슬리피지를 고려한 포지션 크기 계산
        
        슬리피지로 인해 실제 진입가가 예상보다 높아지므로
        동일한 리스크 금액을 유지하기 위해 포지션 크기를 조정합니다.
        
        Args:
            signal: 거래 신호
            portfolio: 포트폴리오 객체
            expected_slippage_pct: 예상 슬리피지 비율 (기본 0.5%)
        
        Returns:
            슬리피지를 고려한 포지션 크기
        """
        # 기본 포지션 크기 계산
        base_position_size = self.calculate_position_size(signal, portfolio)
        
        # 슬리피지를 고려한 실제 진입가
        adjusted_entry_price = signal.price * (1 + expected_slippage_pct)
        
        # 동일 리스크 금액 유지를 위한 포지션 크기 조정
        if signal.stop_loss and signal.stop_loss > 0:
            risk_amount = portfolio.equity * self.risk_per_trade
            adjusted_price_risk = adjusted_entry_price - signal.stop_loss
            
            if adjusted_price_risk > 0:
                adjusted_position_size = risk_amount / adjusted_price_risk
                
                # 최대/최소 포지션 제한 적용
                max_size = (portfolio.equity * self.max_position_size) / adjusted_entry_price
                min_size = (portfolio.equity * MIN_POSITION_SIZE) / adjusted_entry_price
                
                adjusted_position_size = min(adjusted_position_size, max_size)
                adjusted_position_size = max(adjusted_position_size, min_size)
                
                return adjusted_position_size
        
        # Fallback: 슬리피지 비율만큼 포지션 크기 감소
        return base_position_size * (1 - expected_slippage_pct)

    # ============================================
    # 테스트용 Wrapper 메서드
    # ============================================

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        ATR 계산 (테스트용 wrapper)

        Args:
            data: OHLCV 데이터
            period: ATR 기간 (기본 14)

        Returns:
            ATR 시리즈
        """
        return TechnicalIndicators.calculate_atr(data, period=period)

    def _get_dynamic_k_value(self, atr_pct: float) -> float:
        """
        ATR 비율 기반 동적 K값 계산 (테스트용 wrapper)

        Args:
            atr_pct: ATR 비율 (%)

        Returns:
            K값 (2.0, 1.5, 1.0)
        """
        if atr_pct < 2.0:
            return 2.0  # 저변동성
        elif atr_pct < 4.0:
            return 1.5  # 중변동성
        else:
            return 1.0  # 고변동성

    def _calculate_target_price_atr(self, data: pd.DataFrame, current_idx: int) -> float:
        """
        ATR 기반 돌파가 계산 (테스트용 wrapper)

        Args:
            data: OHLCV 데이터
            current_idx: 현재 인덱스

        Returns:
            돌파가 (데이터 부족 시 기존 방식으로 fallback)
        """
        # ATR 기반 돌파가 시도
        atr_target = self._calculate_atr_based_breakout(data, current_idx)

        if atr_target is not None:
            return atr_target

        # Fallback: 기존 래리 윌리엄스 방식
        if current_idx < 2:
            # 데이터 부족 시 현재가 반환
            return data.iloc[current_idx]['open']

        yesterday_high = data.iloc[current_idx - 1]['high']
        yesterday_low = data.iloc[current_idx - 1]['low']
        today_open = data.iloc[current_idx]['open']

        return today_open + (yesterday_high - yesterday_low) * self.k_value

    def _calculate_target_price(self, data: pd.DataFrame, current_idx: int) -> float:
        """
        기존 고정 K값 방식 돌파가 계산 (테스트용 wrapper)

        Args:
            data: OHLCV 데이터
            current_idx: 현재 인덱스

        Returns:
            돌파가
        """
        if current_idx < 2:
            return data.iloc[current_idx]['open']

        yesterday_high = data.iloc[current_idx - 1]['high']
        yesterday_low = data.iloc[current_idx - 1]['low']
        today_open = data.iloc[current_idx]['open']

        return today_open + (yesterday_high - yesterday_low) * self.k_value

