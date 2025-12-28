"""
AI 분석 서비스
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI
import pandas as pd
import numpy as np
import talib
from ..config.settings import AIConfig, DataConfig
from ..utils.helpers import df_to_json_dict, safe_json_dumps
from ..utils.logger import Logger
from ..trading.signal_analyzer import SignalAnalyzer
from ..trading.indicators import TechnicalIndicators


class AIService:
    """AI 분석 서비스 클래스"""
    
    @staticmethod
    def _format_number(value: Any, format_str: str = ',.0f') -> str:
        """
        숫자 포맷팅 헬퍼 함수
        숫자일 때만 포맷을 적용하고, 'N/A'나 None일 때는 그대로 반환
        
        Args:
            value: 포맷할 값
            format_str: 포맷 문자열 (예: ',.0f', '.2f', '.1f')
            
        Returns:
            포맷된 문자열 또는 원본 값
        """
        if value == 'N/A' or value is None:
            return 'N/A'
        try:
            if isinstance(value, (int, float)):
                return f"{value:{format_str}}"
            return str(value)
        except (ValueError, TypeError):
            return 'N/A'
    
    def __init__(self):
        """AI 서비스 초기화"""
        self.client = OpenAI()
        self.model = AIConfig.MODEL
    
    def prepare_analysis_data(
        self,
        chart_data: Dict,
        orderbook_summary: Dict,
        current_status: Dict,
        technical_indicators: Optional[Dict[str, float]] = None,
        position_info: Optional[Dict[str, Any]] = None,
        fear_greed_index: Optional[Dict[str, Any]] = None,
        backtest_result: Optional[Dict[str, Any]] = None,
        market_correlation: Optional[Dict[str, Any]] = None,
        flash_crash: Optional[Dict[str, Any]] = None,
        rsi_divergence: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        AI 분석을 위한 데이터 준비 (전문 투자자 관점의 심화 분석)
        
        Args:
            chart_data: 차트 데이터
            orderbook_summary: 오더북 요약
            current_status: 현재 상태
            technical_indicators: 기술적 지표
            position_info: 포지션 정보
            fear_greed_index: 공포탐욕지수
            backtest_result: 백테스팅 결과 (빠른 백테스팅 필터링 결과)
            market_correlation: 시장 상관관계 분석 (Phase 2)
            flash_crash: 플래시 크래시 감지 결과 (Phase 2)
            rsi_divergence: RSI 다이버전스 감지 결과 (Phase 2)
            
        Returns:
            AI 분석용 데이터 딕셔너리
        """
        # 차트 데이터 최적화: 전체 데이터 대신 요약 통계만 전달
        # 백테스팅에서는 minute60 데이터가 없을 수 있으므로 안전하게 처리
        # DataFrame은 or 연산자로 직접 체크할 수 없으므로 is not None으로 체크
        hourly_data = chart_data.get('minute60')
        if hourly_data is None:
            hourly_data = chart_data.get('hourly')
        if hourly_data is None:
            hourly_data = chart_data.get('day')
        
        data = {
            "daily_chart_summary": self._create_chart_summary(
                chart_data['day'], 
                current_status.get('current_price', 0)
            ),
            "hourly_chart_summary": self._create_chart_summary(
                hourly_data, 
                current_status.get('current_price', 0),
                recent_days=5
            ),
            "orderbook_summary": orderbook_summary,
            "current_status": current_status
        }
        
        # 기술적 지표 추가
        if technical_indicators:
            data["technical_indicators"] = technical_indicators
            
            # 신호 분석 추가 (베스트 프랙티스 기반)
            if current_status.get('current_price'):
                signal_analysis = SignalAnalyzer.analyze_signals(
                    technical_indicators,
                    current_status['current_price']
                )
                data["signal_analysis"] = signal_analysis
        
        # 포지션 정보 추가
        if position_info:
            data["position_info"] = position_info
        
        # 공포탐욕지수 추가
        if fear_greed_index:
            data["fear_greed_index"] = fear_greed_index
        
        # Phase 2: 시장 상관관계 분석 추가
        if market_correlation:
            data["market_correlation"] = market_correlation
        
        # Phase 2: 플래시 크래시 감지 결과 추가
        if flash_crash:
            data["flash_crash"] = flash_crash
        
        # Phase 2: RSI 다이버전스 감지 결과 추가
        if rsi_divergence:
            data["rsi_divergence"] = rsi_divergence
        
        # 추가 고급 지표 계산
        current_price = current_status.get('current_price', 0)
        if current_price > 0 and chart_data:
            # 1. 변동성 지표 강화
            volatility_indicators = self._calculate_volatility_indicators(
                technical_indicators, current_price
            )
            if volatility_indicators:
                data["volatility_indicators"] = volatility_indicators
            
            # 2. 거래량 분석 강화
            volume_analysis = self._calculate_volume_analysis(chart_data['day'])
            if volume_analysis:
                data["volume_analysis"] = volume_analysis
            
            # 3. 모멘텀 지표 추가
            momentum_indicators = self._calculate_momentum_indicators(
                technical_indicators
            )
            if momentum_indicators:
                data["momentum_indicators"] = momentum_indicators
            
            # 4. 시장 구조 분석
            market_structure = self._calculate_market_structure(
                chart_data['day'], current_price
            )
            if market_structure:
                data["market_structure"] = market_structure
            
            # 5. 다중 시간대 분석
            timeframe_analysis = self._calculate_multi_timeframe_analysis(chart_data)
            if timeframe_analysis:
                data["timeframe_analysis"] = timeframe_analysis
            
            # 6. 리스크 메트릭스
            risk_metrics = self._calculate_risk_metrics(chart_data['day'])
            if risk_metrics:
                data["risk_metrics"] = risk_metrics
            
            # 7. 오더북 심화 분석
            advanced_orderbook = self._analyze_advanced_orderbook(
                orderbook_summary, current_price
            )
            if advanced_orderbook:
                data["advanced_orderbook"] = advanced_orderbook
            
            # 8. 캔들 패턴 인식
            candlestick_patterns = self._detect_candlestick_patterns(chart_data['day'])
            if candlestick_patterns:
                data["candlestick_patterns"] = candlestick_patterns
        
        # 9. 백테스팅 결과 추가 (빠른 백테스팅 필터링 결과)
        if backtest_result:
            data["backtest_result"] = backtest_result
        
        return data
    
    def _calculate_volatility_indicators(
        self, 
        technical_indicators: Dict[str, float], 
        current_price: float
    ) -> Optional[Dict[str, float]]:
        """변동성 지표 계산 (예외 안전)"""
        try:
            if not technical_indicators:
                Logger.print_warning("기술적 지표 없음 - 변동성 분석 스킵")
                return None
            
            volatility = {}
            
            # ATR
            try:
                if 'atr' in technical_indicators:
                    volatility['atr'] = float(technical_indicators['atr'])
            except (ValueError, TypeError, KeyError) as e:
                Logger.print_warning(f"ATR 변환 실패: {e}")
            
            # 볼린저 밴드
            try:
                required_keys = ['bb_upper', 'bb_middle', 'bb_lower']
                if all(k in technical_indicators for k in required_keys):
                    volatility['bb_upper'] = float(technical_indicators['bb_upper'])
                    volatility['bb_middle'] = float(technical_indicators['bb_middle'])
                    volatility['bb_lower'] = float(technical_indicators['bb_lower'])
                    if 'bb_width' in technical_indicators:
                        volatility['bb_width'] = float(technical_indicators['bb_width'])
            except (ValueError, TypeError, KeyError) as e:
                Logger.print_warning(f"볼린저 밴드 변환 실패: {e}")
            
            # 켈트너 채널
            try:
                if all(k in technical_indicators for k in ['keltner_upper', 'keltner_lower']):
                    volatility['keltner_upper'] = float(technical_indicators['keltner_upper'])
                    volatility['keltner_lower'] = float(technical_indicators['keltner_lower'])
            except (ValueError, TypeError, KeyError) as e:
                Logger.print_warning(f"켈트너 채널 변환 실패: {e}")
            
            return volatility if volatility else None
            
        except Exception as e:
            Logger.print_error(f"변동성 지표 계산 중 오류: {e}")
            return None
    
    def _calculate_volume_analysis(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """거래량 분석 강화 (개선된 계산)"""
        try:
            if df is None or 'volume' not in df.columns or len(df) < 2:
                return None
            
            volume_indicators = TechnicalIndicators.calculate_volume_indicators(df)
            
            # OBV
            try:
                obv = TechnicalIndicators.calculate_obv(df)
                if not obv.empty and not pd.isna(obv.iloc[-1]):
                    volume_indicators['obv'] = float(obv.iloc[-1])
                    
                    # OBV 기울기로 모멘텀 측정
                    if len(obv) >= 5:
                        obv_slope = (obv.iloc[-1] - obv.iloc[-5]) / 5
                        volume_indicators['obv_momentum'] = float(obv_slope)
            except Exception as e:
                Logger.print_warning(f"OBV 계산 실패: {e}")
            
            # 가격-거래량 상관관계
            try:
                if len(df) >= 20:
                    price_volume_corr = df['close'].tail(20).corr(df['volume'].tail(20))
                    if not pd.isna(price_volume_corr):
                        volume_indicators['price_volume_correlation'] = float(price_volume_corr)
            except Exception as e:
                Logger.print_warning(f"가격-거래량 상관관계 계산 실패: {e}")
            
            # VWAP (Volume Weighted Average Price)
            try:
                if len(df) >= 20:
                    recent_20 = df.tail(20)
                    vwap = (recent_20['close'] * recent_20['volume']).sum() / recent_20['volume'].sum()
                    current_price = df['close'].iloc[-1]
                    if vwap > 0:
                        vwap_distance = ((current_price - vwap) / vwap) * 100
                        volume_indicators['vwap'] = float(vwap)
                        volume_indicators['vwap_distance'] = float(vwap_distance)
            except Exception as e:
                Logger.print_warning(f"VWAP 계산 실패: {e}")
            
            # 개선된 매수/매도 압력 계산
            try:
                if len(df) >= 5:
                    # 최근 5일 평균 대비 현재 거래량
                    avg_volume_5d = df['volume'].tail(5).mean()
                    current_volume = df['volume'].iloc[-1]
                    volume_ratio = current_volume / avg_volume_5d if avg_volume_5d > 0 else 1.0
                    
                    # 가격 변화율
                    price_change_pct = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
                    
                    # 거래량과 가격 변화의 조합으로 압력 계산
                    if price_change_pct > 0 and volume_ratio > 1.0:
                        buying_pressure = min(100, abs(price_change_pct) * volume_ratio)
                        selling_pressure = max(0, 100 - buying_pressure)
                    elif price_change_pct < 0 and volume_ratio > 1.0:
                        selling_pressure = min(100, abs(price_change_pct) * volume_ratio)
                        buying_pressure = max(0, 100 - selling_pressure)
                    else:
                        buying_pressure = 50
                        selling_pressure = 50
                    
                    volume_indicators['buying_pressure'] = float(buying_pressure)
                    volume_indicators['selling_pressure'] = float(selling_pressure)
            except Exception as e:
                Logger.print_warning(f"매수/매도 압력 계산 실패: {e}")
            
            return volume_indicators if volume_indicators else None
            
        except Exception as e:
            Logger.print_error(f"거래량 분석 중 오류: {e}")
            return None
    
    def _calculate_momentum_indicators(
        self, 
        technical_indicators: Dict[str, float]
    ) -> Optional[Dict[str, float]]:
        """모멘텀 지표 계산 (예외 안전)"""
        try:
            if not technical_indicators:
                return None
            
            momentum = {}
            
            # 각 지표를 안전하게 추출
            for key in ['roc', 'cci', 'williams_r', 'adx', 'plus_di', 'minus_di']:
                try:
                    if key in technical_indicators:
                        momentum[key] = float(technical_indicators[key])
                except (ValueError, TypeError, KeyError) as e:
                    Logger.print_warning(f"{key} 변환 실패: {e}")
            
            return momentum if momentum else None
            
        except Exception as e:
            Logger.print_error(f"모멘텀 지표 계산 중 오류: {e}")
            return None
    
    def _find_swing_high(self, df: pd.DataFrame, lookback: int = 50) -> int:
        """스윙 고점 찾기"""
        try:
            if len(df) < lookback:
                lookback = len(df)
            
            recent_data = df.tail(lookback)
            high_idx = recent_data['high'].idxmax()
            return df.index.get_loc(high_idx)
        except:
            return len(df) - 1
    
    def _find_swing_low(self, df: pd.DataFrame, lookback: int = 50) -> int:
        """스윙 저점 찾기"""
        try:
            if len(df) < lookback:
                lookback = len(df)
            
            recent_data = df.tail(lookback)
            low_idx = recent_data['low'].idxmin()
            return df.index.get_loc(low_idx)
        except:
            return len(df) - 1
    
    def _is_uptrend(self, df: pd.DataFrame) -> bool:
        """상승 추세 여부 판단"""
        try:
            if len(df) < 20:
                return False
            ma20 = TechnicalIndicators.calculate_ma(df, 20)
            ma50 = TechnicalIndicators.calculate_ma(df, 50) if len(df) >= 50 else None
            if ma50 is not None and not ma50.empty:
                return ma20.iloc[-1] > ma50.iloc[-1]
            return df['close'].iloc[-1] > df['close'].iloc[-20]
        except:
            return False
    
    def _calculate_market_structure(
        self, 
        df: pd.DataFrame, 
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """시장 구조 분석 (개선된 피보나치 계산)"""
        try:
            if df is None or len(df) < 20:
                return None
            
            structure = {}
            
            # 지지/저항 레벨
            try:
                levels = TechnicalIndicators.calculate_support_resistance_levels(df)
                structure['support_levels'] = levels.get('support_levels', [])
                structure['resistance_levels'] = levels.get('resistance_levels', [])
            except Exception as e:
                Logger.print_warning(f"지지/저항 레벨 계산 실패: {e}")
                structure['support_levels'] = []
                structure['resistance_levels'] = []
            
            # 개선된 피보나치 되돌림 (스윙 포인트 기반)
            try:
                if len(df) >= 50:
                    swing_high_idx = self._find_swing_high(df, lookback=50)
                    swing_low_idx = self._find_swing_low(df, lookback=50)
                    is_uptrend = self._is_uptrend(df)
                    
                    if is_uptrend:
                        # 상승 추세: 저점에서 고점으로
                        base = df['low'].iloc[swing_low_idx]
                        target = df['high'].iloc[swing_high_idx]
                    else:
                        # 하락 추세: 고점에서 저점으로
                        base = df['high'].iloc[swing_high_idx]
                        target = df['low'].iloc[swing_low_idx]
                    
                    diff = abs(target - base)
                    if diff > 0:
                        structure['fibonacci_levels'] = {
                            "23.6%": float(base + diff * 0.236),
                            "38.2%": float(base + diff * 0.382),
                            "50.0%": float(base + diff * 0.5),
                            "61.8%": float(base + diff * 0.618)
                        }
                        structure['fibonacci_base'] = float(base)
                        structure['fibonacci_target'] = float(target)
                        structure['fibonacci_trend'] = 'uptrend' if is_uptrend else 'downtrend'
                elif len(df) >= 20:
                    # Fallback: 최근 20일 기준
                    recent_high = df['high'].tail(20).max()
                    recent_low = df['low'].tail(20).min()
                    diff = recent_high - recent_low
                    
                    if diff > 0:
                        structure['fibonacci_levels'] = {
                            "23.6%": float(recent_high - diff * 0.236),
                            "38.2%": float(recent_high - diff * 0.382),
                            "50.0%": float(recent_high - diff * 0.5),
                            "61.8%": float(recent_high - diff * 0.618)
                        }
            except Exception as e:
                Logger.print_warning(f"피보나치 계산 실패: {e}")
            
            # 가격 구조 분석
            try:
                if len(df) >= 10:
                    recent_highs = df['high'].tail(10)
                    recent_lows = df['low'].tail(10)
                    
                    structure['higher_highs'] = bool(recent_highs.iloc[-1] > recent_highs.iloc[-5] if len(recent_highs) >= 5 else False)
                    structure['higher_lows'] = bool(recent_lows.iloc[-1] > recent_lows.iloc[-5] if len(recent_lows) >= 5 else False)
                    
                    if structure['higher_highs'] and structure['higher_lows']:
                        structure['trend_structure'] = 'bullish'
                    elif not structure['higher_highs'] and not structure['higher_lows']:
                        structure['trend_structure'] = 'bearish'
                    else:
                        structure['trend_structure'] = 'sideways'
            except Exception as e:
                Logger.print_warning(f"가격 구조 분석 실패: {e}")
            
            return structure if structure else None
            
        except Exception as e:
            Logger.print_error(f"시장 구조 분석 중 오류: {e}")
            return None
    
    def _calculate_multi_timeframe_analysis(
        self, 
        chart_data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict[str, Any]]:
        """다중 시간대 분석 (예외 안전)"""
        try:
            if not chart_data:
                return None
            
            timeframe_analysis = {}
            
            # 15분봉 분석
            try:
                if 'minute15' in chart_data and chart_data['minute15'] is not None:
                    df_15m = chart_data['minute15']
                    if len(df_15m) >= 14:
                        indicators_15m = TechnicalIndicators.get_latest_indicators(df_15m)
                        timeframe_analysis['15min'] = {
                            'rsi': indicators_15m.get('rsi'),
                            'macd_signal': 'bullish' if indicators_15m.get('macd', 0) > indicators_15m.get('macd_signal', 0) else 'bearish',
                            'trend': 'bullish' if df_15m['close'].iloc[-1] > df_15m['close'].iloc[-5] else 'bearish' if len(df_15m) >= 5 else 'neutral'
                        }
            except Exception as e:
                Logger.print_warning(f"15분봉 분석 실패: {e}")
            
            # 4시간봉 분석 (60분봉으로 대체)
            try:
                if 'minute60' in chart_data and chart_data['minute60'] is not None:
                    df_4h = chart_data['minute60']
                    if len(df_4h) >= 20:
                        current_price = df_4h['close'].iloc[-1]
                        ma20 = TechnicalIndicators.calculate_ma(df_4h, 20)
                        if not ma20.empty:
                            key_level_distance = ((current_price - ma20.iloc[-1]) / ma20.iloc[-1]) * 100
                            timeframe_analysis['4hour'] = {
                                'trend': 'bullish' if current_price > ma20.iloc[-1] else 'bearish',
                                'key_level_distance': float(key_level_distance),
                                'volume_profile': 'high' if df_4h['volume'].tail(5).mean() > df_4h['volume'].mean() else 'low'
                            }
            except Exception as e:
                Logger.print_warning(f"4시간봉 분석 실패: {e}")
            
            # 일봉 분석
            try:
                if 'day' in chart_data and chart_data['day'] is not None:
                    df_daily = chart_data['day']
                    if len(df_daily) >= 50:
                        ma20 = TechnicalIndicators.calculate_ma(df_daily, 20)
                        ma50 = TechnicalIndicators.calculate_ma(df_daily, 50)
                        if not ma20.empty and not ma50.empty:
                            ma_alignment = ma20.iloc[-1] > ma50.iloc[-1]
                            timeframe_analysis['daily'] = {
                                'trend': 'bullish' if df_daily['close'].iloc[-1] > ma20.iloc[-1] else 'bearish',
                                'ma_alignment': bool(ma_alignment)
                            }
            except Exception as e:
                Logger.print_warning(f"일봉 분석 실패: {e}")
            
            return timeframe_analysis if timeframe_analysis else None
            
        except Exception as e:
            Logger.print_error(f"다중 시간대 분석 중 오류: {e}")
            return None
    
    def _calculate_risk_metrics(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """리스크 메트릭스 계산 (개선된 버전)"""
        try:
            if df is None or len(df) < 30:
                return None
            
            metrics = {}
            
            # 일간 수익률 계산
            try:
                returns = df['close'].pct_change().dropna()
                if len(returns) < 30:
                    return None
                
                recent_returns = returns.tail(30)
                
                # 무위험 이자율 (연 5%를 일간으로, 암호화폐는 높은 리스크 프리미엄 고려)
                risk_free_rate_daily = 0.05 / 365.25
                
                # 초과 수익률
                excess_returns = recent_returns - risk_free_rate_daily
                
                # 30일 변동성 (연율화, 365.25일 고려)
                volatility_30d = recent_returns.std() * np.sqrt(365.25) * 100
                metrics['volatility_30d'] = float(volatility_30d)
                
                # 개선된 Sharpe Ratio
                if excess_returns.std() > 0:
                    sharpe_ratio = (excess_returns.mean() / excess_returns.std()) * np.sqrt(365.25)
                    metrics['sharpe_ratio'] = float(sharpe_ratio)
                
                # Sortino Ratio (하방 리스크만 고려)
                downside_returns = excess_returns[excess_returns < 0]
                if len(downside_returns) > 0 and downside_returns.std() > 0:
                    sortino_ratio = (excess_returns.mean() / downside_returns.std()) * np.sqrt(365.25)
                    metrics['sortino_ratio'] = float(sortino_ratio)
                
            except Exception as e:
                Logger.print_warning(f"수익률 기반 메트릭스 계산 실패: {e}")
            
            # 최대 낙폭 (Max Drawdown)
            try:
                if len(df) >= 30:
                    cumulative = (1 + df['close'].pct_change()).cumprod()
                    running_max = cumulative.expanding().max()
                    drawdown = (cumulative - running_max) / running_max
                    max_drawdown = drawdown.min() * 100
                    metrics['max_drawdown'] = float(max_drawdown)
            except Exception as e:
                Logger.print_warning(f"최대 낙폭 계산 실패: {e}")
            
            # 유동성 점수 (거래량 기반)
            try:
                if 'volume' in df.columns and len(df) >= 20:
                    avg_volume = df['volume'].tail(20).mean()
                    current_volume = df['volume'].iloc[-1]
                    if avg_volume > 0:
                        liquidity_score = min(100, (current_volume / avg_volume) * 50)
                        metrics['liquidity_score'] = float(liquidity_score)
            except Exception as e:
                Logger.print_warning(f"유동성 점수 계산 실패: {e}")
            
            return metrics if metrics else None
            
        except Exception as e:
            Logger.print_error(f"리스크 메트릭스 계산 중 오류: {e}")
            return None
    
    def _analyze_advanced_orderbook(
        self, 
        orderbook_summary: Dict, 
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """오더북 심화 분석 (예외 안전)"""
        try:
            if not orderbook_summary or current_price <= 0:
                return None
            
            analysis = {}
            
            # 매수/매도 불균형
            try:
                bid_volumes = orderbook_summary.get('bid_volumes', [])
                ask_volumes = orderbook_summary.get('ask_volumes', [])
                
                if bid_volumes and ask_volumes:
                    total_bid = sum(bid_volumes[:10])  # 상위 10개
                    total_ask = sum(ask_volumes[:10])
                    total_volume = total_bid + total_ask
                    
                    if total_volume > 0:
                        imbalance = ((total_bid - total_ask) / total_volume) * 100
                        analysis['bid_ask_imbalance'] = float(imbalance)
            except Exception as e:
                Logger.print_warning(f"매수/매도 불균형 계산 실패: {e}")
            
            # 큰 주문 (Whale Walls) 찾기
            try:
                large_orders = []
                bid_prices = orderbook_summary.get('bid_prices', [])
                ask_prices = orderbook_summary.get('ask_prices', [])
                
                # 매수 측 큰 주문
                if bid_prices and bid_volumes:
                    total_bid_20 = sum(bid_volumes[:20])
                    for i, (price, volume) in enumerate(zip(bid_prices[:20], bid_volumes[:20])):
                        if total_bid_20 > 0 and volume > total_bid_20 * 0.1:  # 전체의 10% 이상
                            large_orders.append({
                                'side': 'bid',
                                'price': float(price),
                                'volume': float(volume),
                                'percentage': float((volume / total_bid_20) * 100)
                            })
                
                # 매도 측 큰 주문
                if ask_prices and ask_volumes:
                    total_ask_20 = sum(ask_volumes[:20])
                    for i, (price, volume) in enumerate(zip(ask_prices[:20], ask_volumes[:20])):
                        if total_ask_20 > 0 and volume > total_ask_20 * 0.1:
                            large_orders.append({
                                'side': 'ask',
                                'price': float(price),
                                'volume': float(volume),
                                'percentage': float((volume / total_ask_20) * 100)
                            })
                
                if large_orders:
                    analysis['large_orders'] = large_orders[:5]  # 상위 5개만
            except Exception as e:
                Logger.print_warning(f"큰 주문 분석 실패: {e}")
            
            # 스프레드 분석
            try:
                bid_prices = orderbook_summary.get('bid_prices', [])
                ask_prices = orderbook_summary.get('ask_prices', [])
                if bid_prices and ask_prices and len(bid_prices) > 0 and len(ask_prices) > 0:
                    spread = ask_prices[0] - bid_prices[0]
                    if current_price > 0:
                        spread_bps = (spread / current_price) * 10000  # basis points
                        analysis['spread_analysis'] = {
                            'spread_bps': float(spread_bps),
                            'spread_trend': 'narrowing' if spread_bps < 10 else 'widening'
                        }
            except Exception as e:
                Logger.print_warning(f"스프레드 분석 실패: {e}")
            
            return analysis if analysis else None
            
        except Exception as e:
            Logger.print_error(f"오더북 심화 분석 중 오류: {e}")
            return None
    
    def _detect_candlestick_patterns(
        self, 
        df: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """캔들 패턴 인식 (TA-Lib 필수 사용)"""
        try:
            if df is None or len(df) < 3:
                return None
            
            patterns = []
            recent_candles = df.tail(10)  # 더 많은 캔들 확인
            
            if len(recent_candles) >= 3:
                # TA-Lib 패턴 인식
                open_prices = recent_candles['open'].values
                high_prices = recent_candles['high'].values
                low_prices = recent_candles['low'].values
                close_prices = recent_candles['close'].values
                
                # 주요 패턴들 감지
                pattern_functions = {
                    'hammer': talib.CDLHAMMER,
                    'doji': talib.CDLDOJI,
                    'engulfing': talib.CDLENGULFING,
                    'morning_star': talib.CDLMORNINGSTAR,
                    'evening_star': talib.CDLEVENINGSTAR,
                    'shooting_star': talib.CDLSHOOTINGSTAR,
                    'hanging_man': talib.CDLHANGINGMAN,
                    'inverted_hammer': talib.CDLINVERTEDHAMMER,
                    'three_white_soldiers': talib.CDL3WHITESOLDIERS,
                    'three_black_crows': talib.CDL3BLACKCROWS,
                    'harami': talib.CDLHARAMI,
                    'harami_cross': talib.CDLHARAMICROSS,
                    'dark_cloud_cover': talib.CDLDARKCLOUDCOVER,
                    'piercing': talib.CDLPIERCING
                }
                
                for pattern_name, pattern_func in pattern_functions.items():
                    try:
                        result = pattern_func(open_prices, high_prices, low_prices, close_prices)
                        # 최근 3개 캔들에서 패턴 확인
                        for i in range(-3, 0):
                            if abs(result[i]) > 0:  # 0이 아니면 패턴 감지
                                signal = 'bullish' if result[i] > 0 else 'bearish'
                                confidence = 'strong' if abs(result[i]) >= 100 else 'moderate'
                                
                                # 위치 판단
                                current_price = close_prices[i]
                                location = 'midrange'
                                if i == -1:  # 가장 최근 캔들
                                    # 지지/저항 근처인지 간단히 판단
                                    recent_range = (high_prices[-10:].max() - low_prices[-10:].min())
                                    if recent_range > 0:
                                        price_position = (current_price - low_prices[-10:].min()) / recent_range
                                        if price_position < 0.2:
                                            location = 'at_support'
                                        elif price_position > 0.8:
                                            location = 'at_resistance'
                                
                                patterns.append({
                                    'pattern': pattern_name,
                                    'signal': signal,
                                    'confidence': confidence,
                                    'location': location
                                })
                                break  # 한 패턴당 하나만 추가
                    except Exception as e:
                        Logger.print_warning(f"TA-Lib 패턴 {pattern_name} 감지 실패: {e}")
                        continue
            
            # 중복 제거 및 최신 순 정렬
            seen = set()
            unique_patterns = []
            for p in reversed(patterns):  # 최신부터
                key = (p['pattern'], p['signal'])
                if key not in seen:
                    seen.add(key)
                    unique_patterns.append(p)
            
            return {'recent_patterns': unique_patterns[:5]} if unique_patterns else None
            
        except Exception as e:
            Logger.print_error(f"캔들 패턴 인식 중 오류: {e}")
            return None
    
    def _create_chart_summary(
        self, 
        df: pd.DataFrame, 
        current_price: float,
        recent_days: int = 5
    ) -> Dict[str, Any]:
        """
        차트 데이터 요약 생성 (토큰 최적화)
        
        Args:
            df: 차트 DataFrame
            current_price: 현재가
            recent_days: 최근 며칠치 상세 데이터 포함
            
        Returns:
            요약된 차트 데이터 딕셔너리
        """
        try:
            if df is None or len(df) == 0:
                return {}
            
            # 최근 N일 상세 데이터
            recent_data = df.tail(recent_days)
            
            # 주요 통계
            summary = {
                "recent_candles": df_to_json_dict(recent_data),
                "key_statistics": {}
            }
            
            # 30일 통계 (또는 사용 가능한 데이터)
            lookback = min(30, len(df))
            if lookback > 0:
                recent_30d = df.tail(lookback)
                
                # 이동평균 계산
                ma20 = TechnicalIndicators.calculate_ma(recent_30d, 20)
                ma50 = TechnicalIndicators.calculate_ma(recent_30d, 50) if len(recent_30d) >= 50 else None
                
                summary["key_statistics"] = {
                    "period_high": float(recent_30d['high'].max()),
                    "period_low": float(recent_30d['low'].min()),
                    "period_avg_volume": float(recent_30d['volume'].mean()),
                    "current_price": float(current_price) if current_price > 0 else float(df['close'].iloc[-1]),
                    "price_change_pct": float(((df['close'].iloc[-1] - df['close'].iloc[-lookback]) / df['close'].iloc[-lookback]) * 100) if lookback > 0 else 0.0,
                    "ma20": float(ma20.iloc[-1]) if not ma20.empty and not pd.isna(ma20.iloc[-1]) else None,
                    "ma50": float(ma50.iloc[-1]) if ma50 is not None and not ma50.empty and not pd.isna(ma50.iloc[-1]) else None,
                    "trend": "bullish" if (ma50 is not None and not ma50.empty and ma20.iloc[-1] > ma50.iloc[-1]) else "bearish" if ma50 is not None else "neutral",
                    "volatility": float(recent_30d['close'].pct_change().std() * 100) if len(recent_30d) > 1 else 0.0
                }
            
            return summary
            
        except Exception as e:
            Logger.print_error(f"차트 요약 생성 실패: {e}")
            # Fallback: 최소한의 데이터라도 반환
            try:
                return {
                    "recent_candles": df_to_json_dict(df.tail(5)),
                    "key_statistics": {
                        "current_price": float(df['close'].iloc[-1]) if len(df) > 0 else 0.0
                    }
                }
            except:
                return {}
    
    def analyze(
        self,
        ticker: str,
        analysis_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        AI 분석 수행
        
        Args:
            ticker: 거래 종목
            analysis_data: 분석용 데이터
            
        Returns:
            AI 분석 결과 (decision, reason, confidence)
        """
        coin_symbol = ticker.split('-')[1]
        
        # 변동성 돌파 룰 통과 여부 확인
        is_breakout_strategy = analysis_data.get('rule_breakout', {}).get('passed', False)
        
        if is_breakout_strategy:
            # 백테스팅 결과 기반 판단 가이드
            bt_result = analysis_data.get('backtest_result', {})
            metrics = bt_result.get('metrics', {})
            
            # 백테스팅 등급 판정
            total_return = metrics.get('total_return', 0)
            win_rate = metrics.get('win_rate', 0)
            sharpe = metrics.get('sharpe_ratio', 0)
            profit_factor = metrics.get('profit_factor', 0)
            
            if total_return > 5 and win_rate > 40 and sharpe > 0.5:
                backtest_grade = "STRONG PASS"
                recommended_action = "전략이 작동 중. 현재 시그널 신뢰 가능. 매수 진행."
            elif total_return > 3 and win_rate > 35 and sharpe > 0.3:
                backtest_grade = "WEAK PASS"
                recommended_action = "전략 약화 중. 포지션 사이즈 50% 축소 권장."
            else:
                backtest_grade = "FAIL"
                recommended_action = "전략 실패. 시장 환경 변화. 매수 금지."
            
            # 개선된 변동성 돌파 프롬프트 (안전/위험 조건 분리)
            system_prompt = (
                f"당신은 백테스팅 검증 전략의 실행 환경을 체크하는 검증자입니다.\n\n"
                
                f"## 현재 상황:\n"
                f"- 백테스팅 통과: 전략이 작동 중입니다.\n"
                f"- 전략: 변동성 돌파 (Volatility Breakout)\n"
                f"- 진입 조건: 3단계 관문(응축 → 돌파 → 거래량) 모두 충족\n\n"
                
                f"## 백테스팅 성과 (최근 30일):\n"
                f"- 총 수익률: {self._format_number(total_return, '.2f')}% (기준: >5%)\n"
                f"- 승률: {self._format_number(win_rate, '.2f')}% (기준: >40%)\n"
                f"- Sharpe Ratio: {self._format_number(sharpe, '.2f')} (기준: >0.5)\n"
                f"- Profit Factor: {self._format_number(profit_factor, '.2f')} (기준: >1.5)\n"
                f"→ **등급: {backtest_grade}** - {recommended_action}\n\n"
                
                f"## 당신의 임무:\n"
                f"현재 시장 환경에서 이상 징후만 체크하세요. 전략은 이미 검증되었습니다.\n\n"
                
                f"### ✅ 안전 조건 (모두 충족해야 함):\n"
                f"1. **오더북 안전**: 매도벽 비율 < 5% (현재가 위 큰 매도벽 없음)\n"
                f"2. **추세 명확**: ADX > 25 (강한 추세 존재)\n"
                f"3. **거래량 확인**: 현재 거래량 > 평균의 1.5배\n"
                f"4. **볼린저 밴드**: 상단 터치 후 즉시 하락 패턴 아님\n\n"
                
                f"### ⚠️ 위험 조건 (하나라도 있으면 중단):\n"
                f"1. **BTC 급락 위험**: market_risk='high' (베타 > 1.2, 알파 < 0, BTC 하락 중)\n"
                f"2. **RSI 다이버전스**: 가격 상승하지만 RSI 고점 하락 (모멘텀 약화)\n"
                f"3. **플래시 크래시**: 비정상적 급락 감지 (ATR 대비 2배 이상)\n"
                f"4. **극단적 탐욕**: 공포탐욕지수 > 75 (과열 시장)\n\n"
                
                f"## 판단 기준:\n"
                f"- **BUY**: 안전 조건 모두 충족 AND 위험 조건 없음\n"
                f"- **HOLD**: 안전 조건 미충족 OR 위험 조건 하나 이상 존재\n"
                f"- **SELL**: 위험 조건 2개 이상 또는 명백한 플래시 크래시\n\n"
                
                f"## 출력 형식 (한국어 JSON):\n"
                f"{{\n"
                f"  \"decision\": \"buy|sell|hold\",\n"
                f"  \"reason\": \"6개 섹션으로 구성된 상세 분석 (한국어)\",\n"
                f"  \"confidence\": \"high|medium|low\",\n"
                f"  \"safety_conditions_met\": {{\"orderbook\": true/false, \"trend\": true/false, \"volume\": true/false, \"bb_pattern\": true/false}},\n"
                f"  \"risk_conditions_detected\": {{\"btc_risk\": true/false, \"rsi_divergence\": true/false, \"flash_crash\": true/false, \"greed_index\": true/false}},\n"
                f"  \"key_indicators\": [\"주요 지표 리스트\"]\n"
                f"}}\n\n"
                
                f"**중요**: 백테스팅에서 검증된 전략을 신뢰하되, 현재 시장 환경의 이상 징후만 엄격히 체크하세요."
            )
        else:
            # 일반 분석 프롬프트
            system_prompt = (
                f"Professional {coin_symbol} trading analyst. Provide objective, data-driven recommendations.\n\n"
                
                f"Analysis Framework:\n"
                f"- Trend: MA/EMA alignment, structure (HH/HL)\n"
                f"- Momentum: RSI, MACD, oscillators (overbought/oversold)\n"
                f"- Volume: OBV, pressure, unusual activity, VWAP\n"
                f"- Volatility: ATR, BB width, risk metrics\n"
                f"- Structure: S/R levels, Fibonacci, orderbook dynamics\n"
                f"- Multi-timeframe: 15m/4h/daily alignment\n\n"
                
                f"Decision Criteria:\n"
                f"- BUY: Bullish convergence, volume confirmation, favorable R/R, support proximity\n"
                f"- SELL: Bearish signals, resistance proximity, risk reduction, overbought\n"
                f"- HOLD: Mixed signals, consolidation, awaiting confirmation\n\n"
                
                f"Reason Structure (6 sections in Korean):\n"
                f"1. 종합 평가 2. 추세 분석 3. 모멘텀 분석\n"
                f"4. 변동성/거래량 5. 시장 구조 6. 신호 종합 및 판단\n\n"
                
                f"Output (Korean JSON):\n"
                f"{{\"decision\": \"buy|sell|hold\", \"reason\": \"6-section analysis\", \"confidence\": \"high|medium|low\", \"key_indicators\": [...]}}\n"
            )

        # 변동성 돌파 룰 통과 정보 추가
        rule_breakout_info = ""
        if is_breakout_strategy:
            rule_info = analysis_data.get('rule_breakout', {})
            rule_breakout_info = f"""

🚨 변동성 돌파 전략 룰 통과 정보:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 관문 1 (응축): {rule_info.get('gate1', 'N/A')}
✅ 관문 2 (돌파): {rule_info.get('gate2', 'N/A')}
✅ 관문 3 (거래량): {rule_info.get('gate3', 'N/A')}

**중요**: 위 룰을 통과했지만, 이는 '속임수(Fakeout)'일 수 있습니다.
아래 데이터를 철저히 분석하여 진짜 돌파인지 가짜 돌파인지 판단하세요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        user_prompt = f"""Analyze this comprehensive market data and provide professional investment decision:
{rule_breakout_info}
DAILY CHART SUMMARY:
{safe_json_dumps(analysis_data.get('daily_chart_summary', {}))}

HOURLY CHART SUMMARY:
{safe_json_dumps(analysis_data.get('hourly_chart_summary', {}))}

ORDERBOOK:
{safe_json_dumps(analysis_data['orderbook_summary'])}

CURRENT STATUS:
- KRW Balance: {analysis_data['current_status']['krw_balance']:,.0f} KRW
- {ticker} Balance: {analysis_data['current_status']['coin_balance']:.8f}
- Current Price: {analysis_data['current_status']['current_price']:,.0f} KRW"""

        # 기술적 지표 추가
        if 'technical_indicators' in analysis_data:
            user_prompt += f"""

TECHNICAL INDICATORS:
{safe_json_dumps(analysis_data['technical_indicators'])}"""
        
        # 신호 분석 결과 추가
        if 'signal_analysis' in analysis_data:
            signal = analysis_data['signal_analysis']
            signals_list = signal.get('signals', [])
            
            user_prompt += f"""

SIGNAL ANALYSIS (베스트 프랙티스 기반 다중 지표 조합):
- Decision: {signal.get('decision', 'N/A')}
- Buy Score: {signal.get('buy_score', 0):.1f}
- Sell Score: {signal.get('sell_score', 0):.1f}
- Total Score: {signal.get('total_score', 0):.1f}
- Signal Strength: {signal.get('signal_strength', 0):.1f}
- Confidence: {signal.get('confidence', 'N/A')}

KEY SIGNALS (주요 신호 - 각 신호의 매수/매도 영향도를 전문적으로 분석하세요):
{chr(10).join(f'  • {s}' for s in signals_list) if signals_list else '  • 신호 없음'}

**중요**: 위의 각 신호를 다음 관점에서 분석하세요:
1. 각 신호가 매수/매도 결정에 미치는 구체적 영향
2. 신호 간 충돌이 있다면 어떤 신호가 우선순위를 가지는지와 그 이유
3. 신호의 강도 (Strong/Moderate/Weak)와 신뢰도
4. 시간대별 신호의 중요도 (일봉 > 4시간봉 > 15분봉)
5. 신호의 수렴(convergence) 또는 발산(divergence) 여부"""
        
        # 공포탐욕지수 추가
        if 'fear_greed_index' in analysis_data:
            fgi = analysis_data['fear_greed_index']
            user_prompt += f"""

FEAR & GREED INDEX (시장 심리 지표):
- Value: {fgi.get('value', 'N/A')}/100
- Classification: {fgi.get('classification', 'N/A')}
- Interpretation: 
  • 0-24: Extreme Fear (극도의 공포) - 매수 기회
  • 25-44: Fear (공포) - 매수 고려
  • 45-55: Neutral (중립)
  • 56-75: Greed (탐욕) - 매도 고려
  • 76-100: Extreme Greed (극도의 탐욕) - 매도 신호"""

        # 포지션 정보 추가
        if 'position_info' in analysis_data:
            pos = analysis_data['position_info']
            user_prompt += f"""

POSITION INFO:
- Average Buy Price: {pos.get('avg_buy_price', 0):,.0f} KRW
- Current Price: {pos.get('current_price', 0):,.0f} KRW
- Profit/Loss: {pos.get('profit_loss', 0):,.0f} KRW ({pos.get('profit_rate', 0):+.2f}%)
- Total Amount: {pos.get('total_amount', 0):.8f} {pos.get('currency', '')}
- Current Value: {pos.get('current_value', 0):,.0f} KRW"""
        
        # 변동성 지표 추가
        if 'volatility_indicators' in analysis_data:
            vol = analysis_data['volatility_indicators']
            user_prompt += f"""

VOLATILITY INDICATORS (변동성 분석):
- ATR: {vol.get('atr', 'N/A')}
- Bollinger Bands: Upper={self._format_number(vol.get('bb_upper', 'N/A'), ',.0f')}, Middle={self._format_number(vol.get('bb_middle', 'N/A'), ',.0f')}, Lower={self._format_number(vol.get('bb_lower', 'N/A'), ',.0f')}
- BB Width: {self._format_number(vol.get('bb_width', 'N/A'), '.2f')}% (변동성 확대/축소)
- Keltner Channels: Upper={self._format_number(vol.get('keltner_upper', 'N/A'), ',.0f')}, Lower={self._format_number(vol.get('keltner_lower', 'N/A'), ',.0f')}"""
        
        # 거래량 분석 추가
        if 'volume_analysis' in analysis_data:
            vol_analysis = analysis_data['volume_analysis']
            user_prompt += f"""

VOLUME ANALYSIS (거래량 심화 분석):
- Volume MA(20): {self._format_number(vol_analysis.get('volume_ma_20', 'N/A'), ',.0f')}
- Volume Ratio: {self._format_number(vol_analysis.get('volume_ratio', 'N/A'), '.2f')}x (현재/평균)
- OBV: {self._format_number(vol_analysis.get('obv', 'N/A'), ',.0f')}
- Volume Trend: {vol_analysis.get('volume_trend', 'N/A')}
- Unusual Volume: {vol_analysis.get('unusual_volume', False)} (평균의 2배 이상)
- Buying Pressure: {self._format_number(vol_analysis.get('buying_pressure', 'N/A'), '.1f')}/100
- Selling Pressure: {self._format_number(vol_analysis.get('selling_pressure', 'N/A'), '.1f')}/100"""
        
        # 모멘텀 지표 추가
        if 'momentum_indicators' in analysis_data:
            momentum = analysis_data['momentum_indicators']
            user_prompt += f"""

MOMENTUM INDICATORS (모멘텀 지표):
- ROC (10일): {self._format_number(momentum.get('roc', 'N/A'), '.2f')}%
- CCI: {self._format_number(momentum.get('cci', 'N/A'), '.1f')}
- Williams %R: {self._format_number(momentum.get('williams_r', 'N/A'), '.1f')}
- ADX (추세 강도): {self._format_number(momentum.get('adx', 'N/A'), '.1f')}
- +DI (상승 방향성): {self._format_number(momentum.get('plus_di', 'N/A'), '.1f')}
- -DI (하락 방향성): {self._format_number(momentum.get('minus_di', 'N/A'), '.1f')}"""
        
        # 시장 구조 분석 추가
        if 'market_structure' in analysis_data:
            structure = analysis_data['market_structure']
            user_prompt += f"""

MARKET STRUCTURE (시장 구조 분석):
- Support Levels (지지선): {len(structure.get('support_levels', []))}개
  {chr(10).join(f'  • {level["price"]:,.0f} KRW ({level["strength"]}, {level["touches"]}회 터치)' for level in structure.get('support_levels', [])[:3])}
- Resistance Levels (저항선): {len(structure.get('resistance_levels', []))}개
  {chr(10).join(f'  • {level["price"]:,.0f} KRW ({level["strength"]}, {level["touches"]}회 터치)' for level in structure.get('resistance_levels', [])[:3])}
- Fibonacci Retracement (피보나치 되돌림):
  {chr(10).join(f'  • {level}: {price:,.0f} KRW' for level, price in structure.get('fibonacci_levels', {}).items())}
- Price Structure:
  • Higher Highs: {structure.get('higher_highs', False)}
  • Higher Lows: {structure.get('higher_lows', False)}
  • Trend: {structure.get('trend_structure', 'N/A')}"""
        
        # 다중 시간대 분석 추가
        if 'timeframe_analysis' in analysis_data:
            tf = analysis_data['timeframe_analysis']
            user_prompt += f"""

MULTI-TIMEFRAME ANALYSIS (다중 시간대 분석):"""
            if '15min' in tf:
                user_prompt += f"""
- 15분봉: Trend={tf['15min'].get('trend', 'N/A')}, RSI={self._format_number(tf['15min'].get('rsi', 'N/A'), '.1f')}, MACD Signal={tf['15min'].get('macd_signal', 'N/A')}"""
            if '4hour' in tf:
                user_prompt += f"""
- 4시간봉: Trend={tf['4hour'].get('trend', 'N/A')}, Key Level Distance={self._format_number(tf['4hour'].get('key_level_distance', 'N/A'), '.2f')}%, Volume Profile={tf['4hour'].get('volume_profile', 'N/A')}"""
            if 'daily' in tf:
                user_prompt += f"""
- 일봉: Trend={tf['daily'].get('trend', 'N/A')}, MA Alignment={tf['daily'].get('ma_alignment', False)}"""
        
        # 리스크 메트릭스 추가
        if 'risk_metrics' in analysis_data:
            risk = analysis_data['risk_metrics']
            user_prompt += f"""

RISK METRICS (리스크 지표):
- Sharpe Ratio: {self._format_number(risk.get('sharpe_ratio', 'N/A'), '.2f')}
- Max Drawdown: {self._format_number(risk.get('max_drawdown', 'N/A'), '.2f')}%
- 30일 Volatility: {self._format_number(risk.get('volatility_30d', 'N/A'), '.2f')}%
- Liquidity Score: {self._format_number(risk.get('liquidity_score', 'N/A'), '.1f')}/100"""
        
        # 오더북 심화 분석 추가
        if 'advanced_orderbook' in analysis_data:
            adv_ob = analysis_data['advanced_orderbook']
            user_prompt += f"""

ADVANCED ORDERBOOK ANALYSIS (오더북 심화 분석):
- Bid/Ask Imbalance: {self._format_number(adv_ob.get('bid_ask_imbalance', 'N/A'), '.1f')} (-100=매도 압력, +100=매수 압력)
- Large Orders (Whale Walls): {len(adv_ob.get('large_orders', []))}개
  {chr(10).join(f'  • {order["side"].upper()}: {order["price"]:,.0f} KRW, Volume={order["volume"]:.4f} ({order["percentage"]:.1f}%)' for order in adv_ob.get('large_orders', [])[:3])}
- Spread Analysis:
  • Spread: {self._format_number(adv_ob.get('spread_analysis', {}).get('spread_bps', 'N/A'), '.2f')} bps
  • Trend: {adv_ob.get('spread_analysis', {}).get('spread_trend', 'N/A')}"""
        
        # 캔들 패턴 추가
        if 'candlestick_patterns' in analysis_data:
            patterns = analysis_data['candlestick_patterns']
            if patterns.get('recent_patterns'):
                user_prompt += f"""

CANDLESTICK PATTERNS (캔들 패턴):
{chr(10).join(f'  • {p["pattern"]}: {p["signal"]} 신호 (신뢰도: {p["confidence"]}, 위치: {p["location"]})' for p in patterns.get('recent_patterns', []))}"""
        
        # 백테스팅 결과 추가
        if 'backtest_result' in analysis_data:
            bt_result = analysis_data['backtest_result']
            metrics = bt_result.get('metrics', {})
            user_prompt += f"""

QUICK BACKTEST RESULTS (빠른 백테스팅 결과 - 최근 30일):
- Total Return: {self._format_number(metrics.get('total_return', 'N/A'), '.2f')}%
- Win Rate: {self._format_number(metrics.get('win_rate', 'N/A'), '.2f')}%
- Sharpe Ratio: {self._format_number(metrics.get('sharpe_ratio', 'N/A'), '.2f')}
- Max Drawdown: {self._format_number(abs(metrics.get('max_drawdown', 0)), '.2f')}%
- Total Trades: {metrics.get('total_trades', 'N/A')}
- Profit Factor: {self._format_number(metrics.get('profit_factor', 'N/A'), '.2f')}
- Filter Passed: {bt_result.get('passed', False)}

**중요**: 위 백테스팅 결과는 최근 30일 동안의 전략 성능을 보여줍니다. 
이 결과를 참고하여 현재 시장 상황과 과거 성과를 종합적으로 고려한 결정을 내려주세요.
백테스팅 성과가 좋지 않더라도 현재 시장 상황이 유리하면 매수/매도 결정을 할 수 있습니다."""

        user_prompt += """

위의 종합 데이터를 바탕으로 전문 투자자 관점에서 투자 결정을 내려주세요.

## 분석 요구사항:

1. **주요 신호 심층 분석**
   - 위에 나열된 각 주요 신호(KEY SIGNALS)에 대해 매수/매도 결정에 미치는 영향을 구체적으로 분석
   - 신호 간 충돌이 있다면 우선순위와 근거를 명확히 제시
   - 신호의 강도(Strong/Moderate/Weak)와 신뢰도를 평가

2. **지표별 영향도 분석**
   - 추세 지표(MA, EMA): 방향성 판단의 기본 근거
   - 모멘텀 지표(RSI, MACD, Stochastic): 과매수/과매도 및 반전 가능성
   - 변동성 지표(BB, ATR): 리스크 수준과 가격 행동의 맥락
   - 거래량 지표(OBV, Volume Ratio): 가격 움직임의 확인 또는 발산
   - 시장 구조(지지/저항, 피보나치): 리스크 관리 수준과 돌파/붕괴 구간
   - 캔들 패턴: 단기 반전 또는 지속 신호

3. **종합 판단 기준**
   - 기술적 지표의 일관성 (다중 지표 확인)
   - 변동성과 리스크 수준
   - 거래량과 모멘텀의 확인
   - 시장 구조 (지지/저항, 추세)
   - 다중 시간대 분석의 일치성
   - 오더북의 매수/매도 압력
   - 캔들 패턴의 신호

4. **reason 필드 작성 가이드**
   반드시 다음 6개 섹션으로 구성하여 작성하세요:
   
   **1. 종합 평가**: 현재 시장 상태의 한 문장 요약
   **2. 추세 분석**: MA/EMA 신호, 가격 구조, 다중 시간대 정렬/발산
   **3. 모멘텀 분석**: RSI, MACD, Stochastic 해석, 과매수/과매도 상태
   **4. 변동성 및 거래량 분석**: 변동성 지표 의미, 거래량 확인/발산, 비정상 거래량
   **5. 시장 구조 분석**: 주요 지지/저항 수준과 근접도, 피보나치 수준, 오더북 역학
   **6. 신호 종합 및 판단 근거**: 증거의 가중치, 리스크-보상 평가, 최종 결정 근거

반드시 한국어로 응답하고, 객관적이고 사실적이며 분석가답게 작성하세요.
JSON 형식으로 응답:
{"decision": "buy|sell|hold", "reason": "위 6개 섹션으로 구성된 상세한 기술적 분석 (한국어)", "confidence": "high|medium|low", "key_indicators": ["가장 중요한 지표1", "가장 중요한 지표2", ...]}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            ai_response = response.choices[0].message.content
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            Logger.print_info(f"[{timestamp}] AI 분석 중...")
            Logger.print_ai_response(timestamp, ai_response)
            
            decision_data = json.loads(ai_response)
            
            return {
                "decision": decision_data.get("decision", "").lower(),
                "reason": decision_data.get("reason", "No reason provided"),
                "confidence": decision_data.get("confidence", "unknown")
            }
            
        except json.JSONDecodeError as e:
            Logger.print_error(f"AI 응답 파싱 실패: {str(e)}")
            Logger.print_info(f"원본 응답: {ai_response}")
            return None
        except Exception as e:
            Logger.print_error(f"AI 분석 실패: {str(e)}")
            return None

